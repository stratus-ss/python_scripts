#!/usr/bin/env python
# Primary Function: This script will check an environment config file which is related to software loads
# It takes a component, a config file, and an optional blueprint as options. It then searches the config file
# If the component version exists in the file, it will check for the corresponding _env version.
# If both of these are the same, the script will exit, pushing an error condition to Jenkins, which should then abort
# If the version is not the same, the config file will be updated and eventually checked into stash

import sys
import os
import argparse
import fileinput
import shutil
import datetime
from tools.common import textColours
import acs.component
import ConfigParser


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


def update_config(component_and_version, config_file, previous_version_dict, proposed_version_dict):
    """Updates the env config file. This method will create a backup of the file, write the proposed changes
    and update previous_version_dict/proposed_version_dict for later comparison"""

    def insert_component_into_dict(name, current_version, proposed_version=None):
        # There will only be a proposed version on the component that is being upgraded
        # otherwise just keep the current value. This is used to track the blueprint for a component in case
        # of a roll back. Conversely if the only thing that is passed in is the blueprint, track the component
        # version
        if proposed_version is None:
            proposed_version = current_version
        if "_env" in name:
            acs_component = name.split("_env")[0]
            add_to_dictionary(previous_version_dict, acs_component, "component_env_version",
                              current_version)
            add_to_dictionary(proposed_version_dict, acs_component, "component_env_version",
                              proposed_version)
        else:
            acs_component = name
            add_to_dictionary(previous_version_dict, acs_component, "component_version",
                              current_version)
            add_to_dictionary(proposed_version_dict, acs_component, "component_version",
                              proposed_version)

    config = ConfigParser.RawConfigParser()
    config.optionxform = str  # make keys case sensitive
    config.read(config_file)
    # Search the config sections for possible items
    for sections in config.sections():
        for items in config.items(sections):
            for item in component_and_version:
                # component_name is refers to the actual component and not the blueprint which is why they are split
                proposed_component_version = item.split(":")[1].strip()
                user_inputted_component = item.split(":")[0].strip()
                # Look for the component that the user passed in, inside of the section in the config file
                # configParser returns ('component', 'value')
                if user_inputted_component in items:
                    if user_inputted_component == items[0]:
                        current_version_number = items[1]
                        insert_component_into_dict(user_inputted_component, current_version_number,
                                                   proposed_component_version)
                        config.set(sections, user_inputted_component, proposed_component_version)
    # write the modified config file back
    with open(config_file, 'wb') as configfile:
        config.write(configfile)


def format_string_to_json(component_and_env_dict):
    """This method creates a json file formatted for the load.py script. In the event of a fallback situation, this file
    needs to have the following information:
    {"ahp-reporting":{"version":{"current":"0.0.166","new":"0.0.166"},"type":"acs","env_version":
    {"current":"tec-qa-sjc_3.0.1","new":"tec-qa-sjc_3.0.1"}}}
    """
    filename = "/tmp/rollback_version"
    close_file = False
    env_string = None
    component_string = None
    # Attempt to remove any previous files, if none exists just eat the error
    try:
        os.remove(filename)
    except OSError:
        pass
    print("evaluating components to generate %s" % filename)
    for component in component_and_env_dict.keys():
        for key, version in component_and_env_dict[component].iteritems():
            if key == "component_env_version":
                env_string = '"env_version":{"current":"%s","new":"%s"}}' % (version, version)
            if key == "component_version":
                component_string = '"%s":{"version":{"current":"%s","new":"%s"}' % (component, version, version)
        # This section sets the type to ACS if the component is found in the static mapping
        if component in acs.component.CMPS:
            if env_string is not None and component_string is not None:
                json_string = '{%s,"type":"acs",%s}' % (component_string, env_string)
            elif env_string is not None:
                json_string = '{%s: {%s,"type":"acs"}' % (component, env_string)
            else:
                json_string = '{%s,"type":"acs"}' % component_string
        # If the component isn't apart of the ACS and doesn't have an env_version just output the component version
        else:
            if env_string is None:
                json_string = '{%s}' % component_string
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
        print("%s has been closed. The rollback file has been written" % filename)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='%s    Updates the environment file with new components/blueprints'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                     epilog='%s \nSample usage: %s --config-file conf/env/tec-qa.env.conf '
                                            ' --comp ahp-booking:1.2.259 --blueprint ahp-booking_env:tec-qa-sjc_2.0.1 '
                                            '\n%s' % (textColours.HIGHLIGHT, sys.argv[0], textColours.ENDC),
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--comp', '-c', action='append', dest='component_name', help='A list of component labels'
                                                                                     ' associated with software loads',
                        required=True)
    parser.add_argument('--config-file', '-f', action='store', dest='config_file', help='The config file with all the '
                                                                                        'environment information',
                        required=True)
    parser.add_argument('--blueprint', '-b', action='append', dest='blue_print', help='')
    options = parser.parse_args()

    # This dict stores the component and the previous version to track in case of rollback
    previous_component_version_dict = {}
    proposed_component_version_dict = {}
    if options.blue_print is not None:
        if "_env" not in options.blue_print[0]:
            print("Unexpected input for blueprint. Expected blueprint with _env")
            parser.print_help()
            sys.exit()
        list_of_components = options.component_name + options.blue_print
    else:
        list_of_components = options.component_name
    todays_date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
    backup_location = "%s.backup" % options.config_file
    shutil.copyfile(options.config_file, backup_location)
    print("physical file backed up to: %s" % backup_location)

    script_input_check(options.component_name)
    # The update_config method also generates the content for previous_component_version_dict and
    # proposed_component_version_dict. There is no harm writing the file before doing the version sanity check
    # because if there is an error condition the script aborts and the pipeline should /NOT/ push the file in failure
    # case
    update_config(list_of_components, options.config_file, previous_component_version_dict,
                  proposed_component_version_dict)

    for key in previous_component_version_dict.keys():
        if key in proposed_component_version_dict.keys():
            if previous_component_version_dict[key] == proposed_component_version_dict[key]:
                sys.stderr.write("Detected the same versions of %s and %s_env... aborting as there is no change to "
                                 "make\n" % (key, key))
                sys.exit(1)
    format_string_to_json(previous_component_version_dict)
