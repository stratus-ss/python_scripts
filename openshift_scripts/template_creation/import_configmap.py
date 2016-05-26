#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Primary Function:
# This will import a config map into a project

from template_shared_code import TemplateParsing
import os
import sys

try:
    # Storing the creation in a variable because if there is an error, the variable will be empty
    creation_output = os.popen("oc create -f %s -n %s 2> /dev/null" %
             (TemplateParsing.options.config_map_file, TemplateParsing.options.destination_project_name)).read()
except NameError:
    print("Syntax error, you need to specify --configmap-file and --destination-project-name "
          "in order to import a configmap into a specific project")
    sys.exit(2)
if creation_output:
    for line in open(TemplateParsing.options.config_map_file).readlines():
        if "name:" in line:
            configmap_name =  line.split(": ")[1].strip()

    try:
        print("Created configmap %s in project %s" % (configmap_name, TemplateParsing.options.destination_project_name))
    except NameError:
        print("New config map added to project %s using the configmap file %s" %
              (TemplateParsing.options.destination_project_name, TemplateParsing.options.config_map_file))
else:
    print("There was an error processing %s. Is it a properly formatted yaml or json file? "
          "Does the configmap name already exist in the destination project?" %
          TemplateParsing.options.config_map_file)