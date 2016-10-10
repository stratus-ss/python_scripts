#!/usr/bin/env python
# Primary function: This script will check the deployment configs for successful deployment
# If a failure has occurred, it will link the deployment config to a specific pod.

import os
import sys
import json
import argparse

parser = argparse.ArgumentParser()

parser.add_argument('-c', action='store', dest='component_name', help='Pass in the list of component labels'
                    ' associated with deployment configs', required=True)
options = parser.parse_args()


def process_deployment_config_json(command):
    cmd_output = os.popen(command).read()
    json_data = json.loads(cmd_output)
    component_dict = {}
    for component in json_data['items']:
        component_name = str(component['metadata']['name'])
        component_label = "name=" + str(component['metadata']['labels']['name'])
        latest_version = int(component['status']['latestVersion'])
        component_dict[component_name] = [component_label, latest_version]
    return (component_dict)


def process_pod_json(command, incoming_dict):
    cmd_output = os.popen(command).read()
    json_data = json.loads(cmd_output)
    container_failed = False
    if json_data['items']:
        for component in json_data['items']:
            component_name = str(component['metadata']['name'])
            pod_id = str(component['status']['containerStatuses'][0]['containerID'].split("//")[1])
            for container in component['status']['containerStatuses']:
                if not container['ready']:
                    container_failed = True
            # The api can report that a pod is {ready: True} even if a container is down
            # Therefore, flag the pod as not ready
            if container_failed:
                incoming_dict[component_name] = {pod_id : False}
            else:
                incoming_dict[component_name] = {pod_id: True}
    else:
        # instead of reparsing output, just parse the command. Since this component is failing
        # the api has no information about the failed pod and thus no easy way to return this info
        missing_component = command.split("-l")[1].split("-o")[0].strip()
        incoming_dict[missing_component] = {None: False}

if __name__ == "__main__":
    pod_status_dict = {}
    deployment_config_label = "internal.acs.amadeus.com/component=%s" % options.component_name
    get_dc_command = "sudo oc get dc -l %s -o json" % deployment_config_label
    component_attributes = process_deployment_config_json(get_dc_command)
    for first_key in component_attributes.keys():
        get_pod_command = "sudo oc get pod -l %s -o json" % component_attributes[first_key][0]
        process_pod_json(get_pod_command, pod_status_dict)
    exit_with_error = False
    for key in pod_status_dict.keys():
        for value in pod_status_dict[key].values():
            if not value:
                if "name" in key:
                    print("This component did not deploy at all:      \t%s" % key)
                else:
                    print("This component has container(s) not ready: \t%s" % key)
                exit_with_error = True
    if exit_with_error:
        sys.exit(1)