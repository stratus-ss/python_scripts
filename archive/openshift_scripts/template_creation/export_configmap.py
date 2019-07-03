#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Primary Function:
# This will export a config map from a project

from template_shared_code import TemplateParsing
import os

template_name = TemplateParsing.options.source_project_name + "_" + TemplateParsing.options.config_map_name + \
                "_configmap_template"
template_output_path = "/tmp/"
template_output = template_output_path + template_name + ".yaml"
export_command = "oc get configmap %s -n %s -o yaml" % (TemplateParsing.options.config_map_name,
                                                        TemplateParsing.options.source_project_name)
resource_dict = {"configmap": "import"}

TemplateParsing.substitute_values_in_template(export_command, template_output, resource_dict)
print("Config map generated: %s" % template_output_path)