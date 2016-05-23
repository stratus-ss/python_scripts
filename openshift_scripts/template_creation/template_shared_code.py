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

class TemplateParsing:

    parser = OptionParser()
    parser.add_option('--source-project-name', '-s', dest = 'source_project_name',
                      help = 'Specify the project the application template is in')
    parser.add_option('--destination-project-name', '-d', dest = 'destination_project_name',
                      help = 'Specify the project the application template is in')
    parser.add_option('--url', '-u', dest = 'url', help = '(Optional) Specify a URL to inject into the template.'
                                                          ' If the keyworld "replace" is used, the current route '
                                                          'is replaced with a similar url by swapping the project name')
    parser.add_option('--env-variables', '-e', dest = 'env_variables', help = '(Optional) environment variables to'
                                                                              ' put in the template. ENV_NAME=\"value\"'
                                                                              ' NOTE: escaping quotes is required',
                      action = 'append')
    parser.add_option('--app-name', '-a', dest = 'app_name', help = 'Specify an application to make a template from')

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
    def substitute_values_in_template(export_command, template_output, substitute_this_url, environment_variables,
                                      source_project, destination_project):
        # Store the sys.stdout so that it is easy to restore later
        old_stdout = sys.stdout

        if substitute_this_url or environment_variables:
            sys.stdout = open(template_output, 'w')
            previous_line = ""
            for current_line in os.popen(export_command).read().split("\n"):
                # This flag is used to make sure that we don't double print lines
                # if it is set to true, the global print statement is not run
                skip_line = False
                # If the url option has been defined, look for the route section
                if substitute_this_url:
                    if "kind: Route" in current_line:
                        route_section = True
                    if "status:" in current_line:
                        route_section = False
                    if "host: " in current_line:
                        try:
                            # If we find a route section, tell the global print statement not to handle this line
                            # as it is going to be substituted
                            #if route_section:
                            skip_line = True
                            # If we are simply keeping the same route but changing projects, overwrite the
                            # substitute_this_url variable with the appropriate url
                            if substitute_this_url == "replace":
                                replace_url = current_line.split(": ")[1].replace(source_project,
                                                                                          destination_project)
                                TemplateParsing.replace_value(current_line, replace_url)
                            else:
                                TemplateParsing.replace_value(current_line, substitute_this_url)
                        except NameError:
                            pass
                # If the environment variable substitution has been passed on the cli, attempt to split the values
                # passed and store the results in a dictionary for easier lookup
                if environment_variables:
                    environment_variable_dict = {}
                    for value in environment_variables:
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
    def create_objects(destination_project, template_full_path):
        change_to_project = os.popen("oc project %s 2> /dev/null" % destination_project).read()
        if not change_to_project:
            os.popen("oc new-project %s" % destination_project)
        print(os.popen("oc process -f %s | oc create -f -" % template_full_path)).read()


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
