#!/usr/bin/env python
# Primary Function: This script will check an environment config file which is related to software loads
# It takes a component, a config file, and an optional blueprint as options. It then searches the config file
# If the component version exists in the file, the run will abort raising an error to Jenkins
# If the version is not the same, the config file will be updated and eventually checked into stash

import sys
import os
import argparse
import fileinput
import shutil
import datetime
from tools.common import textColours

parser = argparse.ArgumentParser(description='%s    Updates the environment file with new components/blueprints'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                 epilog='%s \nSample usage: %s --config-file conf/env/tec-qa.env.conf '
                                        ' --comp ahp-booking:1.2.259 --blueprint ahp-booking_env:tec-qa-sjc_2.0.1 '
                                        '\n%s' % (textColours.HIGHLIGHT, sys.argv[0], textColours.ENDC),
                                 formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument('--comp', '-c', action='append', dest='component_name', help='A list of component labels'
                    ' associated with software loads', required=True)
parser.add_argument('--config-file', '-f', action='store', dest='config_file', help='The config file with all the '
                                                                                    'environment information',
                    required=True)
parser.add_argument('--blueprint', '-b', action='append', dest='blue_print', help='')
options = parser.parse_args()


def script_input_check(component_to_check):
    """This is an input sanitation to make sure that blueprints and components are passed in
    component:version"""
    for components in component_to_check:
        try:
            components.split(":")[1]
        except IndexError:
            print(textColours.FAIL + textColours.BOLD +
                  "An argument was passed in but was not in the proper format: %s\n" % components + textColours.ENDC)
            parser.print_help()
            sys.exit(1)

def add_to_dictionary(dictionary, name_of_component, component_type, version):
        if name_of_component in dictionary:
            dictionary[name_of_component][component_type] = version
        else:
            dictionary[name_of_component] = {component_type: version}

def update_config(component_and_version, config_file, previous_version_dict):
    component_name = component_and_version.split(":")[0].strip()
    proposed_component_version = component_and_version.split(":")[1].strip()
    for line in fileinput.FileInput(config_file, inplace=1):
        if not line.isspace():
            if line.split()[0] == component_name:
                current_component_version_number = line.split(" = ")[1].strip()
                add_to_dictionary(previous_version_dict, component_name, "component_name",
                                                                         current_component_version_number)
                print(component_name + " = " + proposed_component_version)
                if current_component_version_number == proposed_component_version:
                    sys.stderr.write("%s Component version already exists in file: %s\n" % (textColours.FAIL,
                                                                                            component_and_version))
                    sys.exit(1)
            elif line.split()[0] == component_name + "_env":
                current_component_env_version = line.split(" = ")[1].strip()
                add_to_dictionary(previous_version_dict, component_name, "component_env_version",
                                                                         current_component_env_version)
                print(line),
            else:
                print(line),
        else:
            print(line),


def format_string_to_json(component_and_env_dict):
    filename = "/tmp/rollback_version"
    close_file = False
    env_string = None
    # Attempt to remove any previous files, if none exists just eat the error
    try:
        os.remove(filename)
    except OSError:
        pass
    for component in component_and_env_dict.keys():
        for key, version in component_and_env_dict[component].iteritems():
            if key == "component_env_version":
                env_string = '"env_version":{"current":"%s","new":"%s"}}' % (version, version)
            if key == "component_name":
                component_string = '"%s":{"version":{"current":"%s","new":"%s"}' % (component, version, version)
        if env_string is not None:
            json_string = '{%s,"type":"acs",%s}' % (component_string, env_string)

            # Check if the file has already been created. If it does append to the file, if not do a write operation
            # The file should only exist at this point if it has had current json data written to it
            if os.path.isfile(filename):
                write_file = open(filename, "a")
            else:
                write_file = open(filename, "w")
            write_file.write(json_string)
            write_file.write("\n")
            close_file = True
    if close_file:
        write_file.close()

if __name__ == "__main__":

    # This dict stores the component and the previous version to track in case of rollback
    previous_component_version_dict = {}
    if options.blue_print is not None:
        list_of_components = options.component_name + options.blue_print
    else:
        list_of_components = options.component_name
    todays_date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
    backup_location = "%s.backup" % options.config_file
    shutil.copyfile(options.config_file, backup_location)
    print("physical file backed up to: %s" % backup_location)

    script_input_check(options.component_name)
    for component in list_of_components:
        update_config(component, options.config_file, previous_component_version_dict)

    format_string_to_json(previous_component_version_dict)

