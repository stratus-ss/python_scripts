#!/usr/bin/env python
# Primary function: This script will check the deployment configs for successful deployment
# If a failure has occurred, it will link the deployment config to a specific pod.

import os
import json


def add_to_dictionary(dictionary, image_name, container_identification, value):
    """Add items to a dictionary. The items will be stored in a multidimensional array
    {image_name: {container id : [list of values]}"""
    if image_name in dictionary:
        dictionary[container_identification][image_name].append(value)
    else:
        dictionary[container_identification] = {image_name: [value]}


def examin_dcs(deployment_name):
    command = "sudo oc describe dc %s" % deployment_name
    output = os.popen(command).read()
    component_label = None
    start_parsing = False
    for line in output.split("\n"):
        if "(latest)" in line and "Deployment" in line:
            start_parsing = True
        if "Replicas:" in line:
            start_parsing = False
        if start_parsing:
            if "Status:" in line:
                if line.split(":")[1].strip() == "Complete":
                    successful_deployment = True
                else:
                    successful_deployment = False
        if line.startswith("  Selector:"):
            component_label = line.split(":")[1].strip()
    if successful_deployment:
        print("Latest deploment has succeeded")
        return(None)
    else:
        return(component_label)

pod_status_dict = {}

for deployment_config_name in open("report-dc").readlines():
    pod_label = examin_dcs(deployment_config_name)
    if pod_label is not None:
        json_data = json.loads(os.popen("sudo oc get pod -l %s -o json" % pod_label).read())
        for pod in json_data['items'][0]['status']['containerStatuses']:
            pod_id = pod['containerID'].split("//")[1]
            pod_status = pod['ready']
            component_name = pod['name']
            add_to_dictionary(pod_status_dict, component_name, pod_id, pod_status)

print(pod_status_dict)

