#!/usr/bin/python
#this will run the reports on the remote server
import os
import sys
import paramiko
import getpass

try:
    reports = sys.argv[1]
    script = sys.argv[2]
except:
    print "This script expects the host list to be passed as the first argument and the script as the second"
    print "USAGE: ./push_component_script.py <host list> <script name>"
    sys.exit()

remote_script_location = "/usr/local/ops/scripts"

print "Pushing new script to remote locations"

current_user = getpass.getuser()

for host in open(reports).readlines():
    #Ignore blank spaces and comments in the host list
    if host.strip():
        if not host.startswith("#"):
            try:
                print "=============================="
                print host
                ssh = paramiko.SSHClient()
                ssh.load_system_host_keys()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(host.rstrip(), username = current_user)
                transport = ssh.get_transport()
                psuedo_tty = transport.open_session()
                psuedo_tty.get_pty()
                read_tty = psuedo_tty.makefile()
                psuedo_tty.exec_command("sudo mkdir -p %s; sudo chown -R :..linuxadmin %s; sudo chmod -R 775 %s " % (remote_script_location, remote_script_location, remote_script_location))
                print read_tty.read(),
                read_tty.close()
                psuedo_tty.close()
                ssh.close()
                print os.popen('rsync -av --progress %s %s:%s' % (script, host.rstrip(), remote_script_location)).read(),
                print "=============================="
            except Exception, e:
                print "There was a problem connecting to %s" % host
                print e
                pass

