#!/usr/bin/python
# This script is intended to do most of the pre-work for the setup of OSE v 3.1 prior to running the ansible
# installer
# It makes the assumption that DNS is already setup properly and that the host from which this script is run
# has ssh-key access to all hosts you wish to configure
# Written by Steve ovens <steve.ovens@redhat.com>
# March 4, 2016

#### import section
import socket
import sys
import os
import subprocess
import shutil
import fileinput
import getpass
try:
    import ansible
except:
    print("This script requires ansible to be installed on the machine this script is being run from")
    print("Exiting...")
    sys.exit()

#### setup logging

class Tee(object):
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)

logfile = "/tmp/OSE_setup.log"
logfile_writer = open(logfile, "a")
old_stdout = sys.stdout
sys.stdout = Tee(sys.stdout, logfile_writer)
####

##### variable setup. This is a listing of the variables used in this script. Initialized to blank
ansible_host_file_location = "/etc/ansible/hosts"
ansible_file_master_section = "[masters]"
ansible_file_node_section = "\n[nodes]"
ansible_file_etcd_section = "\n[etcd]"
ansible_file_ose_children = "\n[OSEv3:children]" \
               "\nmasters" \
               "\nnodes" \
               "\netcd"
ansible_file_ose_vars = "\n[OSEv3:vars]" \
                        "\ndeployment_type=openshift-enterprise" \
                        "\nopenshift_master_cluster_method=native"
ansible_file_lb_section = "\n[lb]"

subscribe_hosts = ""
subscription_username = ""
subscription_password = ""

master_node_list = []
infrastructure_node_list = []
application_node_list = []
# Dictionary is used to store region and zone information
application_node_dict = {}
infrastructure_node_dict = {}
etcd_node_list = []

forward_dns_error_list = []
reverse_dns_error_list = []

# The load balancer doesn't need to be a list, but it is used for consistent handling of node names
load_balancer_node_lst = []

number_of_masters = ""
number_of_application_nodes = ""
number_of_infrastructure_nodes = ""
number_of_load_balancer_nodes = ""
etcd_on_master = ""
etcd_location = ""
use_infrastructure_nodes = ""
use_load_balancer_node = ""
openshift_portal_net = "172.30.0.0/16"
osm_cluster_network = "10.1.0.0/16"
osm_subdomain = ""
ose_required_packages_list = ["wget", "git", "net-tools", "bind-utils", "iptables-services", "bridge-utils",
                              "bash-completion", "atomic-openshift-utils", "docker"]
ose_repos = ["rhel-7-server-rpms", "rhel-7-server-extras-rpms", "rhel-7-server-ose-3.1-rpms"]

public_administration_url = ""
master_cluster_hostname = ""

docker_sysconfig_file = "/etc/sysconfig/docker"
docker_storage_file = "/etc/sysconfig/docker-storage-setup"
validate_docker_storage_file = ""
copy_docker_storage_file = ""
##### End variable declarations

##### Static method declaration


def add_to_list(list_name, number_of_hosts, question):
    counter = 0
    while counter < int(number_of_hosts):
        list_name.append(raw_input("Please enter the fqdn of " + question + str(counter + 1) + ": "))
        counter += 1


def add_to_dictionary(dictionary_name, number_of_hosts, question):
    counter = 0
    determine_current_default_region = question.split()[0]
    if "infrastructure" in determine_current_default_region:
        current_region = "Infra"
    if "app" in determine_current_default_region:
        current_region = "Applications"
    change_default_region = validate_yes_no_answer("Do you wish to change the default region from %s"
                                                       " (yes/no)? " % current_region)
    if "yes" in change_default_region:
        current_region = raw_input("Please enter a region name: ")
    add_zone = validate_yes_no_answer("Do you want to add zones for your nodes (yes/no)? ")
    while counter < int(number_of_hosts):
        dictionary_key = raw_input("Please enter the fqdn of " + question + str(counter + 1) + ": ")
        if "yes" in add_zone:
            current_zone = raw_input("Please enter the zone this host is located in: ")
            dictionary_name[dictionary_key] = {'region': current_region, 'zone': current_zone}
        else:
            dictionary_name[dictionary_key] = {'region': current_region}
        counter +=1


def validate_yes_no_answer(question_to_re_ask):
    answer = raw_input(question_to_re_ask).lower()
    while answer != "yes" and answer != "no":
        print("\nPlease enter yes or no")
        answer = raw_input(question_to_re_ask)
    return answer


def validate_int(question_to_ask):
    answer = raw_input(question_to_ask)
    while answer != int:
        try:
            answer = int(answer)
            break
        except ValueError:
            print("That is not a valid number")
            answer = raw_input(question_to_ask)


def subscription_manager_setup():
    register_command = ["subscription-manager", "register", "--username=%s" % subscription_username, "--password=%s"
                        % subscription_password]
    attach_command = ["subscription-manager", "attach", "--auto"]
    disable_repo = ["subscription-manager", "repos", "--disable=*"]
    enable_repo_command = ["subscription-manager", "repos"]
    for repos in ose_repos:
        enable_repo_command.append('--enable=%s' % repos)
    return(register_command, attach_command, disable_repo, enable_repo_command)


def run_subscription_manager(*args):
    for item, command in enumerate(args):
        if command:
            print(subprocess.Popen(command, stderr = subprocess.STDOUT, stdout = subprocess.PIPE).communicate()[0])


def do_yum_install():
    # while it is bad for to do an import statement outside of the header, if this script is being run
    # on a non-RHEL host, this bit of code is unneeded
    import yum
    yb = yum.YumBase()
    inst = yb.rpmdb.returnPackages()
    installed = [x.name for x in inst]

    for package in ose_required_packages_list:
        if package in installed:
            print('{0} is already installed'.format(package))
        else:
            print('Installing {0}'.format(package))
            kwarg = {
                    'name':package
            }
            yb.install(**kwarg)
            yb.resolveDeps()
            yb.buildTransaction()
            yb.processTransaction()


def gather_docker_storage_file_info():
    docker_storage_autoextend = validate_yes_no_answer("Do you want docker to autoextend the volume group as needed "
                                                       "(yes/no)? ")
    docker_storage_devs = raw_input("What device (ex. /dev/sdX) do you want to use for the docker storage? ")
    docker_storage_vg = raw_input("What would you like to name the volume group? ")
    return(docker_storage_autoextend, docker_storage_devs, docker_storage_vg)


def write_docker_storage_file(autoextend_vg, user_defined_devs, user_defined_vg, user_defined_docker_storage_file):
    # Ensure that the global logfile is closed before starting to write the docker-storage-file
    sys.stdout = old_stdout
    f = open(user_defined_docker_storage_file, "w")
    f.write("DEVS=%s\n" % user_defined_devs)
    f.write("VG=%s\n" % user_defined_vg)
    f.write("AUTO_EXTEND_POOL=%s\n" % autoextend_vg)
    f.close()


def run_anisble_adhoc_on_all_hosts(command_to_run):
    print(subprocess.Popen(["ansible", "OSEv3", "-a", "%s" % command_to_run], stderr = subprocess.STDOUT,
                           stdout = subprocess.PIPE).communicate()[0])


def ansible_copy_to_all_hosts(file_to_copy):
    print(subprocess.Popen(["ansible", "OSEv3", "-m", "copy", "-a", "src=%s dest=%s" % (file_to_copy, file_to_copy)],
                           stderr = subprocess.STDOUT, stdout = subprocess.PIPE).communicate()[0])


##### End method declarations

print("This script expects that the following conditions are met before being run:")
print("1: DNS forward and reverse records for all the hosts intended to be in the OSE environment are pre-setup")
print("2: SSH keys from this host to the root user of all hosts in the OSE environment exist")
print("3: The optional requirement of an NFS server is done outside the scope of this setup script")

print("\nBy default OSE uses 172.30.0.0/16 (openshift_master_portal_net) and 10.1.0.0/16 (osm_cluster_network_cidr) "
      "if this overlaps with your current network topology you may change OSE to use a different subnet "
      "during this setup.")

subscribe_hosts = validate_yes_no_answer("\nDo you want to subscribe to the RHN now? ")
logfile_writer.write(subscribe_hosts)
if "yes" in subscribe_hosts:
    subscription_username = raw_input("Please enter the username for RHN access: ")
    logfile_writer.write(subscription_username)
    subscription_password = getpass.getpass(prompt="Please enter your password for the RHN network: ")
    logfile_writer.write("****")
##### setup the masters


number_of_masters = validate_int("\nHow many masters is your environment going to have? ")
logfile_writer.write(number_of_masters)

etcd_on_master = validate_yes_no_answer("\nAre the etcd services going to reside on the master nodes (yes/no)? ")
logfile_writer.write(etcd_on_master)

add_to_list(master_node_list, number_of_masters, "master node ")

if "no" in etcd_on_master:
    add_to_list(etcd_node_list, number_of_masters, "etcd node")
else:
    etcd_node_list = master_node_list


#### setup the infrastructure

use_load_balancer_node = validate_yes_no_answer("\nAre you going to have a separate node for HA Proxy load balancing "
                                                "(yes/no)? ")
logfile_writer.write(use_load_balancer_node)

if "yes" in use_load_balancer_node:
    number_of_load_balancer_nodes = validate_int("\nPlease enter the number of load balancer nodes in the OSE environment: ")
    logfile_writer.write(number_of_load_balancer_nodes)
    add_to_list(load_balancer_node_lst, number_of_load_balancer_nodes, "load balancer node ")

use_infrastructure_nodes = validate_yes_no_answer("\nAre you going to have separate nodes for infrastructure such as "
                                                  "the router or docker registry (yes/no)? ")
logfile_writer.write(use_infrastructure_nodes)

if "yes" in use_infrastructure_nodes:
    number_of_infrastructure_nodes = validate_int("\nPlease enter the number of infrastructure nodes the OSE environment: ")
    logfile_writer.write(number_of_infrastructure_nodes)
    add_to_dictionary(infrastructure_node_dict, number_of_infrastructure_nodes, "infrastructure node ")


#### setup the application nodes

number_of_application_nodes = validate_int("\nHow many application nodes will you have? ")
logfile_writer.write(number_of_application_nodes)
add_to_dictionary(application_node_dict, number_of_application_nodes, "application node ")

print("\nIt is recommended that you specify a subdomain for your application wild card dns")
print("For example, if your OSE domain is example.com, you might want to consider setting the default subdomain to "
      "apps.example.com and using this for your wild card entry")

set_default_subdomain = validate_yes_no_answer("\nDo you want to change the OSE default subdomain (yes/no)? ")
logfile_writer.write(set_default_subdomain)

if "yes" in set_default_subdomain:
    osm_subdomain = raw_input("Please enter the subdomain you wish to use for dynamic link generation: ")
    logfile_writer.write(osm_subdomain)

# all_nodes_list isn't required but in the event that more node types will be defined, it's easier to add it to
# an 'all_nodes_list' then anywhere node lists may be referenced below

for node in application_node_dict.keys():
    application_node_list.append(node)

for node in infrastructure_node_dict.keys():
    infrastructure_node_list.append(node)

all_nodes_list = [master_node_list, application_node_list, infrastructure_node_list, load_balancer_node_lst]

#### setup the networking for OSE

change_portal_net = validate_yes_no_answer("\nDo you want to change the default portal network (yes/no)? ")
logfile_writer.write(change_portal_net)
change_osm_cluster_net = validate_yes_no_answer(("\nDo you want to change the default cluster network (yes/no)? "))
logfile_writer.write(change_osm_cluster_net)

if "yes" in change_portal_net:
    openshift_portal_net = raw_input("\nPlease enter the subnet with cidr mask for the Portal Network: ")
    logfile_writer.write(openshift_portal_net)

if "yes" in change_osm_cluster_net:
    osm_cluster_network = raw_input("\nPlease enter the subnet with cidr mask for the cluster network: ")
    logfile_writer.write(osm_cluster_network)

#### Setup the required packages

are_we_running_on_a_host_inside_ose = validate_yes_no_answer("\nIs this script being run from a host that will be part"
                                                             " of the OSE environment (yes/no)? ")
logfile_writer.write(are_we_running_on_a_host_inside_ose)

register_command, attach_command, disable_repo, enable_repo_command = subscription_manager_setup()

if "yes" in are_we_running_on_a_host_inside_ose:
    run_subscription_manager(register_command, attach_command, disable_repo, enable_repo_command)
    do_yum_install()
else:
    are_we_on_a_RHEL_host = validate_yes_no_answer("\nIs this script being run on a RHEL host (yes/no)? ")
    logfile_writer.write(are_we_on_a_RHEL_host)
    if "yes" in are_we_on_a_RHEL_host:
        run_subscription_manager(register_command, attach_command, disable_repo, enable_repo_command)
        do_yum_install()


#### Set the ansible file

# Set the node section
if infrastructure_node_dict:
    for infra in infrastructure_node_dict.keys():
        ansible_file_node_section += '\n%s openshift_node_labels="%s"' % (infra, infrastructure_node_dict[infra])

if application_node_dict:
    for app in application_node_dict.keys():
        ansible_file_node_section += '\n%s openshift_node_labels="%s"' % (app, application_node_dict[app])

# Set the master section

for masters in master_node_list:
    ansible_file_master_section+= "\n%s openshift_schedulable=false" % masters
    ansible_file_node_section += "\n%s" % masters
    if "yes" in etcd_on_master:
        ansible_file_etcd_section += "\n%s" % masters

ansible_file_master_section += "\n"
ansible_file_node_section += "\n"
ansible_file_etcd_section += "\n"
ansible_file_lb_section += "\n"

# Set the OSEv3 section
print("\nOSE provides an administrative webUI for easy configuration. This normally defaults to the URL of your"
      "load balancer which in turn should load balance between your master nodes")
change_admin_url = validate_yes_no_answer("\nWould you like to specify a different public URL (yes/no)? ")
logfile_writer.write(change_admin_url)

if "yes" in use_load_balancer_node:
    ansible_file_ose_children += "\nlb"
    for host in load_balancer_node_lst:
        ansible_file_lb_section += "\n%s" % host
    if "yes" in change_admin_url:
        public_administration_url = raw_input("Please specify the public URL you would like to use: ")
        logfile_writer.write(public_administration_url)
    else:
        public_administration_url = load_balancer_node_lst[0]
    master_cluster_hostname = load_balancer_node_lst[0]
else:
    print("\nBecause you are not using an HA proxy load balancer in your OSE environment")
    public_administration_url = raw_input("Please specify the public URL you would like to use: ")
    logfile_writer.write(public_administration_url)
    master_cluster_hostname = raw_input("\nPlease enter a DNS cluster hostname for the master nodes: ")
    logfile_writer.write(master_cluster_hostname)
    ansible_file_lb_section = ""

ansible_file_ose_children += "\n"

use_htpasswd = validate_yes_no_answer("\nDo you want to use htpasswd for authentication (yes/no?) ")

if "yes" in use_htpasswd:
    ansible_file_ose_vars += "\nopenshift_master_identity_providers=[{'name': 'htpasswd_auth', 'login': 'true', 'challenge': 'true', 'kind': 'HTPasswdPasswordIdentityProvider', 'filename': '/etc/origin/htpasswd'}]"

ansible_file_ose_vars += "\nopenshift_master_cluster_hostname=%s" % master_cluster_hostname
ansible_file_ose_vars += "\nopenshift_master_cluster_public_hostname=%s" % public_administration_url
ansible_file_ose_vars += "\nopenshift_master_portal_net=%s" % openshift_portal_net
ansible_file_ose_vars += "\nosm_cluster_network_cidr=%s" % osm_cluster_network

if osm_subdomain:
    ansible_file_ose_vars += "\nosm_default_subdomain=%s" % osm_subdomain


# close the log file momentarily so that we can write the ansible file
sys.stdout = old_stdout

f = open(ansible_host_file_location, "w")
f.write(ansible_file_master_section)
f.write(ansible_file_node_section)
f.write(ansible_file_etcd_section)
f.write(ansible_file_lb_section)
f.write(ansible_file_ose_children)
f.write(ansible_file_ose_vars)
f.close()
#### End ansible file writing

# resume logging
sys.stdout = Tee(sys.stdout, logfile_writer)


#### DNS checks

# This section checks to ensure that the DNS prerequisites exist
print("\nBeginning forward and reverse zone checks...")
for each_node_type in all_nodes_list:
    for node in each_node_type:
        try:
            # Do the forward lookup
            host_ip = socket.gethostbyname(node)
        except socket.gaierror:
            forward_dns_error_list.append(node)
            host_ip = ""

        if host_ip:
            # Do the reverse lookup
            try:
                socket.gethostbyaddr(host_ip)
            except socket.herror:
                reverse_dns_error_list.append(node)

if forward_dns_error_list:
    print("\nThe following hosts (which you specified) failed the forward dns lookup:")
    for node in forward_dns_error_list:
        print(node)
else:
    print("All hosts PASSED forward zone checks")


if reverse_dns_error_list:
    print("\nThe following hosts (which you specified) failed the reverse dns lookup:")
    for node in reverse_dns_error_list:
        print(node)
else:
    if forward_dns_error_list:
        print("\nThe following failed both forward and reverse zone lookups")
        for node in forward_dns_error_list:
            print(node)
    else:
        print("\nAll hosts PASSED reverse zone lookups")

if "yes" in subscribe_hosts:
    print("\nThe hosts you indicated previously will now be subscribed to the RHN network with the credentials provided "
          "earlier.")
    run_anisble_adhoc_on_all_hosts(register_command)
    run_anisble_adhoc_on_all_hosts(attach_command)
    run_anisble_adhoc_on_all_hosts(disable_repo)
    run_anisble_adhoc_on_all_hosts(enable_repo_command)
else:
    print("\nYou elected not to subscribe to RHN, I assume this means that you have completed this step previously...")

print("Beginning the install of OSE required packages...")
yum_command = "yum install -y "
for packages in ose_required_packages_list:
    yum_command += "%s " % packages

run_anisble_adhoc_on_all_hosts(yum_command)

print("\nThe following section is meant to setup the docker storage on all hosts. It is recommended that you use a "
      "second disk for this operation. For all possible options for the docker storage, see 'man docker-storage-setup'")


is_this_correct_file = "no"
while "no" in is_this_correct_file:
    docker_storage_autoextend, docker_storage_devs, docker_storage_vg = gather_docker_storage_file_info()
    write_docker_storage_file(docker_storage_autoextend, docker_storage_devs, docker_storage_vg, docker_storage_file)
    # restart the global logger after writing to the docker file
    sys.stdout = Tee(sys.stdout, logfile_writer)
    print("This is your current docker-storage-setup-file: \n")
    with open(docker_storage_file, "r") as user_created_file:
        print(user_created_file.read())
    is_this_correct_file = validate_yes_no_answer("\nIs this correct (yes/no)? ")

print("A copy of %s has been placed in /tmp" % docker_sysconfig_file)
shutil.copyfile(docker_sysconfig_file, "/tmp/docker")

for line in fileinput.FileInput(docker_sysconfig_file, inplace = 1):
    if "OPTIONS=" in line:
        print("OPTIONS='--selinux-enabled --insecure-registry %s'" % openshift_portal_net)
    else:
        print(line),

print("\nCopying %s to all nodes" % docker_sysconfig_file)
os.popen("ansible OSEv3 -m copy -a 'src=%s dest=%s'" % (docker_sysconfig_file, docker_sysconfig_file)).read()

copy_docker_storage_file = validate_yes_no_answer("Do you want to copy the docker storage file to all nodes and run"
                                                  " the docker-storage-setup (yes/no)? ")

if "yes" in copy_docker_storage_file:
    print("\nCopying %s to all nodes" % docker_storage_file)
    ansible_copy_to_all_hosts(docker_storage_file)

    print("\nRunning docker-storage-setup on all nodes")
    run_anisble_adhoc_on_all_hosts("docker-storage-setup")

    print("Enabling docker...")
    run_anisble_adhoc_on_all_hosts("systemctl enable docker")
    run_anisble_adhoc_on_all_hosts("systemctl start docker")

    print("\nYou are now ready to proceed with the install of OSE")
    print("Run 'ansible-playbook /usr/share/ansible/openshift-ansible/playbooks/byo/config.yml' to proceed "
          "with the install")
else:
    print("\nThe docker setup has not been completed. Please verify /etc/sysconfig/docker-storage-setup."
          " Once you have set this file you can copy it to all hosts by running: ")
    print("ansible OSEv3 -m copy -a 'src=%s dest=%s'" % (docker_sysconfig_file, docker_sysconfig_file))
    print("\nTo complete the docker setup, run: ansible OSEv3 -a 'docker-storage-setup'")
    print("Run 'ansible-playbook /usr/share/ansible/openshift-ansible/playbooks/byo/config.yml' to proceed "
          "with the install")

