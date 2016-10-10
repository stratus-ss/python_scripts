#!/usr/bin/python
# Date Created: Sept 2016
# Primary Function: This script will examine a pod to extract which node it is on. With this info
# it logs into the node and uses the docker tools to extract various pieces of information as well
# as the docker logs if a container is in a failed state
# Dependencies: nothing outside of the python stdlibs

import os
import argparse
import sys

# in tec-qa at least there is no paramiko installed on the master.
# If this changes in the future remote connections can be redone with paramiko
try:
    import paramiko
    ssh_method = "paramiko"
except ImportError:
    print("Paramiko not available, falling back to openssh")
    ssh_method = "ssh"

parser = argparse.ArgumentParser()
parser.add_argument('--pod-name', action='store', dest='pod_name', help='Specify the pod name which has the containers '
                                                                        'you wish to inspect')
parser.add_argument('--exposed-port', action="store_true", dest='exposed_port', help='Specify the port which to find inside '
                                                                'the docker inspect command', default=False)
parser.add_argument('--container-start',  action='store_true', dest='container_start_time',
                    help='Retrieve the container start time', default=False)
parser.add_argument('--restart-count', dest='container_restart_count', help='Retrieve the number of container restarts',
                    action='store_true', default=False)
parser.add_argument('--container-running', dest='container_running', action='store_true', default=False,
                    help='Retrieve whether or not the container is running')
parser.add_argument('--oom', dest='oom_killed', help='Retrieve the number of times a container has been killed by OOM',
                    action='store_true', default=False)
options = parser.parse_args()

# If the pod name is not given, exit the program gracefully; all other arguments are optional
if options.pod_name is None:
    print("No pod name was specified. This is required")
    parser.print_help()
    sys.exit()


class textColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    HIGHLIGHT = '\033[96m'


oc_describe = os.popen("sudo oc describe pod %s" % options.pod_name).read()
ssh_command = ""

ports_exposed = []
docker_information = {}
list_of_options_to_print = []
container_dict = {}

# By default, don't attempt to find a reason for the state of a container
find_reason = False


def add_to_dictionary(dictionary, image_name, container_identification, value):
    """Add items to a dictionary. The items will be stored in a multidimensional array
    {image_name: {container id : [list of values]}"""
    if image_name in dictionary:
        dictionary[container_identification][image_name].append(value)
    else:
        dictionary[container_identification] = {image_name: [value]}


def process_ssh_output(output):
    """Used to parse the output of ssh. Because paramiko is not in the stdlib, this function processes the
    output returned from running commands over ssh. Returns list of ports exposed to docker, whether or not
    the container is running, the point in time the container was started, and how many times the OOM killer
    has been activated on a container."""
    list_of_ports = []
    exposed_ports_start = False
    for ssh_lines in output.split("\n"):
        # All values split the same way so its more efficient to put it in a variable
        if ": " in ssh_lines:
            ssh_line_value = ssh_lines.split(": ")[1].replace(",", "")
        if '"Running":' in ssh_lines:
            if "true" in ssh_line_value:
                container_running = True
            else:
                container_running = False
        if '"StartedAt":' in ssh_lines:
            container_start_at_time = ssh_line_value
        if '"OOMKilled":' in ssh_lines:
            oomkilled = ssh_line_value
        if '"ExposedPorts": {' in ssh_lines:
            exposed_ports_start = True
        elif '},' in ssh_lines and not '{' in ssh_lines:
            exposed_ports_start = False
        elif exposed_ports_start:
            list_of_ports.append(ssh_lines.split(":")[0].strip())
    return(list_of_ports, container_running, container_start_at_time, oomkilled)


def format_output(text_to_print):
    """format_output is used to make sure that all output is lined up in a readable fashion. It does this
    by figuring out which line has the most characters in it and then padding the other lines with whitespaces
    to make all lengths equal."""
    longest_line = 0
    # All lines except the image ID should be indented
    indent = True
    for line in text_to_print:
        heading = line.split(": ")[0] + ":"
        if len(heading) > longest_line:
            longest_line = len(heading)
    for line_second_pass in text_to_print:
        value = line_second_pass.split(": ")[1]
        heading = line_second_pass.split(": ")[0] + ":"
        while len(heading) < longest_line:
            heading += " "
        if "Image ID" in line_second_pass:
            colour = textColors.OKBLUE
            indent = False
        if "Container restarts" in line_second_pass:
            if value != 0:
                colour = textColors.WARNING
        if "Container running" in line_second_pass:
            if value:
                colour = textColors.OKGREEN
            else:
                print(textColors.FAIL),
        if indent:
            print("    " + colour + heading + "\t" + value + textColors.ENDC)
        else:
            print(colour + heading + "\t\t" + value + textColors.ENDC)
        colour = textColors.ENDC
        indent = True

for line in oc_describe.split("\n"):
    if line.startswith("Node:"):
        node_name = line.split()[1].split("/")[0]
        print("Beginning docker inspect on remote node: %s\n" % node_name)
    elif line.startswith("    State:"):
        state_of_container = line.split("State:")[1]
        if not "Running" in state_of_container:
            # Attempt to parse the reason why a container is not currently running
            find_reason = True
            # If a container is not running, skip to the next line and parse the reason
            pass
    elif line.startswith("      Reason:"):
        if find_reason:
            reason_container_is_not_running = line.split("Reason:")[1].strip()
            add_to_dictionary(docker_information, docker_container_id, docker_image, reason_container_is_not_running)
    elif line.startswith("    Image:"):
        docker_image = line.split("Image:")[1].strip().split("@")[0]
        add_to_dictionary(docker_information, docker_container_id, docker_image, port_list)
    elif line.startswith("    Container ID:"):
        docker_container_id = line.split("//")[1]
        ssh_command = "sudo docker inspect %s; " % docker_container_id
        ssh_output = os.popen("ssh -o StrictHostKeyChecking=no -t %s '%s' 2> /dev/null" % (node_name, ssh_command)).read()
        if ssh_output == "":
            print("Could not connect to host, check the ssh key")
            sys.exit()
        port_list, container_is_running, container_start_time, oom_killed = process_ssh_output(ssh_output)
    elif line.startswith("    Restart"):
        pod_restart_count = line.split("Count:")[1].strip()
        container_dict[docker_container_id] = [port_list, container_is_running, container_start_time, oom_killed,
                                               pod_restart_count]

# This section compiles a list of things to print based on the arguments the user passed in
for key in docker_information.keys():
    container_id = docker_information[key].keys()[0]
    image_id = key
    open_ports = docker_information[image_id][container_id][0]
    list_of_options_to_print.append("\nImage ID: %s" % image_id)
    list_of_options_to_print.append("Container: %s" % container_id)
    if options.exposed_port:
        list_of_options_to_print.append("Exposed ports: %s" % open_ports)
    if options.container_start_time:
        list_of_options_to_print.append("Container start time: %s" % container_dict[container_id][2])
    if options.container_restart_count:
        list_of_options_to_print.append("Container restarts: %s" % container_dict[container_id][4])
    if options.container_running:
        list_of_options_to_print.append("Container running: %s" % container_dict[container_id][1])
        # The length of the list stored in docker_information will be greater than 1 if
        # a container was not running and a reason could be found
        if len(docker_information[image_id][container_id]) > 1:
            failed_container_reason = docker_information[image_id][container_id][1]
            list_of_options_to_print.append("Container is down because: %s" % failed_container_reason)
        # If a container is not running, retrieve the docker logs
        if not container_dict[container_id][1]:
            command = "sudo docker logs %s" % container_id
            # because we are not holding the connection open with paramiko, we need to establish another
            # ssh connection
            ssh_running_output = os.popen("ssh -o StrictHostKeyChecking=no -t %s '%s' 2> /dev/null" %
                                          (node_name, command)).read()
            list_of_options_to_print.append("Docker log output: %s" % ssh_running_output)
    if options.oom_killed:
        list_of_options_to_print.append("Container OOM killed: %s" % container_dict[container_id][3])

format_output(list_of_options_to_print)
