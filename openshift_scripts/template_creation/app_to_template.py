#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Modified: June 1, 2016
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
from template_shared_code import TemplateParsing


if not TemplateParsing.options.source_project_name or not TemplateParsing.options.app_name:
    TemplateParsing.parser.print_help()
    sys.exit()

# Store the sys.stdout so that it is easy to restore later
old_stdout = sys.stdout

# We want to store the current project so we can return to it after we create the template
# In case the project has been deleted or is missing, switch to the default project
try:
    destination_project = os.popen("oc project 2>/dev/null").read().split()[2]
except IndexError:
    os.popen("oc project default").read()

template_name = TemplateParsing.options.app_name + "_template"
template_output_path = "/tmp/"
template_output = template_output_path + template_name + ".yaml"
ose_resources_to_export = ['imagestream', 'deploymentconfig', 'buildconfig', 'service', 'route']
resource_with_apps = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")
resource_dictionary = {}
promote_image = False
###### End variable declaration


# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % TemplateParsing.options.source_project_name).read()
print("Checking for valid configuration files for %s in %s" % (TemplateParsing.options.app_name,
                                                               TemplateParsing.options.source_project_name))

# Check to make sure the application exists in the project
# Assume that the deployment config is going to have the same name as the app
app_in_project = False
for current_line in os.popen("/usr/bin/oc get dc").read().split("\n"):
    if TemplateParsing.options.app_name in current_line:
        app_in_project = True
        print("Valid configurations found...")

if app_in_project:
    if TemplateParsing.options.ose_registry is not None and TemplateParsing.options.copy_build_config.lower() == "no" \
       and TemplateParsing.options.ose_token is not None and TemplateParsing.options.docker_username is not None:
        ose_resources_to_export = ['imagestream', 'deploymentconfig', 'service', 'route']
        resource_dictionary['image_deployment'] = TemplateParsing.options.ose_registry
        promote_image = True
    for resource in ose_resources_to_export:
        resource_with_apps.append("%s/%s" % (resource, TemplateParsing.options.app_name))
    export_command = "/usr/bin/oc export %s --as-template=%s" % (" ".join(resource_with_apps), template_name)
    # If the optional url flag was passed into the script, search the text for a route spec
    # At the time of writing this is denoted by "host: <url>" in the spec section of a route
    if TemplateParsing.options.url is not None or TemplateParsing.options.env_variables is not None:
        resource_dictionary['source_project'] = TemplateParsing.options.source_project_name
        resource_dictionary['destination_project'] = TemplateParsing.options.destination_project_name
        if TemplateParsing.options.url is not None:
            resource_dictionary["url"] = TemplateParsing.options.url
        if TemplateParsing.options.env_variables is not None:
            resource_dictionary["environment_vars"] = TemplateParsing.options.env_variables
        TemplateParsing.substitute_values_in_template(export_command, template_output, resource_dictionary)
    else:
        TemplateParsing.export_as_template(export_command, template_output)
else:
    print("%s was not found in project %s" % (TemplateParsing.options.app_name,
                                              TemplateParsing.options.source_project_name))
    sys.exit(2)

TemplateParsing.create_objects(TemplateParsing.options.destination_project_name, template_output)

if promote_image:
    TemplateParsing.docker_promote_image(TemplateParsing.options.ose_registry, TemplateParsing.options.docker_username,
                                     TemplateParsing.options.ose_token, TemplateParsing.options.source_project_name,
                                     TemplateParsing.options.destination_project_name, TemplateParsing.options.app_name)