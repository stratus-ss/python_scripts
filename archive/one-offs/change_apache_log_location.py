#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: March 10, 2015
# Primary Function: replace the default log location in apache
# Log Location:  no logs

import fileinput
import sys
import os
if len(sys.argv) < 2 or sys.argv[1] == "-h":
    print """
    This script will change the default log location
    for apache.
     
    change_apache_log_location.py <file to edit>
    """
    exit()
file_to_edit = sys.argv[1]
os.popen("cp %s    /tmp" %    file_to_edit)
print "copying %s to /tmp" % file_to_edit
for line in fileinput.FileInput(file_to_edit, inplace = 1):
    if "logs" in line:
        if "etc" in line:
            print(line.replace("/etc/httpd/logs", "/DATA/logs/apache")) 
        else:
            print(line.replace("logs", "/DATA/logs/apache"))
    else:
        print line,

