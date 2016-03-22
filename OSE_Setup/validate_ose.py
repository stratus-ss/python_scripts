#!/usr/bin/env python2

import socket
import subprocess
from helper_functions import ImportHelper
from ssh_connection_handling import HandleSSHConnections
ImportHelper.import_error_handling("paramiko", globals())
import hashlib

docker_file_dict = {}
forward_lookup_dict = {}
reverse_lookup_dict = {}
repo_dict = {}
ssh_connection = HandleSSHConnections()


def add_to_dictionary(dictionary, name_of_server, component, value):
    if name_of_server in dictionary:
        dictionary[name_of_server][component] = value
    else:
        dictionary[name_of_server] = {component:value}


def process_host_file(ansible_host_file):
    # This section should parse the ansible host file for hosts
    # This doesn't work as it stands because it will suck in variables from the OSE install as well
    # Need a better way to parse the config file

    hosts_list = []
    for line in open(ansible_host_file).readlines():
        if line.startswith("["):
            pass
        else:
            host = line.split()[0]
            hosts_list.append(host)


def test_ssh_keys(host, user):
    """
    test_ssh_keys simply attempts to open an ssh connection to the host
    returns True if the connection throws a Paramiko exception
    """
    try:
        ssh_connection.open_ssh(host, user)
        ssh_connection.close_ssh()
        ssh_connection_failed = False
    except paramiko.ssh_exception.AuthenticationException:
        ssh_connection_failed = True

    return(ssh_connection_failed)


def check_forward_dns_lookup(host_name):
    """
    uses socket to do a forward lookup on host
    returns lookup_passed (True|False) and the host_ip
    """
    try:
        host_ip = socket.gethostbyname(host_name)
        lookup_passwed = True
    except socket.gaierror:
        try:
            socket.inet_aton(host_name)
            print("You should be using FQDN instead of IPs in your ansible host file!")
            pass
        except socket.error:
            pass
        lookup_passed = False
        host_ip = ""

    return(lookup_passed, host_ip)


def check_reverse_dns_lookup(lookup_dict):
    """
    uses socket to do a reverse lookup on hosts in forward_lookup_dict
    returns lookup_passed (True|False) and the hostname
    """
    for hostname in lookup_dict.keys():
        host_ip = lookup_dict[hostname]["ip"]
        try:
            hostname = socket.gethostbyaddr(host_ip)
            lookup_passed = True
        except socket.herror:
            lookup_passed = False
            hostname = ""

    return(lookup_passed, hostname)


def check_docker_files(host, ssh_user):
    """
    check_docker_files assumes there is already a paramiko connection made to the server in question
    """
    file_list = ["/etc/sysconfig/docker", "/etc/sysconfig/docker-storage", "/ect/sysconfig/docker-storage-setup"]
    for files in file_list:
        try:
            ssh_connection.open_ssh(host, ssh_user)
            stdin, stdout, stderr = ssh_connection.ssh.exec_command("sha256sum %s" % files)
            for line in stdout.channel.recv(1024).split("\n"):
                if line.strip():
                    add_to_dictionary(docker_file_dict, host, files, line.split()[0])
        except socket.error:
            print("No SSH connection is open")


def get_systemctl_output():
    systemctl_output = subprocess.Popen(["systemctl", "status", "docker"], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE).stdout.read()
    return(systemctl_output)


def is_docker_running(output):
    """
    is_docker_running checks whether docker is active. Returns true if its active
    false if not.
    """
    docker_running = False
    for line in output.split("\n"):
        if "Active:" in line:
            if "active" in line:
                docker_running = True
                active_since = line
    if docker_running:
        print("Docker is active")
        print(active_since)
    else:
        print("Docker is not running: \n")
        print(output)
    return(docker_running)


def is_docker_enabled(output):
    """
    is_docker_enabled checks to see if docker is enabled in systemd. Returns true if enabled
    false if not
    """
    for line in output.split("\n"):
        if "Loaded: " in line:
            if "enabled" in line.split("vendor preset")[0]:
                docker_enabled = True
            else:
                docker_enabled = False
    if docker_enabled:
        print("Docker is enabled")
    else:
        print("Docker is currently disabled")
    return(docker_enabled)


def is_host_subscribed():
    """
    is_host_subscribed uses subprocess to run the subscription-manager command.
    It parses the output for the word 'Current' if found, returns true, otherwise returns false

    """
    subscription_manager_output = subprocess.Popen(["subscription-manager", "status"], stoud=subprocess.PIPE,
                                                   stderr=subprocess.PIPE).stdout.read()
    for line in subscription_manager_output.split("\n"):
        if "Overall" in line:
            if "Current" in line:
                host_is_subscribed = True
            else:
                host_is_subscribed False
    if host_is_subscribed:
        print("Host subscription is Current")
    else:
        print("Host subsription is Unknown")
    return(host_is_subscribed)


def which_repos_are_enabled(incoming_dict):
    """
    which_repos_are_enabled parses the output from 'subscription-manager repos' command
    After parsing, it stores enabled repos in a dictionary with the hostname as the key.
    This function does not return anything
    """
    output = subprocess.Popen(["subscription-manager", "repos"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout.read()
    hostname = socket.gethostname()
    repo_id_keyword = "Repo ID: "
    repo_enabled_keyword = "Enabled: "
    for line in output.split("\n"):
        if repo_id_keyword in line:
            repo_name = line.split(repo_id_keyword)[1].strip()
        if repo_enabled_keyword in line:
            if "1" in line.split(repo_enabled_keyword)[1]:
                is_repo_enabled = True
                add_to_dictionary(incoming_dict, hostname, repo_name, is_repo_enabled)



# check that proper yum packages are installed
