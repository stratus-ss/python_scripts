#!/usr/bin/env python
# This script should be used to clean up deployer pods that are left behind after a failed deployment
# It will read a file which has one deployer pod per line, it will then attempt to remove said pod

import os
import sys
from tools import ssh, common
import openshift.cluster
import argparse
from tools.common import textColours

parser = argparse.ArgumentParser(description='%s    destroys any deployer pods left behind by a failed deploy'
                                                 '%s' % (textColours.BOLD, textColours.ENDC),
                                 epilog='%s \nSample usage: %s --cleanup-file /tmp/deployer_cleanup '
                                        '--env-file conf/env/tec-qa.env.conf \n%s' %
                                        (textColours.HIGHLIGHT, sys.argv[0], textColours.ENDC),
                                 formatter_class=argparse.RawTextHelpFormatter)

parser.add_argument('--cleanup-file', action='store', dest='cleanup_file',
                    help='A file with a list of deployer pods to remove')

parser.add_argument('--env-file', action='store', dest='env_file',
                    help='The config file for the environment', required=True)

options = parser.parse_args()

if __name__ == "__main__":

    if options.cleanup_file is None:
        cleanup_file = "/tmp/deployer_cleanup"
    else:
        cleanup_file = options.cleanup_file

    # Setup the ssh connections
    os.environ['ENV_FILE'] = options.env_file
    user = common.get_stack_user()
    gateway_ip = common.get_gateway_ip()
    env_options = common.get_env_options()
    gateway_session = ssh.SSHSession(gateway_ip, user)

    for deployer_pod_line in open(cleanup_file).readlines():
        if "deploy" in deployer_pod_line.split("-")[-1]:
            component_name = deployer_pod_line.split(" : ")[0]
            deployer_pod_name = deployer_pod_line.split(" : ")[1]
            os_master_session = openshift.cluster.get_master_session(gateway_session, component_name)
            destroy_command = "sudo oc delete pod %s" % deployer_pod_name
            destroy_pod_output = os_master_session.get_cmd_output(destroy_command)