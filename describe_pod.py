#!/usr/bin/python
import os
import argparse
import sys

# in tec-qa at least there is no paramiko installed on the master.
# If this changes in the future this can be redone
try:
    import paramiko
    ssh_method = "paramiko"
except ImportError:
    print("Paramiko not available, falling back to openssh")
    ssh_method = "ssh"

parser = argparse.ArgumentParser()
parser.add_argument('--pod-name', action='store', dest='pod_name', help='Specify the pod name which has the containers '
                                                                        'you wish to inspect')
parser.add_argument('--port', action="store", dest='port', help='Specify the port which to find inside '
                                                                'the docker inspect command', type=int)
parser.add_argument('--exposed-port', action="store_true", dest='exposed_port', help='Specify the port which to find inside '
                                                                'the docker inspect command', default=False)
parser.add_argument('--container-start',  action='store_true', dest='container_start_time',
                    help='Retrieve the container start time', default=False)
parser.add_argument('--restart-count', dest='container_restart_count', help='Retrieve the number of container restarts',
                    action='store_true', default=False)
parser.add_argument('--pod-readiness', dest='pod_readiness', help='Retrieve whether or not the pod is ready',
                    action='store_true', default=False)
parser.add_argument('--container-running', dest='container_running', action='store_true', default=False,
                    help='Retrieve whether or not the container is running')
parser.add_argument('--oom', dest='oom_killed', help='Retrieve the number of times a container has been killed by OOM',
                    action='store_true', default=False)
options = parser.parse_args()

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
        # All values split the same way so its more efficient to put it in a variable
        ssh_line_value = ssh_lines.split(": ")[1].replace(",", "")
        if '"Running":' in ssh_lines:
            container_running = ssh_line_value
        if '"StartedAt":' in ssh_lines:
            container_start_time = ssh_line_value
        if '"OOMKilled":' in ssh_lines:
            oomkilled = ssh_line_value
        if '"RestartCount:"' in ssh_lines:
            restart_count = ssh_line_value
        if '"ExposedPorts": {' in ssh_lines:
            exposed_ports_start = True
        elif '},' in ssh_lines and not '{' in ssh_lines:
            exposed_ports_start = False
        elif exposed_ports_start:
            list_of_ports.append(ssh_lines.split(":")[0].strip())
    return(list_of_ports, container_running, container_start_time, oomkilled, restart_count)


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
        port_list, container_is_running, container_start_time, oom_killed, restart_counter = process_ssh_output(ssh_output)

for key in docker_information.keys():
    container_id = docker_information[key].keys()[0]
    image_id = key
    open_ports = docker_information[image_id][container_id]
    print("Image ID: %s" % image_id)
    print("Container: %s" % container_id)
    if options.exposed_port:
        print("Exposed ports: %s" % open_ports)
    if options.container_start_time:
        print("Container start time: %s" % container_start_time)
    if options.container_restart_count:
        print("Container restarts: %s" % restart_counter)
    if options.container_running:
        print("Container status: %s" % container_is_running)
    if options.oom_killed:
        print("Container OOM killed: %s" % oom_killed)
    print("\n")
