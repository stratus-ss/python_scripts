#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: May 2016
# Modified: June 1, 2016
# Primary Function:


import os
import sys
import datetime
from optparse import OptionParser
import json
import yaml

parser = OptionParser()
parser.add_option('--project-name', '-p', dest = 'project_name',
                      help = 'Specify the project export to yaml')
parser.add_option('--imagestream', '-i', dest = 'imagestream', help="Include ImageStream in the export", action='store_true')
parser.add_option('--deploymentconfig', '-d', dest = 'deploymentconfig', help="Include DeploymentConfig in the export", action='store_true')
parser.add_option('--buildconfig', '-b', dest = 'buildconfig', help="Include BuildConfig in the export", action='store_true')
parser.add_option('--service', '-s', dest = 'service', help="Include Service in the export", action='store_true')
parser.add_option('--route', '-r',  dest = 'route', help="Include Route in the export", action='store_true')
parser.add_option('--persistentvolume', '-v',  dest = 'persistentvolume', help="Include PersistentVolume in the export", action='store_true')
parser.add_option('--persistentvolumeclaim', '-c',  dest = 'persistentvolumeclaim', help="Include PersistentVolumeClaim in the export", action='store_true')
parser.add_option('--configmap', '-m',  dest = 'configmap', help="Include ConfigMap in the export", action='store_true')

(options, args) = parser.parse_args()


ose_resources_to_export_list = []
for opt, value in options.__dict__.items():
  if value == True:
      ose_resources_to_export_list.append(opt)


# Store the sys.stdout so that it is easy to restore later
old_stdout = sys.stdout

template_output_path = "/tmp/"
template_name = template_output_path + options.project_name + "_template_temp"
template_output = template_output_path + options.project_name + "_template.yaml" 
json_object_list = []
persistent_volume_list = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")

metadata_to_remove_list = ["creationTimestamp", "finalizers", "resourceVersion", "selfLink", "uid", "generation"]
# ose_resources_to_export_list = ["deploymentconfig", "persistentvolume", "persistentvolumeclaim"]
###### End variable declaration


def get_oc_json_object(ocp_object, specific_resource_name=None):
    """This method should take an argument and return the json form"""
    if specific_resource_name:
        json_object = json.loads(os.popen("oc get %s %s -o json --export" % (ocp_object, specific_resource_name)).read())
    else:
        json_object = json.loads(os.popen("oc get %s -o json --export" % (ocp_object)).read())
    return(json_object)


# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % options.project_name).read()


# build the initial json object list so that we can purge parts we dont want
for resource in ose_resources_to_export_list:
    if resource == "persistentvolume":
        pass
    else:
        temp_holder = get_oc_json_object(resource)      
        for individual_entry in temp_holder["items"]:
            # get rid of the status information as it is not needed
            individual_entry.pop("status")
            # We want to extract the volume name from the claim in order to back it up
            if resource == "persistentvolumeclaim":
                volume_name = individual_entry['spec']['volumeName']
                persistent_volume_list.append(volume_name)
            try:
                individual_entry['spec'].pop('revisionHistoryLimit')
            except:
                pass
            for metadata in metadata_to_remove_list:
                try:
                    individual_entry['metadata'].pop(metadata)
                except:
                    pass
        json_object_list.append(temp_holder)

if options.persistentvolume:
    for volume in persistent_volume_list:
        temp_holder = get_oc_json_object("persistentvolume", specific_resource_name=volume)
        temp_holder.pop('status')
        temp_holder['spec']['claimRef'].pop('resourceVersion')
        temp_holder['spec']['claimRef'].pop('uid')
        for metadata in metadata_to_remove_list:
            try:
                temp_holder['metadata'].pop(metadata)
            except:
                pass
        
        json_object_list.append(temp_holder)

for item in json_object_list:
    sys.stdout = open(template_output, 'a')
    print(yaml.safe_dump(item))
    print('---')

