#!/usr/bin/python
import os
from optparse import OptionParser
import sys

# in tec-qa at least there is no paramiko installed on the master.
# If this changes in the future this can be redone
try:
    import paramiko
    ssh_method = "paramiko"
except ImportError:
    print("Paramiko not available, falling back to openssh")
    ssh_method = "ssh"

parser = OptionParser()
parser.add_option('-n', '--pod-name', dest='pod_name', help='Specify the pod name which has the containers ' \
                                                      'you wish to inspect')
parser.add_option('-p', '--port', dest='port', help='Specify the port which to find inside the docker inspect command')
(options, args) = parser.parse_args()

# If the pod name is not given, exit the program gracefully
if options.pod_name is None:
    print("No pod name was specified. This is required")
    parser.print_help()
    sys.exit()

oc_describe = os.popen("sudo oc describe pod %s" % options.pod_name).read()
ssh_command = ""

ports_exposed = []
docker_information = {}


def add_to_dictionary(dictionary, image_name, container_id, port_list):
    if image_name in dictionary:
        dictionary[image_name][container_id] = port_list
    else:
        dictionary[image_name] = {container_id: port_list}


def process_ssh_output(output):
    list_of_ports = []
    exposed_ports_start = False
    for ssh_lines in output.split("\n"):
        if '"ExposedPorts": {' in ssh_lines:
            exposed_ports_start = True
        elif '},' in ssh_lines and not '{' in ssh_lines:
            exposed_ports_start = False
        elif exposed_ports_start:
            list_of_ports.append(ssh_lines.split(":")[0].strip())
    return(list_of_ports)


for line in oc_describe.split("\n"):
    if line.startswith("Node:"):
        node_name = line.split()[1].split("/")[0]
        print("Beginning docker inspect on remote node: %s" % node_name)
    elif line.startswith("    Image:"):
        docker_image = line.split(":")[1].strip()
        add_to_dictionary(docker_information, docker_image, docker_container_id, port_list)
    elif line.startswith("    Container ID:"):
        docker_container_id = line.split("//")[1]
        if options.port is None:
            ssh_command = "sudo docker inspect %s; " % docker_container_id
        else:
            ssh_command = "sudo docker inspect %s |grep %s; " % (docker_container_id, options.port)
        ssh_output = os.popen("ssh -t %s '%s' 2> /dev/null" % (node_name, ssh_command)).read()
        port_list = process_ssh_output(ssh_output)

for key in docker_information.keys():
    container_id = docker_information[key].keys()[0]
    image_id = key
    open_ports = docker_information[image_id][container_id]
    print("Image ID: %s" % image_id)
    print("Container: %s" % container_id)
    print("Exposed ports: %s" % open_ports)
    print("\n")


"""
start of container
restart count of container
running of container
OOMKilled of container

ready of the pod
"""
