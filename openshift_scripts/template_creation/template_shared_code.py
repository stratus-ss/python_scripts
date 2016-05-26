#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Modified: May 20, 2016
# Primary Function:
# This is just a library for common code base for template related activities

from optparse import OptionParser
import sys
import datetime
import os
import __main__ as main


class TemplateParsing:

    # main.__file__ reads the name of the calling script. Examining this will help determine which help options to show

    parser = OptionParser()
    if not "export" in main.__file__:
        parser.add_option('--destination-project-name', '-d', dest = 'destination_project_name',
                      help = 'Specify the project to apply template to')
    if not "import" in main.__file__:
        parser.add_option('--source-project-name', '-s', dest = 'source_project_name',
                          help = 'Specify the project the resource which you wish to template is in')
    if not "configmap" in main.__file__:
        parser.add_option('--url', '-u', dest = 'url', help = '(Optional) Specify a URL to inject into the template.'
                                                          ' If the keyworld "replace" is used, the current route '
                                                          'is replaced with a similar url by swapping the project name')

        if not "app" in main.__file__:
            parser.add_option("--credentials-file", '-c', dest = 'credentials_file',
                      help = '(Optional) Specify a credentials file to use for the creation of secrets in the'
                             ' destination project. Current options are docker=<path to .dockercfg> or git=<path to '
                             'credentials file>', action = 'append')

    # Only show these options if transfering a single application. These are not applicable to project creation
    if "app" in main.__file__:
        parser.add_option('--app-name', '-a', dest = 'app_name', help = 'Specify an application to make a template from')
        parser.add_option('--env-variables', '-e', dest = 'env_variables',
                      help = '(Optional) environment variables to put in the template. ENV_NAME=\"value\"'
                             ' NOTE: escaping quotes is required', action = 'append')
    if "configmap" in main.__file__:
        parser.add_option('--configmap-file', dest = 'config_map_file',
                      help = 'Specify the configmap file to import from')
    if "export" in main.__file__:
        parser.add_option('--configmap-name', dest = 'config_map_name',
                          help = 'Specify the configmap resource name')

    (options, args) = parser.parse_args()

    # Inspecting the options to make sure something has been passed, if not show the help
    show_help = True
    for opt, value in options.__dict__.items():
        if value is not None:
            show_help = False
    if show_help:
        parser.print_help()
        sys.exit(2)

    @staticmethod
    def replace_value(line_to_replace, replace_with_this):
        split_on_this = ": "
        value_to_replace = [word + split_on_this for word in line_to_replace.split(split_on_this)]
        print("".join(value_to_replace[:-1]) + replace_with_this)
    
    @staticmethod
    def substitute_values_in_template(export_command, template_output, resource_dict):
        # Store the sys.stdout so that it is easy to restore later
        old_stdout = sys.stdout

        sys.stdout = open(template_output, 'w')
        previous_line = ""
        for current_line in os.popen(export_command).read().split("\n"):
            # This flag is used to make sure that we don't double print lines
            # if it is set to true, the global print statement is not run
            skip_line = False
            # If the url option has been defined, look for the route section
            if "configmap" in resource_dict.keys():
                remove_these_lines = ["creationTimestamp", "namespace", "resourceVersion", "selfLink", "uid"]
                if ":" in current_line:
                    yaml_value = current_line.split(":")[0].strip()
                    if yaml_value in remove_these_lines:
                        skip_line = True
            if "urls" in resource_dict.keys():
                if "host: " in current_line:
                    try:
                        # If we find a route section, tell the global print statement not to handle this line
                        # as it is going to be substituted
                        skip_line = True
                        # If we are simply keeping the same route but changing projects, overwrite the
                        # substitute_this_url variable with the appropriate url
                        if resource_dict['url'] == "replace":
                            replace_url = current_line.split(": ")[1].replace(resource_dict['source_project'],
                                                                              resource_dict['destination_project'])
                            TemplateParsing.replace_value(current_line, replace_url)
                        else:
                            TemplateParsing.replace_value(current_line, resource_dict['url'])
                    except NameError:
                        pass
            # If the environment variable substitution has been passed on the cli, attempt to split the values
            # passed and store the results in a dictionary for easier lookup
            if "environment_vars" in resource_dict.keys():
                environment_variable_dict = {}
                for value in resource_dict['environment_vars'].split():
                    try:
                        components = value.split("=")
                        environment_variable_dict[components[0]] = components[1]
                    except IndexError:
                        sys.stdout = old_stdout
                        print("The environment vairable %s is malformed")
                        print("Expected: env_var=value")
                        sys.exit(2)
                if "kind: DeploymentConfig" in current_line:
                    deployment_config_section = True
                try:
                    if deployment_config_section:
                        if "- name:" in previous_line:
                            env_variable_name = previous_line.split("name: ")[1]
                        if env_variable_name in environment_variable_dict:
                            if env_variable_name in previous_line:
                                skip_line = True
                                TemplateParsing.replace_value(current_line,
                                                              environment_variable_dict[env_variable_name])
                        if "status:" in current_line:
                            deployment_config_section = False
                except NameError:
                    pass
            if skip_line == False:
                print(current_line)
            previous_line = current_line
        sys.stdout.close()
        sys.stdout = old_stdout

    @staticmethod
    def export_as_template(export_command, template_full_path):
        os.popen("%s > %s" % (export_command, template_full_path)).read()

    @staticmethod
    def create_objects(destination_project, template_full_path, *args):
        change_to_project = os.popen("oc project %s 2> /dev/null" % destination_project).read()
        git_secret_name = "gitauth"
        docker_secret_name = "dockerconfig"
        if not change_to_project:
            os.popen("oc new-project %s" % destination_project)
        if args:
            for credentials_file in args[0]:
                path_to_file = credentials_file.split("=")[1]
                if "git" in credentials_file:
                    username, password = TemplateParsing.parse_credentials_file(path_to_file)
                    print("Adding git secret: %s" % git_secret_name)
                    os.popen("oc secrets new-basicauth %s --username=%s --password=%s -n %s"
                               % (git_secret_name, username, password, destination_project)).read()
                    print("Adding to serviceaccount/default\n")
                    os.popen("oc secrets add serviceaccount/default secrets/%s" % git_secret_name).read()
                if "docker" in credentials_file:
                    print("Adding .dockerconfig secret: %s" % docker_secret_name)
                    os.popen("oc secrets new %s .dockercfg=%s" % (docker_secret_name, path_to_file)).read()
                    print("Adding to serviceaccount/default and serviceaccount/builder\n")
                    os.popen("oc secrets add serviceaccount/default secrets/%s --for=pull" % docker_secret_name).read()
                    os.popen("oc secrets add serviceaccount/builder secrets/%s --for=pull" % docker_secret_name).read()
        print(os.popen("oc process -f %s | oc create -f -" % template_full_path)).read()

    @staticmethod
    def parse_credentials_file(path_to_file):
        username_split_keyword = "USERNAME"
        password_split_keyword = "PASSWORD"
        for line in open(path_to_file).readlines():
            if line.strip():
                if not line.startswith("#"):
                    if line.upper().startswith(username_split_keyword):
                        if line.upper().split(username_split_keyword)[1].startswith("="):
                            username = line.split("=")[1].strip()
                        if line.upper().split(username_split_keyword)[1].startswith(":"):
                            username = line.split(":")[1].strip()
                    if line.upper().startswith(password_split_keyword):
                        if line.upper().split(password_split_keyword)[1].startswith("="):
                            password = line.split("=")[1].strip()
                        if line.upper().split(password_split_keyword)[1].startswith(":"):
                            password = line.split(":")[1].strip()
        return(username, password)



class PermissionParsing:

    @staticmethod
    def add_to_dictionary(dictionary, role_name, component, value):
        if role_name in dictionary:
            dictionary[role_name][component] = value
        else:
            dictionary[role_name] = {component: value}

    @staticmethod
    def get_project_permissions(project_name):
        def parse_output(incoming_dict, incoming_role, object_name):
            if "none" in line:
                pass
            else:
                dict_object = " ".join(line.split()[1:]).replace(",", "")
                PermissionParsing.add_to_dictionary(incoming_dict, incoming_role, object_name, dict_object)

        my_dict = {}
        policy_bindings = os.popen("oc describe policybinding -n %s" % project_name).read().split("\n")
        for line in policy_bindings:
            if "Role:" in line:
                role = line.split()[-1]
            if "Users:" in line:
                parse_output(my_dict, role, "Users")
            if "Groups" in line:
                parse_output(my_dict, role, "Groups")
            if "ServiceAccounts" in line:
                parse_output(my_dict, role, "ServiceAccounts")
        return(my_dict)
