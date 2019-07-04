#!/usr/bin/python

# Owner: Steve Ovens <steve D0T ovens <AT> redhat -DOT- com>
# Date Created: July 2019
# Primary Function: This script takes a project as its required argument and then any of ImageStream, 
# DeploymentConfig BuildConfig, Service, Route, PersistentVolume, PersistentVolumeClaim, or ConfigMap
# and sanitize the export of these options. There is a lot of unneeded or unwanted metadata that 
# is removed by this script. The output is a yaml file that contains all the definitions required to 
# recreate your project from scratch (by using oc create -f /tmp/<template name>)


import os
import sys
import datetime
from optparse import OptionParser
import json
import yaml
import time

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
parser.add_option('--output-directory', '-o', dest="output_directory", help="The directory to output the template to")

(options, args) = parser.parse_args()

if not options.project_name:
    print("\nProject name is required\n")
    time.sleep(1)
    parser.print_help()
    sys.exit()

# Because the project has different metadata than the other objects we are not including them in the export list  
ose_resources_to_export_list = []

for opt, value in options.__dict__.items():
    if value == True:
        ose_resources_to_export_list.append(opt)

# Store the sys.stdout so that it is easy to restore later
old_stdout = sys.stdout

# Allow for the override of the output directory
if options.output_directory:
    template_output_path = options.output_directory
else:
    template_output_path = "/tmp/"

template_name = template_output_path + options.project_name + "_template_temp"
template_output = template_output_path + options.project_name + "_template.yaml" 
json_object_list = []
persistent_volume_list = []
script_run_date = datetime.datetime.now().strftime("%Y-%m-%d-%H_%M")

metadata_to_remove_list = ["creationTimestamp", "finalizers", "resourceVersion", "selfLink", "uid", "generation"]
###### End variable declaration


def remove_attribute_from_object(resource_name, section_heading, entry_to_remove, extra_section=None):
    """This method pops objects out of a dictionary in a try/except block 
    but swallows the errors because we don't care if we try to pop an object 
    that doesn't exist"""
    try:
        if extra_section:
            resource_name[section_heading][extra_section].pop(entry_to_remove)
        else:
            resource_name[section_heading].pop(entry_to_remove)
    except:
        pass

def get_oc_json_object(ocp_object, specific_resource_name=None):
    """This method should take an argument and return the json form"""
    # If you give a specific resource name, the export command requires an extra argument
    if specific_resource_name:
        # unlike other objects, --export is not available for projects
        if ocp_object == "project":
            json_object = json.loads(os.popen("oc get %s %s -o json" % (ocp_object, specific_resource_name)).read())
        else:
            json_object = json.loads(os.popen("oc get %s %s -o json --export" % (ocp_object, specific_resource_name)).read())
    else:
        json_object = json.loads(os.popen("oc get %s -o json --export" % (ocp_object)).read())
    return(json_object)


# Check for a previous template
if os.path.exists(template_output):
    os.rename(template_output, (template_output + "_" + script_run_date))

# Change to the correct project before attempting to export the resources
os.popen("/usr/bin/oc project %s" % options.project_name).read()

project_json_object = get_oc_json_object('project', specific_resource_name=options.project_name)
# get rid of excess data that just clutters the entries
project_json_object.pop('status')
project_json_object['spec'].pop('finalizers')
for metadata in metadata_to_remove_list:
    remove_attribute_from_object(resource_name=project_json_object, section_heading='metadata', entry_to_remove=metadata)

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
                
            remove_attribute_from_object(resource_name=individual_entry, section_heading='spec', entry_to_remove='revisionHistoryLimit')
            remove_attribute_from_object(resource_name=individual_entry, section_heading='spec', entry_to_remove='clusterIP')
            remove_attribute_from_object(resource_name=individual_entry, section_heading='metadata', extra_section='annotations', entry_to_remove='pv.kubernetes.io/bind-completed')
            for metadata in metadata_to_remove_list:
                remove_attribute_from_object(individual_entry, 'metadata', metadata)
        json_object_list.append(temp_holder)

if options.persistentvolume:
    for volume in persistent_volume_list:
        temp_holder = get_oc_json_object("persistentvolume", specific_resource_name=volume)
        temp_holder.pop('status')
        #remove_attribute_from_object(temp_holder, 'spec', 'resourceVersion')
        remove_attribute_from_object(resource_name=temp_holder, section_heading='spec', extra_section='claimRef', entry_to_remove='apiVersion')
        remove_attribute_from_object(resource_name=temp_holder, section_heading='spec', extra_section='claimRef', entry_to_remove='kind')
        remove_attribute_from_object(resource_name=temp_holder, section_heading='spec', extra_section='claimRef', entry_to_remove='resourceVersion')
        remove_attribute_from_object(resource_name=temp_holder, section_heading='spec', extra_section='claimRef', entry_to_remove='uid')
        for metadata in metadata_to_remove_list:
            remove_attribute_from_object(temp_holder, 'metadata', metadata)
        json_object_list.append(temp_holder)


sys.stdout = open(template_output, 'a')
print(yaml.safe_dump(project_json_object))
for item in json_object_list:
    print('---')
    print(yaml.safe_dump(item))

