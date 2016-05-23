#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Modified: May 20, 2016
# Primary Function:
# This script will interact with OpenShift Enterprise (tested on v 3.1) in order to create a template
# from an existing application inside of a project.
#
# Secondary Function:
# You can optionally replace the route (if one exists) with a custom route, or use the word 'replace'
# to simply swap project names.
# Ex. ./app_to_template.py -s mobileproject -a myapp1 -u replace -d ultranew
# myapp1-mobileproject.example.com ---> myapp1-ultranew.example.com
# You can also optionally change environment variables, but because of the way the golang parser works
# you need to pass in your values like so MYVARNAME=\"value\"


import os
import sys
import datetime
from optparse import OptionParser

###### Variable declaration
parser = OptionParser()
parser.add_option('--source-project-name', '-s', dest = 'source_project_name',
                  help = 'Specify the project the application template is in')
parser.add_option('--destination-project-name', '-d', dest = 'destination_project_name',
                  help = 'Specify the project the application template is in')
parser.add_option('--app-name', '-a', dest = 'app_name', help = 'Specify an application to make a template from')
parser.add_option('--url', '-u', dest = 'url', help = '(Optional) Specify a URL to inject into the template.'
                                                      ' If the keyworld "replace" is used, the current route '
                                                      'is replaced with a similar url by swapping the project name')
parser.add_option('--env-variables', '-e', dest = 'env_variables', help = '(Optional) environment variables to'
                                                                          ' put in the template. ENV_NAME=\"value\"'
                                                                          ' NOTE: escaping quotes is required',
                  action = 'append')
(options, args) = parser.parse_args()

if not options.source_project_name or not options.app_name:
    parser.print_help()
    sys.exit()

# Store the sys.stdout so that it is easy to restore later
old_stdout = sys.stdout

# We want to store the current project so we can return to it after we create the template
# In case the project has been deleted or is missing, switch to the default project
try:
    destination_project = os.popen("oc project").read().split()[2]
except IndexError:
    os.popen("oc project default").read()

template_name = options.app_name + "_template"
template_output_path = "/tmp/"
template_output = template_output_path + template_name + ".yaml"
ose_resources_to_export = ['imagestream', 'deploymentconfig', 'buildconfig', 'service', 'route']
resource_with_apps = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")

for resource in ose_resources_to_export:
    resource_with_apps.append("%s/%s" % (resource, options.app_name))

###### End variable declaration


def replace_value(line_to_replace, replace_with_this):
    split_on_this = ": "
    value_to_replace = [word + split_on_this for word in line_to_replace.split(split_on_this)]
    print("".join(value_to_replace[:-1]) + replace_with_this)


########

# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

# Check to see if the project exists, if it does not, create it
if options.destination_project_name:
    project_needs_to_be_created = True
    for project in os.popen("oc get projects").read().split("\n"):
        try:
            existing_project_name = project.split()[0]
            if options.destination_project_name in existing_project_name:
                project_needs_to_be_created = False
                destination_project = options.destination_project_name
        except IndexError:
            pass
    if project_needs_to_be_created:
        os.popen("oc new-project %s" % options.destination_project_name)

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % options.source_project_name).read()
print("Checking for valid configuration files for %s in %s" % (options.app_name, options.source_project_name))

# Check to make sure the application exists in the project
# Assume that the deployment config is going to have the same name as the app
app_in_project = False
for current_line in os.popen("/usr/bin/oc get dc").read().split("\n"):
    if options.app_name in current_line:
        app_in_project = True
        print("Valid configurations found...")

if app_in_project:
    export_command = "/usr/bin/oc export %s --as-template=%s" % (" ".join(resource_with_apps), template_name)
    # If the optional url flag was passed into the script, search the text for a route spec
    # At the time of writing this is denoted by "host: <url>" in the spec section of a route
    if options.url or options.env_variables:
        sys.stdout = open(template_output, 'w')
        previous_line = ""
        for current_line in os.popen(export_command).read().split("\n"):
            # This flag is used to make sure that we don't double print lines
            # if it is set to true, the global print statement is not run
            skip_line = False
            # If the url option has been defined, look for the route section
            if options.url:
                if "kind: Route" in current_line:
                    route_section = True
                if "host: " in current_line:
                    try:
                        # If we find a route section, tell the global print statement not to handle this line
                        # as it is going to be substituted
                        if route_section:
                            skip_line = True
                            # If we are simply keeping the same route but changing projects, overwrite the options.url
                            # variable with the appropriate url
                            if options.url == "replace":
                                options.url = current_line.split(": ")[1].replace(options.source_project_name,
                                                                                  options.destination_project_name)
                            replace_value(current_line, options.url)
                        if "status:" in current_line:
                            route_section = False
                    except NameError:
                        pass
            # If the environment variable substitution has been passed on the cli, attempt to split the values passed
            # and store the results in a dictionary for easier lookup
            if options.env_variables:
                environment_variable_dict = {}
                for value in options.env_variables:
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
                                replace_value(current_line, environment_variable_dict[env_variable_name])
                        if "status:" in current_line:
                            deployment_config_section = False
                except NameError:
                    pass
            if skip_line == False:
                print(current_line)
            previous_line = current_line
        sys.stdout.close()
        sys.stdout = old_stdout
    else:
        os.popen("%s > %s" % (export_command, template_output))
    print(template_output)
else:
    print("%s was not found in project %s" % (options.app_name, options.source_project_name))
    sys.exit(2)

# return to the project where the template was created
os.popen("oc project %s" % options.destination_project_name).read()
print(os.popen("oc process -f %s | oc create -f -" % template_output).read())