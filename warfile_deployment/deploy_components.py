#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: July 2015
# Primary Function: This is intended to be used to deploy components. Currently it only deploys warfiles
# but it is modular enough to also deploy jarfiles as required.
# Log Location: Logging dumps to stdout
# Script notes: This script is the main callable during deployments. This deployment process includes:
# Undeploying of previous warfile, curl new warfile, attempts to determine current warfile version before deployment,
# version of warfile after deployment, if component information is not in the MANIFEST.MF the script will take an MD%SUM
# for comparison. Optionally, this script can clear akamai and will eventually set nagios downtime. Finally, deployed
# components are optionally moved to an Old_Promotes folder with the timestamp and if available, the warfile version
# Dependencies: deploy_commands.py, helper_functions.py, deployment_parameters.py, ssh_connection_handling.py,
# get_versions.py, purge_akamai.py

import os
import sys
import time
import socket
import operator

# This is important because we need to import some other python libraries
python_module_path = '/usr/local/scripts/python/'
sys.path.append(python_module_path)

from deploy_commands import DetermineHowToRestartTomcat, WhichLocalWarfilesToDeploy, CurlWarfile
from helper_functions import CleanUp, ValidConfigFile, ErrorHelper, ImportHelper
from deployment_parameters import ParseDeploymentParameters
from ssh_connection_handling import HandleSSHConnections
from get_versions import GenericServerType
from purge_akamai import PurgeAkamai
ImportHelper.import_error_handling("paramiko", globals())

class ServerDeployedTo(GenericServerType):

    def __init__(self, component_list):
        self.found_manifest_version = []
        self.get_version_from_manifest(component_list)


def restart_tomcat(command):
    # Since there are 3 different sections which may use these 2 lines
    # I have placed these in a function to reduce the code length and keep DRY
    ssh_connection.psuedo_tty.exec_command(command)
    ssh_connection.psuedo_tty.recv(1024)

def manifest_command(component):
    return("unzip -p %s META-INF/MANIFEST.MF" % component)

def add_to_dictionary(dictionary, name_of_server, component, value):
    if name_of_server in dictionary:
        dictionary[name_of_server][component] = value
    else:
        dictionary[name_of_server] = {component:value}

def convert_to_sorted_tuple(dictionary, sub_dictionary=None):
    # This function converts a dictionary to a sorted tuple for better output formatting
    if sub_dictionary is not None:
        sorted_tuple = sorted(getattr(dictionary, sub_dictionary).items(), key=operator.itemgetter(1))
    else:
        sorted_tuple = sorted(dictionary.items(), key=operator.itemgetter(1))
    sorted_tuple.sort()
    return(sorted_tuple)

# This counter is used to keep of which parameter file we are on so that when hashes are added into a list,
# we can retrieve them properly
paramater_file_counter = 0
local_predeployed_components_list = []
remotely_deployed_component_list = {}
server_list = []

# This is the initial error checking. It checks to see that the input files are text files
# and that the text files have the words 'deploy_warfiles.py' in the first line
# It will allow for a variable amount of config files to be passed in
configuration_counter = 0
parameter_file_list = []
while configuration_counter < len(sys.argv):
    # We are excluding sys.argv[0] as this would be the script name itself
    if configuration_counter == 0:
        pass
    else:
        # This section is checking for the words deploy_warfiles.py. This is a header that will have
        # To be present in the warfile config file
        is_valid_config = ValidConfigFile.config_check(sys.argv[configuration_counter], "deploy_warfiles.py")
        if is_valid_config:
            parameter_file_list.append(sys.argv[configuration_counter])
    configuration_counter += 1

configuration_counter = 0
deployment_parameters = []
for parameter_file in parameter_file_list:
    deployment_parameters.append(ParseDeploymentParameters(parameter_file))
    server_list.append(deployment_parameters[configuration_counter].server_list)
    # local_predeployed_components_list is a list of dictionaries. The dictionary is called
    # component_to_server_map which has the server name as the key and list of warfiles to be deployed to that server
    local_predeployed_components_list.append(WhichLocalWarfilesToDeploy(deployment_parameters[configuration_counter].warfile_list,
                                                                deployment_parameters[configuration_counter].warfile_path,
                                                                deployment_parameters[configuration_counter].server_list))
    configuration_counter +=1

# already_deployed_warfiles is a dictionary used to store all the warfiles that have been successfully curled.
# In the event of a deployment which fails on a particular warfile, this dict will list only files which have made it
# to the server. It key(s) correspond to the configuration files passed in, followed by a dict of server to component
# mappings. I.E. {0: { my_server: [warfile1, warfile2], my_server2: [warfile3, warfile4]}
already_deployed_warfiles = {}

# continue_with_deploy is used to check if there are no files to deploy. If even one component has been detected,
# this variable gets set to True and the deployment continues
continue_with_deploy = False

configuration_counter = 0
for config_file in local_predeployed_components_list:
    sorted_servers_names_to_deploy_to = convert_to_sorted_tuple(config_file, sub_dictionary="component_to_server_map")
    server_counter = 0
    for deployment in sorted_servers_names_to_deploy_to:
        server_name = sorted_servers_names_to_deploy_to[server_counter][0]
        warfile_list = sorted_servers_names_to_deploy_to[server_counter][1]
        if not warfile_list:
            print("Could not find any warfiles to deploy. Check: " + deployment_parameters[configuration_counter].warfile_path)
            continue
        else:
            continue_with_deploy = True
            ssh_connection = HandleSSHConnections()
            ssh_connection.open_ssh(server_name, deployment_parameters[configuration_counter].ssh_user)
            for individual_warfile in warfile_list:
                manifest_found = False
                curl = CurlWarfile(server_name, individual_warfile,
                                   tomcat_user=deployment_parameters[configuration_counter].tomcatuser,
                                   tomcat_password=deployment_parameters[configuration_counter].tomcatpass,
                                   tomcat_port=deployment_parameters[configuration_counter].tomcat_port,
                                   tomcat_version=deployment_parameters[configuration_counter].tomcat_version)
                remote_warfile = deployment_parameters[configuration_counter].tomcat_directory + os.sep + "webapps" + os.sep + \
                                 individual_warfile.split("/")[-1]
                # skip_server is set to true if there is a problem curling warfiles to a given server
                if curl.skip_server:
                    break
                else:
                    if configuration_counter in already_deployed_warfiles:
                        already_deployed_warfiles[configuration_counter].append(individual_warfile)
                    else:
                        already_deployed_warfiles[configuration_counter] = [individual_warfile]
                try:
                    check_manifest_command = manifest_command(remote_warfile)
                    stdin, stdout, stderr = ssh_connection.ssh.exec_command(check_manifest_command)
                    for line in stdout.channel.recv(1024).split("\n"):
                        if line.lower().startswith("version") or line.startswith("Implementation-Version"):
                            manifest_found = True
                            add_to_dictionary(remotely_deployed_component_list, server_name, remote_warfile,
                                              line.split()[1])
                    if not manifest_found:
                        stdin, stdout, stderr = ssh_connection.ssh.exec_command("md5sum %s" %remote_warfile)
                        ###########################
                        for line in stdout.channel.recv(1024).split("\n"):
                            if line.strip():
                                add_to_dictionary(remotely_deployed_component_list, server_name, remote_warfile,
                                              line.split()[0])
                except paramiko.AuthenticationException:
                    print("There was a problem with authentication to host %s" % server_name)
                    pass
                except socket.timeout:
                    print("There was a problem connecting to %s" % server_name)
                    pass
            print("")
            print("=======================================")
            time.sleep(2)
            if "y" in deployment_parameters[configuration_counter].restart_tomcat:
                try:
                    how_do_i_restart_tomcat = DetermineHowToRestartTomcat(deployment_parameters[configuration_counter].tomcat_restart_script,
                                                                          server_name)
                    if hasattr(how_do_i_restart_tomcat, "restart_command"):
                        print("\nRestarting tomcat on %s" % server_name)
                        print("With this command %s" % how_do_i_restart_tomcat.restart_command)
                        restart_tomcat(how_do_i_restart_tomcat.restart_command)
                    elif hasattr(how_do_i_restart_tomcat, "stop_command"):
                        print("\nRestarting tomcat on %s" % server_name)
                        print("With this command: %s" % how_do_i_restart_tomcat.stop_command)
                        restart_tomcat(how_do_i_restart_tomcat.stop_command)
                    elif hasattr(how_do_i_restart_tomcat, "legacy_command"):
                        print("\nRestarting tomcat on %s" % server_name)
                        print("With the legacy command: %s" % how_do_i_restart_tomcat.legacy_command)
                        restart_tomcat(how_do_i_restart_tomcat.legacy_command)
                except Exception,e:
                    print("unhandled exception")
                    print(e)
        server_counter +=1
    configuration_counter += 1
    try:
        ssh_connection.close_ssh()
    except NameError:
        continue

if not continue_with_deploy:
    print("\nThere were no files to deploy. Check the promotes directory as well as the config file(s) for typoos")
    sys.exit()
print("=======================================")
print("")
print("These are the versions of warfiles as found on the deployment server:")

# Since a deploy can have multiple components, we need to map each component to each server it is being deployed to
#
component_counter = 0
for individual_component_dict in local_predeployed_components_list:
    # The component_to_server_map dict looks like this:
    # {'ln-dv-tomcat4': ['/usr/local/ops/promotes/warfiles/GMIOM_Canada/QA/payment-ws.war'],
    # 'ln-dv-tomcat3': ['/usr/local/ops/promotes/warfiles/GMIOM_Canada/QA/payment-ws.war'], }
    # In order to format the output properly I am converting the dict to a tuple and then sorting it
    sorted_local_components = convert_to_sorted_tuple(individual_component_dict,
                                                      sub_dictionary="component_to_server_map")
    server_counter = 0
    for map_component_to_server in individual_component_dict.component_to_server_map.items():
        server_name = sorted_local_components[server_counter][0]
        warfile_list = sorted_local_components[server_counter][1]
        print("\nFor deployment to: %s\n" % server_name)
        component_check = ServerDeployedTo(warfile_list)
        component_list = component_check.found_manifest_version
        component_list.sort()
        if component_check.found_manifest_version:
            for each_warfile in component_list:
                warfile_printable_info = deployment_parameters[component_counter].warfile_path + os.sep + each_warfile
                print("\t" + warfile_printable_info)
        else:
            for files in warfile_list:
                md5sum = os.popen("md5sum %s" % files).read().split()[0]
                print("\t%s: \t%s" % (files, md5sum))
        server_counter +=1
    configuration_counter += 1

print("=======================================")
print("")
print("These were remotely deployed warfile versions:\n")

sorted_servers_deployed_to = convert_to_sorted_tuple(remotely_deployed_component_list)
for server_mapping in sorted_servers_deployed_to:
    print("Deployed to server: %s\n" % server_mapping[0])
    components_sorted = convert_to_sorted_tuple(server_mapping[1])
    for warfile_path, warfile_check_value in components_sorted:
        print("\t%s: \t%s" % (warfile_path, warfile_check_value))
    print("")

print("=======================================")
for config_number, warfile_list in already_deployed_warfiles.items():
    if "y" in deployment_parameters[config_number].move_file:
        move_warfile = ServerDeployedTo(warfile_list)
        for each_warfile in move_warfile.found_manifest_version:
            warfile_full_path = deployment_parameters[config_number].warfile_path + os.sep + each_warfile
            warfile_name = each_warfile.split(": ")[0]
            warfile_version = each_warfile.split(": ")[1]
            print("Moving \t%s to %s" % (warfile_name,
                                         deployment_parameters[config_number].old_warfile_path))
            CleanUp.move_warfiles_to_backup_location(warfile_full_path.split(":")[0],
                                                     deployment_parameters[config_number].old_warfile_path,
                                                     warfile_version=warfile_version.strip())
    if hasattr(deployment_parameters[config_number], "akamai_cred_file"):
        run_the_purge = PurgeAkamai(deployment_parameters[config_number].akamai_cred_file,
                                    deployment_parameters[config_number].cpcode_file)
    for files in os.listdir(deployment_parameters[config_number].warfile_path):
        full_path = deployment_parameters[config_number].warfile_path + os.sep + files
        if os.path.isfile(full_path):
            print("Moving \t%s to %s" % (full_path, deployment_parameters[config_number].old_warfile_path))
            CleanUp.move_warfiles_to_backup_location(full_path, deployment_parameters[config_number].old_warfile_path)
