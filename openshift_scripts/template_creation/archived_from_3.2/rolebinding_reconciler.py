#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Primary Function:
# This script will interact with OpenShift Enterprise (tested on v 3.1) in order to retreive the permissions
# on an existing project and apply them to a different project

from template_shared_code import PermissionParsing
from template_shared_code import TemplateParsing
import sys
import os

try:
    permissions_dictionary = PermissionParsing.get_project_permissions(TemplateParsing.options.source_project_name)
except NameError:
    print("You did not specify a project to get the policy bindings from (--source-project-name=)")
    TemplateParsing.parser.print_help()
    sys.exit(2)

try:
    TemplateParsing.options.destination_project_name
except NameError:
    print("You did not specify which project to apply the bindings to (--destination-project-name)")
    sys.exit(2)

for keys in permissions_dictionary.keys():
    if "Groups" in permissions_dictionary[keys]:
        print(os.popen("oadm policy add-role-to-group %s %s -n %s" % (keys, permissions_dictionary[keys]["Groups"],
                                                            TemplateParsing.options.destination_project_name))).read()
    if "Users" in permissions_dictionary[keys]:
        print(os.popen("oadm policy add-role-to-user %s %s -n %s" % (keys, permissions_dictionary[keys]["Users"],
                                                            TemplateParsing.options.destination_project_name))).read()

