#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Modified: June 1, 2016
# Primary Function:
# This script will interact with OpenShift Enterprise (tested on v 3.1) in order to create a template
# from an existing project.
#
# Secondary Function:
# You can optionally replace the route (if one exists) with a custom route, or use the word 'replace'
# to simply swap project names.
# Ex. ./app_to_template.py -s mobileproject -a myapp1 -u replace -d ultranew
# This will change: myapp1-mobileproject.example.com ---> myapp1-ultranew.example.com
# You can also optionally change environment variables, but because of the way the golang parser works
# you need to pass in your values like so MYVARNAME=\"value\"

import datetime
import os
from template_shared_code import TemplateParsing
import sys

###### Variable declaration

template_name = TemplateParsing.options.source_project_name + "_project_template"
template_output_path = "/tmp/"
template_output = template_output_path + template_name + ".yaml"
ose_resources_to_export = ['imagestream', 'deploymentconfig', 'buildconfig', 'service', 'route']
resources_to_import = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")
resource_dictionary = {}
promote_image = False
###### End variable declaration

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % TemplateParsing.options.source_project_name).read()
valid_apps = []
for current_line in os.popen("/usr/bin/oc get dc").read().split("\n"):
    if "NAME" in current_line:
        pass
    else:
        # Sometimes there is a trailing newline character so this goes in a try/except block to suppress that
        try:
            valid_apps.append(current_line.split()[0])
        except IndexError:
            pass

# All 4 docker options are required to proceed with docker pull/push.
# If all 4 are present, omit the build config because an image 'promotion' is occurring
if TemplateParsing.options.ose_registry is not None and TemplateParsing.options.copy_build_config.lower() == "no" \
   and TemplateParsing.options.ose_token is not None and TemplateParsing.options.docker_username is not None:
    ose_resources_to_export = ['imagestream', 'deploymentconfig', 'service', 'route']
    resource_dictionary['image_deployment'] = TemplateParsing.options.ose_registry
    promote_image = True


for resource in ose_resources_to_export:
    for apps in valid_apps:
        resource_path = "%s/%s" % (resource, apps)
        resources_to_import.append(resource_path)

# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

export_command = "/usr/bin/oc export %s --as-template=%s" % (" ".join(resources_to_import), template_name)

if TemplateParsing.options.url is not None:
    resource_dictionary['source_project'] = TemplateParsing.options.source_project_name
    resource_dictionary['destination_project'] = TemplateParsing.options.destination_project_name
    resource_dictionary["url"] = TemplateParsing.options.url
    TemplateParsing.substitute_values_in_template(export_command, template_output, resource_dictionary)
else:
    print("No URL options are specified, this means that you would have projects sharing the same route.\n"
          "This is probably a bad idea. Exiting...")
    sys.exit()

if TemplateParsing.options.credentials_file:
    TemplateParsing.create_objects(TemplateParsing.options.destination_project_name, template_output,
                                   TemplateParsing.options.credentials_file)
else:
    TemplateParsing.create_objects(TemplateParsing.options.destination_project_name, template_output)

if promote_image:
    # Because a project could have multiple applications, loop over each and then start docker pull/push
    for application in valid_apps:
        TemplateParsing.docker_promote_image(TemplateParsing.options.ose_registry, TemplateParsing.options.docker_username,
                                        TemplateParsing.options.ose_token, TemplateParsing.options.source_project_name,
                                        TemplateParsing.options.destination_project_name,
                                        application)
