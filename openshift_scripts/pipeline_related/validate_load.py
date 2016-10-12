#!/usr/bin/env python
# Primary function: This script will check the deployment configs for successful deployment
# If a failure has occurred, it will link the deployment config to a specific pod.

import os
import sys
import json
import argparse
from tools.common import textColours
from tools import ssh, common
import openshift.cluster

parser = argparse.ArgumentParser(description='%s    Updates the environment file with new components/blueprints'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                 epilog='%s \nSample usage: %s --env-file conf/env/tec-qa.env.conf '
                                        ' --comp ahp-booking \n%s' % (textColours.HIGHLIGHT, sys.argv[0],
                                                                              textColours.ENDC),
                                 formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('--comp', '-c', action='store', dest='component_name', help='Pass in the list of component labels'
                    ' associated with deployment configs', required=True)
parser.add_argument('--env-file', '-f', action='store', dest='config_file',
                    help='The config file for the environment', required=True)

options = parser.parse_args()


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


def process_pod_json(command, status_dict, version_dict, component_label, incoming_session):
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
            pod_id = str(component['status']['containerStatuses'][0]['containerID'].split("//")[1])
            for container in component['status']['containerStatuses']:
                if not container['ready']:
                    container_failed = True
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

if __name__ == "__main__":
    pod_status_dict = {}
    deployment_version_dict = {}

    deployment_config_label = "internal.acs.amadeus.com/component=%s" % options.component_name
    get_dc_command = "sudo oc get dc -l %s -o json" % deployment_config_label

    # This is the file which will have the deployer name in it if there is a failure
    filename = "/tmp/deployer_name"
    # Attempt to remove the file from a previous run to ensure the file is always empty
    try:
        os.remove(filename)
    except OSError:
        pass

    # Setup the ssh connections
    os.environ['ENV_FILE'] = options.config_file
    user = common.get_stack_user()
    gateway_ip = common.get_gateway_ip()
    env_options = common.get_env_options()
    gateway_session = ssh.SSHSession(gateway_ip, user)
    os_master_session = openshift.cluster.get_master_session(gateway_session, options.component_name)

    component_attributes = process_deployment_config_json(get_dc_command, os_master_session)

    for first_key in component_attributes.keys():
        for pod_label in component_attributes[first_key].keys():
            get_pod_command = "sudo oc get pod -l %s -o json" % pod_label
            process_pod_json(get_pod_command, pod_status_dict, deployment_version_dict, pod_label, os_master_session)
    exit_with_error = False

    # compare the dc latest version to component latest version
    for first_key in deployment_version_dict.keys():
        for second_key, value in deployment_version_dict[first_key].iteritems():
            if component_attributes[first_key][second_key] != deployment_version_dict[first_key][second_key]:
                # If there is a problem, store the data with the component name, in the same way that it is stored
                # if there are no pods running. i.e. name=component. This allows consistent error handling
                pod_status_dict.pop(first_key)
                pod_status_dict[second_key] = {first_key: False}

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
                        deployer_name = deployer_json_data['items'][0]['metadata']['name']
                        write_file = open(filename, "a")
                        write_file.write(deployer_name)
                        write_file.write("\n")
                else:
                    sys.stderr.write("%sThis component has container(s) not ready: \t%s\n" % (textColours.FAIL, key))
                exit_with_error = True
    write_file.close()
    if exit_with_error:
        sys.exit(1)
