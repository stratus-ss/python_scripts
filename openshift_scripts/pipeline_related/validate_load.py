#!/usr/bin/env python
# Primary function: This script will check the deployment configs for successful deployment
# If a failure has occurred, it will link the deployment config to a specific pod.

import os
import sys
import json
import argparse
from tools.common import textColours
from tools import ssh, common, log
import openshift.cluster
import acs.component


def process_deployment_config_json(remote_command, incoming_session):
    command_output = incoming_session.get_cmd_output(remote_command)
    json_data = json.loads(command_output)
    component_dict = {}
    for component in json_data['items']:
        component_name = str(component['metadata']['name'])
        component_label = "name=" + str(component['metadata']['labels']['name'])
        latest_version = int(component['status']['latestVersion'])
        component_dict[component_name] = {component_label: latest_version}
    return (component_dict)


def process_pod_json(command, status_dict, version_dict, component_label, incoming_session, container_dict):
    cmd_output = incoming_session.get_cmd_output(command)
    json_data = json.loads(cmd_output)
    container_failed = False
    if json_data['items']:
        for component in json_data['items']:
            component_name = str(component['metadata']['name'])
            # Because of reliable naming convention, you can split on the '-' and extract the deployment
            # config name so that data is stored with the same key as the deployment config dict
            deployment_name = "-".join(component_name.split("-")[:-2])
            deployment_number = int(component['metadata']['annotations']
                                     ['openshift.io/deployment-config.latest-version'])
            try:
                component['status']['containerStatuses']
                docker_image_name = str(component['status']['containerStatuses'][0]['image'])
                container_name = str(component['status']['containerStatuses'][0]['name'])
                for container in component['status']['containerStatuses']:
                    if not container['ready']:
                        container_failed = True
                        container_dict[container_name] = docker_image_name
            except KeyError:
                log.debug("%s has a state of %s" % (component['metadata']['name'], component['status']['phase']))
                pass
            # The api can report that a pod is {ready: True} even if a container is down
            # Therefore, flag the pod as not ready
            if container_failed:
                status_dict[deployment_name] = {component_name : False}
            else:
                status_dict[deployment_name] = {component_name: True}

            version_dict[deployment_name] = {component_label: deployment_number}
    else:
        # instead of reparsing output, just parse the command. Since this component is failing
        # the api has no information about the failed pod and thus no easy way to return this info
        missing_component = command.split("-l")[1].split("-o")[0].strip()
        status_dict[missing_component] = {None: False}


def inspect_load_state(component_to_inspect):
    deployment_config_label = "internal.acs.amadeus.com/component=%s" % component_to_inspect
    get_dc_command = "sudo oc get dc -l %s -o json" % deployment_config_label
    close_file = False
    # This is the file which will have the deployer name in it if there is a failure
    filename = "/tmp/deployer_cleanup"
    # Attempt to remove the file from a previous run to ensure the file is always empty
    try:
        os.remove(filename)
    except OSError:
        pass

    # Need to check the component against acs.component.CMPS[cmp_name]['cluster']
    # All of the component types are statically set in component.py
    try:
        acs.component.CMPS[component_to_inspect]
    except KeyError:
        print("Component is not part of the ACS category. Aborting the validation process")
        sys.exit(0)

    os_master_session = openshift.cluster.get_master_session(gateway_session, component_to_inspect)

    component_attributes = process_deployment_config_json(get_dc_command, os_master_session)

    for first_key in component_attributes.keys():
        for pod_label in component_attributes[first_key].keys():
            get_pod_command = "sudo oc get pod -l %s -o json" % pod_label
            process_pod_json(get_pod_command, pod_status_dict, deployment_version_dict, pod_label, os_master_session,
                             container_status_dict)
    exit_with_error = False

    # compare the dc latest version to component latest version
    for first_key in deployment_version_dict.keys():
        for second_key, value in deployment_version_dict[first_key].iteritems():
            if component_attributes[first_key][second_key] != deployment_version_dict[first_key][second_key]:
                # If there is a problem, store the data with the component name, in the same way that it is stored
                # if there are no pods running. i.e. name=component. This allows consistent error handling
                # Swap the first_key and second_key to normalize the data in the dict
                pod_status_dict.pop(first_key)
                pod_status_dict[second_key] = {first_key: False}
                # At this point the dict looks like:
                # pod_status_dict['name=ahp-report-audit-dmn'] = {'report-audit-dmn-deployment': False}

    for key in pod_status_dict.keys():
        for second_key, value in pod_status_dict[key].iteritems():
            if not value:
                if "name" in key:
                    sys.stderr.write("%sThis component did not deploy at all:      \t%s\n" % (textColours.FAIL, key))
                    # name=component will be in the key if there was a problem
                    # The second key will be empty if the problem was that the pod did not exist. Usually when a pod
                    # no longer exists, there is no longer a deployer pod kicking around.
                    # This will get the name of the deployer pod and write it to a file for cleanup before
                    # failing back to the previous build
                    if second_key is not None:
                        command = "sudo oc get pod -l openshift.io/deployer-pod-for.name=%s-%s -o json" % \
                                  (second_key, component_attributes[second_key][key])
                        cmd_output = os_master_session.get_cmd_output(command)
                        deployer_json_data = json.loads(cmd_output)
                        try:
                            deployer_name = deployer_json_data['items'][0]['metadata']['name']
                            deployer_and_component = component_to_inspect + " : " + deployer_name
                            write_file = open(filename, "a")
                            write_file.write(deployer_and_component)
                            write_file.write("\n")
                            close_file = True
                        except IndexError:
                            write_error_file = open("/tmp/nothing_to_clean", "w")
                            write_error_file.write("%s has no deployer pod left behind" % second_key)
                            write_error_file.close()
                            sys.stderr.write("%sThere was a failure during deployment but no deployer pods found "
                                             "to clean up" % textColours.FAIL)
                            sys.exit(2)
                else:
                    sys.stderr.write("%sThis component has container(s) not ready: \t%s\n" % (textColours.FAIL, key))
                    sys.stderr.write("\nContainer infomration from failure:\n")
                    for container in container_status_dict.keys():
                        sys.stderr.write("\tDocker image name: %s\n" % (container_status_dict[container]))
                        sys.stderr.write("\tContainer name: %s\n" % container)

                exit_with_error = True
    if close_file:
        write_file.close()
    return(exit_with_error)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='%s    Validates that all containers in a pod are up as well as '
                                                 'ensuring that all pods are on the correct deployment version.'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                     epilog='%s \nSample usage: %s --env-file conf/env/tec-qa.env.conf '
                                            ' --comp ahp-booking \n%s' % (textColours.HIGHLIGHT, sys.argv[0],
                                                                          textColours.ENDC),
                                     formatter_class=argparse.RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    parser.add_argument('--env-file', '-f', action='store', dest='config_file',
                        help='The config file for the environment', required=True)

    group.add_argument('--comp', '-c', action='store', dest='component_name',
                        help='Pass in the list of component labels'
                             ' associated with deployment configs')

    group.add_argument('--diff-file', '-d', action='store', dest='diff_file',
                        help='A diff file generated by env_file.py')
    options = parser.parse_args()

    # Setup the ssh connections
    os.environ['ENV_FILE'] = options.config_file
    user = common.get_stack_user()
    gateway_ip = common.get_gateway_ip()
    env_options = common.get_env_options()
    gateway_session = ssh.SSHSession(gateway_ip, user)
    error_encountered = []
    if options.diff_file:
        diff_file_data = open(options.diff_file).read()
        for component in json.loads(diff_file_data):
            pod_status_dict = {}
            deployment_version_dict = {}
            container_status_dict = {}
            error_encountered.append(inspect_load_state(component))

    if options.component_name:
        pod_status_dict = {}
        deployment_version_dict = {}
        container_status_dict = {}
        error_encountered.append(inspect_load_state(options.component_name))

    for exits in error_encountered:
        if exits == True:
            number_of_errors = error_encountered.count(True)
            sys.stderr.write("\n%s%s components had errors during this validation check\n" % (textColours.FAIL,
                                                                                              number_of_errors))
            sys.exit(1)