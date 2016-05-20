#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: Oct 15, 2014
# Primary Function: This script will compare the 'critical' files on a set of servers
# looking for inconsistencies
# Log Location:  Where the script logs, if anywhere.
# NOTE: This script is using optparse because CentOS 6.x and below does not have argparse in the stdlib
# This may need to be updated moving forward

import operator
import os
import sys
from optparse import OptionParser
import rpm
import time
try:
    import paramiko
except:
    print("This script requires paramiko to be installed")
    print("yum install python-paramiko")
    sys.exit()


######################Global Variable Declaration ###############################

#These are dictionaries used for grouping files with servers
SERVER_LIST = {}
COMPARISON_LIST = {}
CONF_FILE_HASH_LIST = {}
Server_Dict = {}
RPM_HASH = {}
RPM_HASH_CHECK = {}
MISSING_FILE_LIST = []
FORMATTING = []

number_of_groups = 0
log_directory = "./logs"

parser = OptionParser()
parser.add_option('-f', dest='parameter_file', help='File containing list files to compare on the remote system')
parser.add_option('-u', dest='ssh_username', help='The user to perform the remote actions as')
(options, args) = parser.parse_args()

if options.parameter_file is None:
    print("Parameter file is missing")
    parser.print_help()
    sys.exit()

if options.ssh_username is None:
    print("No ssh username was specified")
    parser.print_help()
    sys.exit()
######################Global Function Definition#################################


def rpm_check(server_name, ssh_username):
    #log the rpms
    list_of_rpms = "%s_rpm.lst" % server_name
    #This toggles the stdout to a file
    old_stdout = sys.stdout
    SSH = sshConnections()
    SSH.open_ssh(server_name, ssh_username)
    sys.stdout = open(list_of_rpms, "w")
    #A list is not required to capture the output however, I want to produce an alphabetical sorting
    
    rpm_list = 'rpm -qa |sort'
    stdin, stdout, stderr = SSH.ssh.exec_command(rpm_list)
    #print the sorted list
    remote_rpm_hash = stdout.readlines()
    for rpm in remote_rpm_hash:
        print(rpm),
    SSH.close_ssh()
    sys.stdout = old_stdout
    try:
        import hashlib
        #Open the file for read-only and append the option to handle in case of being a binary file ('rb')
        file_to_hash = open(list_of_rpms, 'rb')
        sha_hash = hashlib.sha1()
    except:
        import sha
        sha_hash = sha.new()
        file_to_hash = open(list_of_rpms, 'rb')
    while True:
        #The data needs to be read in chunks for sha. SHA is more efficient than md5 as md5 can only handle 128 chunks
        data = file_to_hash.read(8192)
        #Loop through until there is no data left and then break the loop and calculate the final hash
        if not data:
            break
        sha_hash.update(data)
    hash_output = sha_hash.hexdigest()
    sys.stdout = old_stdout
    return hash_output


class sshConnections:
    #This class allows for easier multiple connections. 
    def open_ssh(self, server, user_name):
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.load_system_host_keys()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(server, username = user_name)
            self.transport = self.ssh.get_transport()
            self.psuedo_tty = self.transport.open_session()
            self.psuedo_tty.get_pty()
            self.read_tty = self.psuedo_tty.makefile()
        except Exception, e:
            if "Connection timed out" in e:
                print("SSH timed out while trying to connect to %s" % server)
            else:
                print("There was a problem attempting to establish a connection to %s" % server)

    def close_ssh(self):
        self.read_tty.close()
        self.psuedo_tty.close()
        self.ssh.close()
        #time.sleep(20)
        #time.sleep(2)


def process_parameter_file(parameter_file):
    global number_of_groups
    for line in open(parameter_file).readlines():
        #Ignore blank spaces, this will only process lines with which have text
        if line.strip():
            if not line.startswith("#"):
                #value is the generic variable for anything after the '=' sign
                value = line.split("=")[1].strip()
        if line.startswith("SERVER_GROUP"):
            group_name = 'Group' + line.split('=')[0].strip().split("SERVER_GROUP")[1]
            SERVER_LIST[value] = group_name 
        if line.startswith("GROUP"):
            number_of_groups = line.split('=')[0].strip().split("GROUP")[1].split("_FILES")[0]
            group_file_name = 'Group' + number_of_groups
            COMPARISON_LIST[value] = group_file_name


#def compare_servers()

def get_file_hashes(server_name, group_name, ssh_username, file_list):
    SSH = sshConnections()
    try:
        SSH.open_ssh(server_name, ssh_username)
    except:
        pass
    old_stdout = sys.stdout
    for individual_file, group in file_list.items():
        if group_name in group: 
            stdin, stdout, stderr = SSH.ssh.exec_command("sudo md5sum %s" % individual_file)
            md5_output = stdout.readlines()
            #The md5 output is returned as a tupple, so I am converting it to a string before adding
            #to the list
            addme = "-".join(md5_output) + "\n"
            try:
                server_key = group_name + "-" + server_name + "_" + addme.split()[1].strip()
                file_hash = addme.split()[0].strip()
                file_name = addme.split()[1].strip()
                Server_Dict[server_key] = file_hash
            except:
                message = "The expected file is missing: %s on %s" % (individual_file, server_name)
                MISSING_FILE_LIST.append(message)
            try:
                stdin, stdout, stderr = SSH.ssh.exec_command("sudo cat %s" % individual_file)
                cat_output = stdout.readlines()
                santized_filename = individual_file.replace("/", "_")
                sys.stdout = open("%s/%s_%s" %(log_directory, server_name, santized_filename), "w")
                for line in cat_output:
                    print(line),
            except:
                pass
        sys.stdout = old_stdout


def check_for_duplicates(incoming_dictionary, outgoing_dictionary):
~/    for key, value in incoming_dictionary.items():
        counter = 0
        if value not in outgoing_dictionary:
            outgoing_dictionary[value] = [key]   
        else:
            outgoing_dictionary[value].append(key)

#################################End Global Function Definition ################################

process_parameter_file(options.parameter_file)

for server, group in SERVER_LIST.items():
    get_file_hashes(server, group, options.ssh_username, COMPARISON_LIST)
    installed_rpms = rpm_check(server, options.ssh_username)
    RPM_HASH[server] = installed_rpms

check_for_duplicates(Server_Dict, CONF_FILE_HASH_LIST)
check_for_duplicates(RPM_HASH, RPM_HASH_CHECK)      
sorted_conf_file_hash = sorted(CONF_FILE_HASH_LIST.items(), key=operator.itemgetter(1))


print("###############Begin File Audit###################")
print("The following files did not match other servers'")
for key, value in sorted_conf_file_hash:
    if len(value) < 2:
        value = ''.join(value)
        value_file = value.split("_")[1]
        value_server = value.split("_")[0]
        appendme = value_file + " " + value_server + ": " + key 
        FORMATTING.append(appendme)

FORMATTING.sort()

previous_file = ''
for line in FORMATTING:
    current_file = line.split()[0]
    if current_file in previous_file:
        print(line)
    else:
        previous_file = current_file
        print("")
        print(line)

print("###########File Audit Completed##########")
print("")
print("###########Missing Files (if any)########")
for messages in MISSING_FILE_LIST:
    print(messages)
print("")
print("#########################################")
print("")
print("These are the servers whose installed rpms match")
print("")
for key, value in RPM_HASH_CHECK.items():
    for server in value:
        print(server + ": " + key)


