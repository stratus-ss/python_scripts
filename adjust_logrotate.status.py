#!/usr/bin/python
# Owner: Ovenss
# Date Created: July 9, 2013
# Primary Function: This will set all of the entries for logrotate to the same date.
#It expects to be passed in the file name (on RHEL based systems this is usually /var/lib/logrotate.status) 
#and a date you want to set as the last time logrotate ran. It will create a backup in /tmp

import os
import sys
import shutil

if len(sys.argv) < 2 or sys.argv[1] == "-h" or sys.argv[1] == "-help":
    print """
USAGE: This script expects to be run like this:

adjust_logrotate.status.py /var/lib/logrotate.status 2013-7-9 

A backup will be created in /tmp
"""
    sys.exit()

file_to_open = sys.argv[1]
date = sys.argv[2]
if "var" in file_to_open:
    backup_file = "/tmp/%s.bak" % file_to_open.split("/")[3]
else:
    backup_file = "/tmp/%s.bak" % file_to_open.split

#make the backup

shutil.copy(file_to_open, backup_file)

old_stdout = sys.stdout
sys.stdout = open(file_to_open, "w")
for line in open(backup_file).readlines():
    if "logrotate state" in line:
        print line,
    else:
        #The entries for logrotate are usually "/var/log/blah" 2013-7-9
        #So we want to print just the log name and insert out own date
        print line.split()[0], '%s' % date
