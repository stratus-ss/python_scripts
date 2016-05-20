#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Primary Function:
# This script will interact with OpenShift Enterprise (tested on v 3.1) in order to create a template
# from an existing application inside of a project.
#
# Secondary Function:
# You can optionally replace the route (if one exists) with a custom route. The script will output the
# location of the template created. The idea for this is so that it can be used in conjunction with
# a process that will recreate the application from the template in a new project
# Ex: oc process -f `./app_to_template.py --source-project-name myproject --app-name cakephp-example \
# --url mynewapp.my-subdomain.example.com | oc create -f -

import os
import sys
import datetime
from optparse import OptionParser

parser = OptionParser()
parser.add_option('--source-project-name', '-p', dest = 'source_project_name',
                  help = 'Specify the project the application template is in')
parser.add_option('--app-name', '-a', dest = 'app_name', help = 'Specify an application to make a template from')
parser.add_option('--url', '-u', dest = 'url', help = '(Optional) Specify a URL to inject into the template')
(options, args) = parser.parse_args()

if not options.source_project_name or not options.app_name:
    parser.print_help()
    sys.exit()

# Store the sys.stdout so that it is easy to restore later
old_stdout = sys.stdout
# We want to store the current project so we can return to it after we create the template
current_project = os.popen("oc project").read().split()[2]
template_name = options.app_name + "_template"
template_output_path = "/tmp/"
template_output = template_output_path + template_name + ".yaml"
ose_resources_to_export = ['imagestream', 'deploymentconfig', 'buildconfig', 'service', 'route']
resource_with_apps = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")

for resource in ose_resources_to_export:
    resource_with_apps.append("%s/%s" % (resource, options.app_name))

# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % options.source_project_name).read()

# Check to make sure the application exists in the project
# Assume that the deployment config is going to have the same name as the app
app_in_project = False
for line in os.popen("/usr/bin/oc get dc").read().split("\n"):
    if options.app_name in line:
        app_in_project = True

if app_in_project:
    export_command = "/usr/bin/oc export %s --as-template=%s" % (" ".join(resource_with_apps), template_name)
    # If the optional url flag was passed into the script, search the text for a route spec
    # At the time of writing this is denoted by "host: <url>" in the spec section of a route
    if options.url:
        sys.stdout = open(template_output, 'w')
        for line in os.popen(export_command).read().split("\n"):
            if "kind: Route" in line:
                route_section = True
            if "host: " in line:
                if route_section:
                    split_on_this = ": "
                    host_url_list = [word + split_on_this for word in line.split(split_on_this)]
                    print("".join(host_url_list[:-1]) + options.url)
            else:
                print(line)

            if "status:" in line:
                route_section = False
        sys.stdout.close()
        sys.stdout = old_stdout
    else:
        os.popen("%s > %s" % (export_command, template_output))
    print(template_output)
else:
    print("%s was not found in project %s" % (options.app_name, options.source_project_name))
    sys.exit(2)

# return to the project where the template was created
os.popen("oc project %s" % current_project).read()