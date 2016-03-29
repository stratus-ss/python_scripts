#!/usr/bin/env python2

import socket
import subprocess
from helper_functions import ImportHelper
from ssh_connection_handling import HandleSSHConnections
ImportHelper.import_error_handling("paramiko", globals())
import hashlib
import yum
import sys
from optparse import OptionParser

ansible_ssh_user = "root"
docker_file_dict = {}
docker_service_check_dict = {}
forward_lookup_dict = {}
reverse_lookup_dict = {}
repo_dict = {}
subscription_dict = {}
ose_package_installed_dict = {}
ose_package_not_installed_dict = {}
ssh_connection = HandleSSHConnections()

ose_required_packages_list = ["wget", "git", "net-tools", "bind-utils", "iptables-services", "bridge-utils",
                              "bash-completion", "atomic-openshift-utils", "docker"]
ose_repos = ["rhel-7-server-rpms", "rhel-7-server-extras-rpms", "rhel-7-server-ose-3.1-rpms"]


parser = OptionParser()
parser.add_option('--ansible-host-file', dest='ansible_host_file', help='Specify location of ansible hostfile')
(options, args) = parser.parse_args()


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
            # I am assuming that FQDN's are being used, this is a work-around for distinguishing
            # between ansible children, vars and actual hostnames
            if "." in host:
                if not host in hosts_list:
                    hosts_list.append(host)
    return(hosts_list)


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


def check_forward_dns_lookup(host_name, dict_to_modify):
    """
    uses socket to do a forward lookup on host
    Does not return anything, inserts values into forward_lookup_dict
    """
    try:
        host_ip = socket.gethostbyname(host_name)
        add_to_dictionary(forward_lookup_dict, host_name, "IP Address", host_ip)
    except socket.gaierror:
        try:
            socket.inet_aton(host_name)
            print("You should be using FQDN instead of IPs in your ansible host file!")
            pass
        except socket.error:
            pass
        add_to_dictionary(dict_to_modify, host_name, "IP Address", None)


def check_reverse_dns_lookup(lookup_dict, dict_to_modify):
    """
    uses socket to do a reverse lookup on hosts in forward_lookup_dict
    Does not return anything, inserts values into reverse_lookup_dict
    """
    for server_name in lookup_dict.keys():
        host_ip = lookup_dict[server_name]["IP Address"]
        if host_ip is not None:
            try:
                hostname = socket.gethostbyaddr(host_ip)
                add_to_dictionary(dict_to_modify, server_name, "PTR Record", hostname)
            except socket.herror:
                add_to_dictionary(dict_to_modify, server_name, "PTR Record", None)


def check_docker_files(host, ssh_user, dict_to_modify):
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
                    add_to_dictionary(dict_to_modify, host, files, line.split()[0])
        except socket.error:
            print("No SSH connection is open")


def get_systemctl_output(service_to_check):
    systemctl_output = subprocess.Popen(["systemctl", "status", service_to_check], stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE).stdout.read()
    return(systemctl_output)


def is_docker_running(server_name, output, dict_to_modify):
    """
    is_docker_running checks whether docker is active. Stores the results in docker_service_check_dict
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
        add_to_dictionary(dict_to_modify, server_name, "Running", True)
    else:
        print("Docker is not running: \n")
        print(output)
        add_to_dictionary(dict_to_modify, server_name, "Running", False)


def is_docker_enabled(server_name, output, dict_to_modify):
    """
    is_docker_enabled checks to see if docker is enabled in systemd.
    Stores the results in docker_service_check_dict
    """
    for line in output.split("\n"):
        if "Loaded: " in line:
            if "enabled" in line.split("vendor preset")[0]:
                add_to_dictionary(dict_to_modify, server_name, "Enabled", True)
            else:
                add_to_dictionary(dict_to_modify, server_name, "Enabled", False)


def is_host_subscribed(server_name, dict_to_modify):
    """
    is_host_subscribed uses subprocess to run the subscription-manager command.
    It parses the output for the word 'Current' if found, returns true, otherwise returns false

    """
    subscription_manager_output = subprocess.Popen(["subscription-manager", "status"], stoud=subprocess.PIPE,
                                                   stderr=subprocess.PIPE).stdout.read()
    for line in subscription_manager_output.split("\n"):
        if "Overall" in line:
            if "Current" in line:
                add_to_dictionary(dict_to_modify, server_name, "Subscribed", True)
            else:
                add_to_dictionary(dict_to_modify, server_name, "Subscribed", False)


def which_repos_are_enabled(server_name, dict_to_modify):
    """
    which_repos_are_enabled parses the output from 'subscription-manager repos' command
    After parsing, it stores enabled repos in a dictionary with the hostname as the key.
    This function does not return anything
    """
    output = subprocess.Popen(["subscription-manager", "repos"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout.read()
    repo_id_keyword = "Repo ID: "
    repo_enabled_keyword = "Enabled: "
    for line in output.split("\n"):
        if repo_id_keyword in line:
            repo_name = line.split(repo_id_keyword)[1].strip()
        if repo_enabled_keyword in line:
            if "1" in line.split(repo_enabled_keyword)[1]:
                add_to_dictionary(dict_to_modify, server_name, repo_name, True)


def package_query(server_name, dict_to_modify, package_list):
    """
    package_query uses the yum module to determine if packages exist on the remote system
    Does not return anything, instead uses add_to_dictionary to populate dictionaries
    for processing later in the summation
    """

    yb = yum.YumBase()
    inst = yb.rpmdb.returnPackages()
    installed_on_system = [x.name for x in inst]
    ose_required_packages_installed = []
    ose_required_packages_not_installed = []
    for package in package_list:
        if package in installed_on_system:
            ose_required_packages_installed.append(package)
        else:
            ose_required_packages_not_installed.append(package)
    add_to_dictionary(ose_package_installed_dict, server_name, "Installed", ose_required_packages_installed)
    add_to_dictionary(ose_package_installed_dict, server_name, "Missing", ose_required_packages_not_installed)


if __name__ == "__main__":
    if options.ansible_host_file is None:
        print("No Ansible host file provided. This is required")
        parser.print_help()
        sys.exit()

    ansible_host_list = process_host_file(options.ansible_host_file)
    for server in ansible_host_list:
        can_connect_to_server = test_ssh_keys(server, ansible_ssh_user)
        if can_connect_to_server:
            ssh_connection.open_ssh(server, ansible_ssh_user)
            check_docker_files(server, ansible_ssh_user, docker_file_dict)
            systemctl_output = get_systemctl_output("docker")
            is_docker_enabled(server, systemctl_output, docker_service_check_dict)
            is_docker_running(server, systemctl_output, docker_service_check_dict)
            is_host_subscribed(server, subscription_dict)
            which_repos_are_enabled(server, repo_dict)
            package_query(server, repo_dict)
        check_forward_dns_lookup(server, forward_lookup_dict)
        check_reverse_dns_lookup(server, reverse_lookup_dict)

