#!/usr/bin/env python
# Primary function: This script will check the deployment configs for successful deployment
# If a failure has occurred, it will link the deployment config to a specific pod.

import os
import json


def examine_deployment_configs(deployment_name):
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
        # Look for the first occurance of Selector and pull out the name=<comp> to match with the pod
        if "Selector:" in line:
            if component_label is None:
                component_label = line.split(":")[1].strip()
    if successful_deployment:
        print("Latest deploment has succeeded")
        return(component_label)
    else:
        return(component_label)

pod_status_dict = {}

for deployment_config_name in open("report-dc").readlines():
    pod_label = examine_deployment_configs(deployment_config_name)
    if pod_label is not None:
        json_data = json.loads(os.popen("sudo oc get pod -l %s -o json" % pod_label).read())
        for pod in json_data['items'][0]['status']['containerStatuses']:
            pod_id = str(pod['containerID'].split("//")[1])
            pod_status = pod['ready']
            component_name = str(pod['name'])
            pod_status_dict[component_name] = {pod_id : pod_status }

for first_key in pod_status_dict.keys():
    for second_key, value in pod_status_dict[first_key].keys():
        if second_key:
            print(second_key)
