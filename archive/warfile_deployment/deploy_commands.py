import os
import time
import subprocess

class CurlWarfile:

    def __init__(self, server_name, warfile_location, **tomcat_information):
        self.predeployed_warfile_hashes = []

        deployment_path = "path=/%s" % warfile_location.split("/")[-1].replace("#", "/").replace(".war", "")
        warfile_name = deployment_path.split("/")[-1]
        # A different curl command is required depending on whether the tomcat version is 6 or 7
        if tomcat_information['tomcat_version'] == "7":
            deploy_command = '/usr/bin/curl -u%s:%s --anyauth --upload-file %s ' \
                             '--url "http://%s:%s/manager/text/deploy?%s" -w "Deployed %s"' %\
                             (tomcat_information['tomcat_user'], tomcat_information['tomcat_password'],
                              warfile_location, server_name, tomcat_information['tomcat_port'], deployment_path,
                              warfile_name)
            undeploy_command = '/usr/bin/curl -u%s:%s --url "http://%s:%s/manager/text/undeploy?%s" -w "Deleted %s "' %\
                           (tomcat_information['tomcat_user'], tomcat_information['tomcat_password'], server_name,
                            tomcat_information['tomcat_port'], deployment_path, warfile_name)
        else:
            deploy_command = '/usr/bin/curl -u%s:%s --anyauth --form deployWar=@%s ' \
                             '--url http://%s:%s/manager/html/upload -w "Deployed %s "' %\
                             (tomcat_information['tomcat_user'], tomcat_information['tomcat_password'],
                              warfile_location, server_name, tomcat_information['tomcat_port'], warfile_name)
            undeploy_command = '/usr/bin/curl -u%s:%s --url "http://%s:%s/manager/html/undeploy?%s" -w \
                                "Deleted %s "' % (tomcat_information['tomcat_user'],
                                                  tomcat_information['tomcat_password'], server_name,
                                                  tomcat_information['tomcat_port'], deployment_path, warfile_name)
        self.undeploy_warfile(server_name=server_name, command=undeploy_command, warfile_name=warfile_name,
                              tomcat_port=tomcat_information['tomcat_port'])

        self.skip_server = self.deploy_warfile(server_name=server_name, command=deploy_command,
                                               warfile_name=warfile_name, tomcat_port=tomcat_information['tomcat_port'])

    def undeploy_warfile(self, **undeployment_arguments):
        print("")
        print("=======================================")
        print("Beginning Undeploy of old version of %s to %s on port %s" % (undeployment_arguments['warfile_name'],
                                                                            undeployment_arguments['server_name'],
                                                                            undeployment_arguments['tomcat_port']))
        print("")
        self.check_curl_success(undeployment_arguments['server_name'], undeployment_arguments['command'])

    def deploy_warfile(self, **deployment_arguments):
        print("")
        print("=======================================")
        print("Beginning Deploy of %s to %s on port %s" % (deployment_arguments['warfile_name'],
                                                           deployment_arguments['server_name'],
                                                           deployment_arguments['tomcat_port']))
        did_deployment_fail = self.check_curl_success(deployment_arguments['server_name'],
                                                      deployment_arguments['command'])
        if did_deployment_fail:
            retry_count = 0
            while did_deployment_fail:
                print("Curl Deployment failed, retrying in 5 seconds. This is attempt number %s" % (retry_count + 1))
                time.sleep(5)
                retry_count += 1
                if retry_count > 2:
                    did_deploy_fail = self.check_curl_success(deployment_arguments['server_name'],
                                                              deployment_arguments['command'])
                    print("I was unable to reach %s. Deployment failed" % deployment_arguments['server_name'])
                    return(True)

    def check_curl_success(self, server_name, command):
        curl_output_line_number = 0
        # Curl uses stderr to show its progress so subprocess is required to capture this output
        for curl_output_line in subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                                 stderr=subprocess.PIPE, shell=True).stderr.read().split("\n"):
            curl_output_line_number += 1
            print(curl_output_line.split("\n")[0].split("curl: ")[0])
            if "curl" in curl_output_line:
                print(curl_output_line.split("\n")[0].split("curl: ")[1])
                print("")

            if curl_output_line_number == 3:
                # counter refers to the line number of the output that the Xferd stats are printed to
                # Because the curl command constantly updates this line until the transfer is complete
                # The output is simply appended to the list. Therefore the most reliable way to determine
                # Whether the file has transfered is to get the -8th column which is labeled as '% Xferd'
                if "refused" in curl_output_line or curl_output_line == "":
                    print("The connection to the server %s was refused... is the port closed?\n\n" % server_name)
                    curl_fail = True
                    return(curl_fail)
                if int(curl_output_line.split("\n")[0].rstrip().split()[-8]) != 100:
                    curl_fail = True
                else:
                    curl_fail = False
                return curl_fail


class WhichLocalWarfilesToDeploy:

    def __init__(self, warfile_list, warfile_path, server_name_list):
        deploy_these_files = []
        self.component_to_server_map = {}
        for warfile in warfile_list:
            full_path_to_warfile = warfile_path + os.sep + warfile
            if os.path.exists(full_path_to_warfile):
                deploy_these_files.append(full_path_to_warfile)
        for server in server_name_list:
            self.component_to_server_map[server] = deploy_these_files


class DetermineHowToRestartTomcat:

    def __init__(self, tomcat_script_location, server_name):
        self.tomcat_script_location = tomcat_script_location
        if "init" in self.tomcat_script_location:
            if len(server_name.split("-")[0]) > 2:
                self.restart_command = self.tomcat_restart()
            else:
                self.stop_command = self.tomcat_stop()
        else:
            self.legacy_command = self.tomcat_legacy()

    def tomcat_restart(self):
        return("sudo nohup %s restart >/dev/null 2>&1" % self.tomcat_script_location)

    def tomcat_stop(self):
        return("sudo nohup %s stop >/dev/null 2>&1; sleep 10; sudo nohup %s start >/dev/null 2>&1" %
               (self.tomcat_script_location, self.tomcat_script_location))

    def tomcat_legacy(self):
        return("sudo nohup %s > /dev/null 2>&1" % self.tomcat_script_location)


class DeployETLs:

    pass
