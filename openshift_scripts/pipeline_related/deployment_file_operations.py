#!/usr/bin/env python
# Primary Function: This script will check an environment config file which is related to software loads
# It takes a component, a config file, and an optional blueprint as options. It then searches the config file
# If the component version exists in the file, it will check for the corresponding _env version.
# If both of these are the same, the script will exit, pushing an error condition to Jenkins, which should then abort
# If the version is not the same, the config file will be updated and eventually checked into stash

import sys
import os
import argparse
import shutil
from tools.common import textColours
from tools import artifactory, log
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
        dictionary[name_of_component][component_type] = [version]
    else:
        dictionary[name_of_component] = {component_type: [version]}


def update_config(component_and_version, config_parser_object, config_file, previous_version_dict,
                  proposed_version_dict):
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

    # Search the config sections for possible items
    for sections in config_parser_object.sections():
        for items in config_parser_object.items(sections):
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
                        config_parser_object.set(sections, user_inputted_component, proposed_component_version)
    # write the modified config file back
    with open(config_file, 'wb') as configfile:
        config.write(configfile)


def format_string_to_json(previous_component_dict, component_being_deployed_dict, output_directory):
    """This method creates a json file formatted for the load.py script. In the event of a fallback situation, this file
    needs to have the following information:
    {"ahp-reporting":{"version":{"current":"0.0.166","new":"0.0.166"},"type":"acs","env_version":
    {"current":"tec-qa-sjc_3.0.1","new":"tec-qa-sjc_3.0.1"}}}
    """

    def write_json_file(component_dict, json_filename):
        close_file = False
        json_env_string = None
        json_component_string = None

        # Attempt to remove any previous files, if none exists just eat the error
        try:
            os.remove(json_filename)
        except OSError:
            pass
        log.debug("evaluating components to generate %s" % json_filename)
        for component in component_dict.keys():
            for key, version in component_dict[component].iteritems():
                if key == "component_env_version":
                    if "component" in json_filename:
                        json_env_string = '"env_version":{"current":"%s","new":"%s"}}' % (version[1], version[0])
                    else:
                        json_env_string = '"env_version":{"current":"%s","new":"%s"}}' % (version[0], version[0])
                if key == "component_version":
                    if "component" in json_filename:
                        json_component_string = '"%s":{"version":{"current":"%s","new":"%s"}' % (
                        component, version[1], version[0])
                    else:
                        json_component_string = '"%s":{"version":{"current":"%s","new":"%s"}' % (component, version[0],
                                                                                                 version[0])
            # This section sets the type to ACS if the component is found in the static mapping
            if component in acs.component.CMPS:
                if json_env_string is not None and json_component_string is not None:
                    json_string = '{%s,"type":"acs",%s}' % (json_component_string, json_env_string)
                else:
                    json_string = '{%s,"type":"acs"}' % json_component_string
            # If the component isn't apart of the ACS and doesn't have an env_version just output the component version
            else:
                if json_env_string is None:
                    json_string = '{%s}' % json_component_string
                    # Check if the file has already been created. If it does append to the file, if not do a write
                    # operation
                    # The file should only exist at this point if it has had current json data written to it
            if os.path.isfile(json_filename):
                write_file = open(json_filename, "a")
            else:
                write_file = open(json_filename, "w")
            write_file.write(json_string)
            write_file.write("\n")
            close_file = True
        if close_file:
            write_file.close()
            log.info("%s has been closed." % json_filename)


    rollback_file_name = output_directory + "rollback_version"
    component_diff_file = output_directory + "component_diff"
    # In order to write a proper diff, the component being deployed requires knowledge of the previous component
    for key in previous_component_dict.keys():
        for second_key in previous_component_dict[key].keys():
            component_being_deployed_dict[key][second_key].append(previous_component_dict[key][second_key][0])
    write_json_file(previous_component_dict, rollback_file_name)
    write_json_file(component_being_deployed_dict, component_diff_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='%s    Updates the environment file with new components/blueprints'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                     epilog='%s \nSample usage: %s --config-file conf/env/tec-qa.env.conf '
                                            ' --comp ahp-booking:1.2.259 --blueprint ahp-booking_env:tec-qa-sjc_2.0.1 '
                                            '\nor\n'
                                            '%s --config-file conf/env/tec-qa.env.conf  --comp ahp-booking:1.2.259 '
                                            '--artifactory --major_version ahp-booking_2.0 %s'
                                            % (textColours.HIGHLIGHT, sys.argv[0], sys.argv[0], textColours.ENDC),
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--comp', '-c', action='append', dest='component_name', help='A list of component labels'
                                                                                     ' associated with software loads',
                        required=True)
    parser.add_argument('--config-file', '-f', action='store', dest='config_file', help='The config file with all the '
                                                                                        'environment information',
                        required=True)
    parser.add_argument('--blueprint', '-b', action='append', dest='blue_print', help='')
    parser.add_argument('--artifactory', action='store_true', help='Attempt to retrieve build information from '
                                                                   'Artifactory (major version, blueprint version etc)')
    parser.add_argument('--major-version', action='append', help='The major version of a blueprint')
    parser.add_argument('--output-directory', action='store', help='Specify the directory where files will be written')
    options = parser.parse_args()

    # This dict stores the component and the previous version to track in case of rollback
    previous_component_version_dict = {}
    proposed_component_version_dict = {}
    if options.output_directory is not None:
        dump_files_here = options.output_directory
    else:
        dump_files_here = "./"
    if options.blue_print is not None:
        if "_env" not in options.blue_print[0]:
            log.error("Unexpected input for blueprint. Expected blueprint with _env")
            parser.print_help()
            sys.exit(1)
        list_of_components = options.component_name + options.blue_print
    else:
        list_of_components = options.component_name

    backup_location = "%s.backup" % options.config_file
    shutil.copyfile(options.config_file, backup_location)
    log.info("physical file backed up to: %s" % backup_location)

    env_file_section_to_find_env_name = 'environment'
    variable_name_of_environment_name = 'ENV_NAME'
    config = ConfigParser.RawConfigParser()
    config.optionxform = str  # make keys case sensitive
    config.read(options.config_file)
    try:
        environment_name = config.get(env_file_section_to_find_env_name, variable_name_of_environment_name)
    except ConfigParser.NoSectionError:
        log.error("%s was not found in %s. Cannot continue..." % (env_file_section_to_find_env_name,
                                                                  options.config_file))
        sys.exit(1)
    except ConfigParser.NoOptionError:
        log.error("%s was not found in section %s in the config file: %s\n"
                  "Cannot continue..." % (variable_name_of_environment_name, env_file_section_to_find_env_name,
                                          options.config_file))
        sys.exit(1)
    except:
        log.warning("Unhandled exception! Exiting...")
        sys.exit(1)

    script_input_check(options.component_name)
    if options.artifactory:
        if options.major_version is not None:
            if environment_name is not None:
                list_of_components = []
                components_with_blueprint_versions_dict = artifactory.ArtifactoryApi.return_all_objects_underneath_folder_with_specific_metadata(
                    'environment-blueprints')

                # Find the blueprint for a component and return the latest one for a given environment
                latest_blueprints_dict = artifactory.ArtifactoryApi.get_latest_version(environment_name,
                                                                                       components_with_blueprint_versions_dict,
                                                                                       options.major_version)
                # build the list of components to update based on information from artifactory
                # as well as information passed in as args to the script
                for component in options.component_name:
                    component_name = component.split(":")[0]
                    component_version = component.split(":")[1]
                    list_of_components.append("%s:%s" % (component_name, component_version))
                for component, blueprint in latest_blueprints_dict.items():
                    # The blueprint needs the _env added to the string to indicate it is a blueprint
                    list_of_components.append("%s_env:%s" % (component, blueprint))
        else:
            log.error("The major version is required to parse artifactory api results")
            parser.print_help()
            sys.exit(1)

    # The update_config method also generates the content for previous_component_version_dict and
    # proposed_component_version_dict. There is no harm writing the file before doing the version sanity check
    # because if there is an error condition the script aborts and the pipeline should /NOT/ push the file in failure
    # case
    update_config(list_of_components, config, options.config_file, previous_component_version_dict,
                  proposed_component_version_dict)

    for key in previous_component_version_dict.keys():
        if key in proposed_component_version_dict.keys():
            if previous_component_version_dict[key] == proposed_component_version_dict[key]:
                log.error("Detected the same versions of %s and %s_env... aborting as there is no change to "
                          "make\n" % (key, key))
                sys.exit(1)
    format_string_to_json(previous_component_version_dict, proposed_component_version_dict, dump_files_here)
