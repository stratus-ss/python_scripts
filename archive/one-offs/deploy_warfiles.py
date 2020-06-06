#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: Oct 24, 2013
# Updated: Nov 28, 2014
# Refactored code to break up the classes
# Added multiple configuration inputs
# Added better error handling so that it suppresses the python stack trace, or compliments it with
# a plain english explaination
# Primary Function: Deploys Warfiles to various environments
# This script is designed to work with tomcat 6 or 7. Most failures are caused by a problem
# with tomcat-users.xml.
# It is the intent of this script to abstract all variables into a config file.
# No one should have to alter this script ever, save for bug fixes or updates.
# All client updates should be done through the generation of new config files
# This script makes use of classes and OOP style programming.


import sys
import os
import subprocess
import shutil
import datetime
import time
import requests
import json
import pytz

try:
    import paramiko
except:
    print("""This script requires the module 'paramiko' to be installed. Use
'sudo pip install paramiko' to install, and then try again""")
    sys.exit()
try:
    import magic
except:
    print("""This script requires the module 'python-magic' to be installed. Use
'sudo pip install python-magic' to install, and then try again""")
    sys.exit()

todays_date = str(datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H:%M'))

#This is the initial error checking. It checks to see that the input files are text files
#and that the text files have the words 'deploy_warfiles.py' in the first line

try:
    #This section will allow for a variable amount of config files to be passed in
    counter = 0
    PARAMETER_FILE_LIST = []
    while counter < len(sys.argv):
        #We are excluding sys.argv[0] as this would be the script name itself
        if counter == 0:
            pass
        else:
            #This section is checking for the words deploy_warfiles.py. This is a header that will have
            #To be present in the warfile config file
            if "ASCII" in (magic.from_file(sys.argv[counter])):
                is_this_my_config = open(sys.argv[counter], 'r')
                first_line = is_this_my_config.readline()
                if "deploy_warfiles.py" in first_line:
                    print("header has valid key word, assuming this is a valid config")
                else:
                    print("This is a text file but does not appear to be a valid warfile deployment config")
                    sys.exit()
            #If the file isnt a text file, abort
            else:
                print("This does not appear to be a text file/valid config file...ABORT")
                sys.exit()
            PARAMETER_FILE_LIST.append(sys.argv[counter])
        counter += 1
    #I am dynamically initializing blank arrays based on the number of the config files passed in
    REMOTE_WARFILES = [[] for x in range(0, len(PARAMETER_FILE_LIST))]
    LOCAL_WARFILES = [[] for x in range(0, len(PARAMETER_FILE_LIST))]
except:
    print("""
    USAGE: This script expects at least one config file passed in as an argument

    I.E: ./deploy_warfiles.py config_file
    """)
    sys.exit()

#This class will handle the parsing of the config file
class ParseDeploymentParameters:

    def setDeploymentParameters(self, config_file):
        #These are being initialized blank so that they are over written each time this function is called
        #This is what allows multiple configs to be passed in
        self._WARFILE_LIST = []
        self._SERVER_LIST = []
        self.INCOMING_CONFIG_FILE = config_file
        for line in open(self.INCOMING_CONFIG_FILE).readlines():
            #Ignore blank spaces, this will only process lines with which have text
            if line.strip() and not line.startswith("#"):
                value = line.split("=")[1].strip()
            if line.startswith("PATH_TO_WARFILE"):
                self.WARFILE_PATH = value
            elif line.startswith("OLD_WARFILE_PATH"):
                self.OLD_WARFILE_PATH = value
            elif line.startswith("WARFILE_NAME"):
                self._WARFILE_LIST.append(value)
            elif line.startswith("SERVERS"):
                self._SERVER_LIST.append(value)
            elif line.startswith("TOMCAT_PORT"):
                self.TOMCAT_PORT = value
            elif line.startswith("RESTART_TOMCAT"):
                self.RESTART_TOMCAT = value
            elif line.startswith("TOMCAT_VERSION"):
                self.TOMCAT_VERSION = value
            elif line.startswith("SSH_USER"):
                self.SSH_USER = value
            elif line.startswith("MOVE_FILE"):
                self.MOVE_FILE = value
            elif line.startswith("TOMCAT_RESTART_SCRIPT"):
                self.TOMCAT_RESTART_SCRIPT = value
            elif line.startswith("TOMCATUSER"):
                self.TOMCATUSER = value
            elif line.startswith("TOMCATPASS"):
                self.TOMCATPASS = value
            elif line.startswith("NAG_START"):
                self.NAG_START = value
            elif line.startswith("NAG_STOP"):
                self.NAG_STOP = value
            elif line.startswith("NAGIOS_SERVER"):
                self.NAGIOS_SERVER = value
            elif line.startswith("TOMCAT_DIRECTORY"):
                self.TOMCAT_DIRECTORY = value
            elif line.startswith("CPCODE_FILE"):
                self.CPCODE_FILE = value
            elif line.startswith("AKAMAI_CRED_FILE"):
                self.AKAMAI_CRED_FILE = value


class sshConnections:
    #This class allows for easier multiple connections. The problem is because /etc/init.d/tomcat restart
    #Sometimes does not wait long enough between stop and start functions. As a result, tomcat may stay down
    #To remedy this, this class will open multiple connections inserting a 20 second pause between connections
    #Hopefully this will allow most instances of tomcat to shutdown gracefully before restarting
    def open_ssh(self, server, user_name):
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(server, username = user_name, timeout=240)
        self.transport = self.ssh.get_transport()
        self.psuedo_tty = self.transport.open_session()
        self.psuedo_tty.get_pty()
        self.read_tty = self.psuedo_tty.makefile()

    def close_ssh(self):
        self.read_tty.close()
        self.psuedo_tty.close()
        self.ssh.close()
        time.sleep(2)

    def try_ssh(self, server_name, parameters):
        try:
                connection_attempt = 0
                try:
                    return SSH.open_ssh(server_name, parameters)
                except:
                    try:
                        return SSH.open_ssh(server_name, parameters)
                    except:
                        print("There was a problem connecting to %s" % server)
                        while connection_attempt < 4:
                            try:
                                connection_attempt += 1
                                print("Making attempt %s" % (connection_attempt + 1))
                                return SSH.open_ssh(server_name, parameters)
                            except:
                                pass
        except:
            print("Connection to remote server failed after multiple attempts")


class StartDeployment:


    def deployment_commands(self, tomcat_version, tomcat_user, tomcat_password, tomcat_port,
         warfile_path, server_hostname, warfile_name, deployment_path, UNDEPLOY_COMMAND, DEPLOY_COMMAND):
            #This section toggles the commands required to deploy to tomcat 6 or 7
            if "7" in warfile_parameters.TOMCAT_VERSION:
                DEPLOY_COMMAND = '/usr/bin/curl -u%s:%s --anyauth --upload-file %s --url \
                "http://%s:%s/manager/text/deploy?%s" -w "Deployed %s"' % (tomcat_user, tomcat_password,
                 warfile_path, server_hostname, tomcat_port, deployment_path, warfile_name)
                UNDEPLOY_COMMAND = '/usr/bin/curl -u%s:%s --url "http://%s:%s/manager/text/undeploy?%s" \
                 -w "Deleted %s "' % (tomcat_user, tomcat_password, server_hostname,
                 tomcat_port, deployment_path, warfile_name)
            else:
                DEPLOY_COMMAND = '/usr/bin/curl -u%s:%s --anyauth --form deployWar=@%s \
                --url http://%s:%s/manager/html/upload -w "Deployed %s "' % (tomcat_user, tomcat_password,
                warfile_path, server_hostname, tomcat_port, warfile_name)
                UNDEPLOY_COMMAND = '/usr/bin/curl -u%s:%s --url http://%s:%s/manager/html/undeploy -d %s \
                -w "Deleted %s "' % (tomcat_user, tomcat_password, server_hostname, tomcat_port,
                deployment_path, warfile_name)
            return (UNDEPLOY_COMMAND, DEPLOY_COMMAND)

    def begin_deployment(self, restart_script, config_counter):
        curl_activities = curlWarfile()
        #These lists are to show all of the hashes
        self.predeployed_warfile_hashes = []

        #TOMCAT_PORT specifies the naming convention of tomcat. Some servers it may be 8585, 9090, 8080 etc.
        try:
            TOMCAT_PORT = warfile_parameters.TOMCAT_PORT
        except:
            TOMCAT_PORT = 8080

        #Some environments have special restart scripts, others just use the tomcat init scripts
        #This is to determine which will be used
        if "init" in warfile_parameters.TOMCAT_RESTART_SCRIPT:
            self.STOP_COMMAND = "%s stop" % (restart_script)
            self.START_COMMAND = "%s start" % (restart_script)
        else:
            self.RESTART_COMMAND = restart_script
        for WARFILE in warfile_parameters._WARFILE_LIST:
            WARFILE_PATH = warfile_parameters.WARFILE_PATH + os.sep + WARFILE
            #Set the deploy path for tomcat curl deploys
            DEPLOY_PATH = "path=/%s" % WARFILE.replace("#", "/").replace(".war", "")
            #Only continue processing if the warfile listed in the config file exists
            if os.path.exists(WARFILE_PATH):
                #Get the predeployment warfile hash
                hash_file = os.popen("md5sum %s" % WARFILE_PATH).read()
                self.predeployed_warfile_hashes.append(hash_file)
                for EACH_SERVER in warfile_parameters._SERVER_LIST:
                    try:
                        if hasattr(warfile_parameters, "NAG_STOP"):
                            print(("Turning of Nagios on host %s" % EACH_SERVER))
                            os.popen("%s %s %s" % (warfile_parameters.NAG_STOP, EACH_SERVER,
                            warfile_parameters.NAGIOS_SERVER)).read()
                        UNDEPLOY_COMMAND, DEPLOY_COMMAND = self.deployment_commands(warfile_parameters.TOMCAT_VERSION,
                        warfile_parameters.TOMCATUSER, warfile_parameters.TOMCATPASS, warfile_parameters.TOMCAT_PORT,
                        WARFILE_PATH, EACH_SERVER, WARFILE, DEPLOY_PATH, UNDEPLOY_COMMAND = "", DEPLOY_COMMAND = "")
                        print("")
                        print("=======================================")
                        print(("Beginning Undeploy of old version of %s to %s on port %s" %
                        (WARFILE, EACH_SERVER, TOMCAT_PORT)))
                        print("=======================================")
                        curl_activities.check_curl_success(UNDEPLOY_COMMAND, EACH_SERVER)
                        print("")
                        print("=======================================")
                        print(("Beginning Deploy of %s to %s on port %s" % (WARFILE, EACH_SERVER,
                        TOMCAT_PORT)))
                        print("=======================================")
                        print("")
                        #Run the deploy command through the check
                        did_curl_fail = curl_activities.check_curl_success(DEPLOY_COMMAND, EACH_SERVER)
                        #If the deploy fails, assume its a network error, and retry up to 3 times
                        #It will wait 10 seconds before retrying the curl
                        if did_curl_fail == "yes":
                            retry_count = 0
                            while retry_count != 3:
                                print("")
                                print(("Curl Deployment failed, retrying in 10 seconds.\
                                This is attempt number %s" % (retry_count + 1)))
                                print("")
                                time.sleep(10)
                                curl_activities.check_curl_success(DEPLOY_COMMAND, EACH_SERVER)
                                retry_count += 1
                            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                            print(("I was unable to reach %s, the deployment failed" % EACH_SERVER))
                    except Exception as e:
                        print(e)
                        pass
                try:
                    if "y" in warfile_parameters.MOVE_FILE.lower():
                        shutil.move('%s' % (WARFILE_PATH), '%s/%s.%s' %
                        (warfile_parameters.OLD_WARFILE_PATH, WARFILE, todays_date))
                except Exception, e:
                    print("")
                    if "Permission denied:" in str(e):
                        print("""There is a permission problem with the directory.
Unable to move warfile to %s""" % warfile_parameters.OLD_WARFILE_PATH)
                        sys.exit()
        curl_activities.verify_warfiles(config_counter)
        #This is another work-around to change the output to the terminal
        LOCAL_WARFILES[config_counter] = self.predeployed_warfile_hashes


class curlWarfile:


    def verify_warfiles(self, config_counter):
        deployed_war_hashes = []
        #This section needs work. We dont have a unified restart script yet to describe all the various
        #environments so this will be a work in progress. Maybe I should move this out to the config file
        #In addition to restarting tomcat, it also grabs an md5 hash of the warfiles on the server
        if "y" in warfile_parameters.RESTART_TOMCAT.lower():
            for EACH_SERVER in warfile_parameters._SERVER_LIST:
                print("")
                print("=======================================")
                print(("Restarting tomcat on %s with this command: %s" % (EACH_SERVER,
                warfile_parameters.TOMCAT_RESTART_SCRIPT)))
                SSH = sshConnections()
                SSH.try_ssh(EACH_SERVER, warfile_parameters.SSH_USER)
                #Loop through all of the files in the remote webapps directory
                for predeployed_warfile_hash in deployment.predeployed_warfile_hashes:
                    stdin, stdout, stderr = SSH.open_ssh.ssh.exec_command(
                        "md5sum %s/webapps/%s"
                        % (
                            warfile_parameters.TOMCAT_DIRECTORY,
                            predeployed_warfile_hash.split("/")[-1],
                        )
                    )

                    md5_output = stdout.readlines()
                    #The md5 output is returned as a tupple, so I am converting it to a string before adding
                    #to the list
                    addme = "".join(md5_output) + "\n"
                    deployed_war_hashes.append(addme.rstrip())
                #I am inserting the the server name in front of each set of warfile hashes
                deployed_war_hashes.insert((len(deployed_war_hashes) - len(deployment.predeployed_warfile_hashes)),
                     (EACH_SERVER + ": "))
                #NOHUP was added to this section because sometimes the ssh session closes before
                #the restart command has finished executing causing the services to stay down
                if hasattr(deployment, "RESTART_COMMAND"):
                    SSH.open_ssh.psuedo_tty.exec_command("sudo nohup %s >/dev/null 2>&1" % deployment.RESTART_COMMAND)
                    SSH.open_ssh.psuedo_tty.recv(1024)
                    SSH.close_ssh()
                else:
                    print("Stopping tomcat")
                    SSH.open_ssh.psuedo_tty.exec_command("sudo nohup %s >/dev/null 2>&1" % deployment.STOP_COMMAND)
                    SSH.open_ssh.psuedo_tty.recv(1024)
                    SSH.close_ssh()
                    print("Sleeping for 10, then restarting tomcat")
                    time.sleep(10)                  
                    SSH = sshConnections()
                    SSH.try_ssh(EACH_SERVER, warfile_parameters.SSH_USER)
                    SSH.open_ssh.psuedo_tty.exec_command("sudo nohup %s >/dev/null 2>&1" % deployment.START_COMMAND)
                    SSH.open_ssh.psuedo_tty.recv(1024)
                    SSH.close_ssh()
                if hasattr(warfile_parameters, "NAG_START"):
                    print(("Re-enabling Nagios on host %s" % EACH_SERVER))
                    os.popen("%s %s %s" % (warfile_parameters.NAG_START, EACH_SERVER,
                    warfile_parameters.NAGIOS_SERVER)).read()
        print("=======================================")
        print("")
        #This was added as a hack to get the output for multiple scripts to be formatted
        REMOTE_WARFILES[config_counter] = deployed_war_hashes


    def check_curl_success(self, command, SERVER_NAME):
        counter = 0
        #Curl uses stderr to show its progress so subprocess is required to capture this output
        for response_from_curl_attempt in subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
             shell=True).stderr.read().split("\n"):
            counter += 1
            print((response_from_curl_attempt.split("\n")[0].rstrip()))
            if counter == 3:
                #Because the curl command constantly updates this line until the transfer is complete
                #The output is simply appended to the list. Therefore the most reliable way to determine
                #Whether the file has transfered is to get the 8th to last column which is labeled as 'Xferd'
                if "refused" in response_from_curl_attempt:
                    print("""
The connection to the server %s was refused... is the port closed?
""" % SERVER_NAME)
                    sys.exit()
                if response_from_curl_attempt == "":
                    print("""
The connection to the server %s was refused... is the port closed?
""" % SERVER_NAME)
                    sys.exit()

                if int(response_from_curl_attempt.split("\n")[0].rstrip().split()[-8]) == 0:
                    curl_fail = "yes"
                else:
                    curl_fail = "no"
                return curl_fail




#If the environment requires an Akamai purge, this section will activate
#This section requires that the django_akamai egg be installed
class purgeAkamai:
    def __init__(self):

        try:
            user_file = open(warfile_parameters.AKAMAI_CRED_FILE).readlines()
            cp_code_file = open(warfile_parameters.CPCODE_FILE).readlines()
        except:
            print("There was a problem with the akamai clearing")
            sys.exit()

        #Gather the user name and password from the user_file
        for line in user_file:
            if "username" in line:
                username = line.split("=")[1].strip()
            if "password" in line:
                password = line.split("=")[1].strip()

        #Since most of the servers have been converted to GMT, report time in GMT
        timezone = pytz.timezone("GMT")
        purge_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d-%H:%M")

        #These urls were obtained from https://api.ccu.akamai.com/ccu/v2/docs/index.html
        akamai_base_url = "https://api.ccu.akamai.com"
        akamai_clear_url = akamai_base_url + "/ccu/v2/queues/default"

        credentials = (username, password)

        #These headers are important as they declare the post type to be json which akamai requires
        akamai_headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

        ###################### This is the purge section ######################

        counter = 0
        cp_code_list = ''
        for individual_cpcode in cp_code_file:
            #Ignore commented lines
            if not individual_cpcode.startswith("#"):
                counter += 1
                #The rest API requires a comma separated list for CPCodes
                #This section makes sure that all but the last CPCode has a comma after it
                if counter < len(cp_code_file):
                    cp_code_list += '"%s",' % individual_cpcode.strip()
                else:
                    cp_code_list += '"%s"' % individual_cpcode.strip()

        #Construct the dict to send to akamai, it should look something like this:
        #{ "type" : "cpcode", "objects" : [ "334455" ] }
        data = '{"objects": [%s], "type": "cpcode"}' % cp_code_list

        #Send the purge request
        request_clear = requests.post(akamai_clear_url, data=data, auth=credentials, headers=akamai_headers)

        #I am turning the json object into a python dictionary so I can extract the Uri
        akamai_response_to_clear_request = json.loads(request_clear.text)

        print(("Time until purge completion: " + str(akamai_response_to_clear_request["estimatedSeconds"])))
        print(("Status: " + akamai_response_to_clear_request["detail"]))
        akamai_purge_url = akamai_base_url + akamai_response_to_clear_request["progressUri"]

        #This step is not needed because all it does is checks the status.
        #However it is a good way to verify that the request was sent and is being processed properly
        request_status = requests.get(akamai_purge_url, auth=credentials, headers=akamai_headers)

        response_to_status_request = json.loads(request_status.text)
        print("")
        print(("Submitted by: " + response_to_status_request["submittedBy"]))
        print(("Purge ID: " + response_to_status_request["purgeId"]))
        print(("Status: " + response_to_status_request["purgeStatus"]))
        print("")

        print(("The original purge request was sent on: " + purge_date))

        #Create the file so that we can check later
        request_file = open("/tmp/check_akamai_status", "w")
        request_file.write("#This is the PROGRESS URI of the request sent on %s GMT\n" % purge_date)
        request_file.write(akamai_response_to_clear_request["progressUri"])
        request_file.close()


#This section will go through the array of input files
#And execute on each individually
counter = 0
for PARAM_FILES in PARAMETER_FILE_LIST:
    warfile_parameters = ParseDeploymentParameters()
    warfile_parameters.setDeploymentParameters(PARAM_FILES)
    deployment = StartDeployment()
    deployment.begin_deployment(warfile_parameters.TOMCAT_RESTART_SCRIPT, counter)
    counter += 1
    if hasattr(warfile_parameters, "CPCODE_FILE"):
        purgeAkamai()


#Display the warfile hashes after the deploy is completed
print("The predeployed (local) warfiles have the following hashes:\n")
warfile_counter = 0
input_file_counter = 0
for predeployed_hash_list in LOCAL_WARFILES:
    print(PARAMETER_FILE_LIST[input_file_counter])
    for individual_hash in predeployed_hash_list:
        print(individual_hash.strip())
        warfile_counter += 1
        if warfile_counter == (len(predeployed_hash_list)):
            print("")
            warfile_counter = 0
            input_file_counter += 1

print("")
print("These are the files which were deployed to the WEBAPPS directory: \n ")

counter = 0
for remote_warfile_list in REMOTE_WARFILES:
    for deployed_hash in remote_warfile_list:
        print deployed_hash
        counter += 1
        if counter == (len(remote_warfile_list)):
            print("")
            counter = 0

