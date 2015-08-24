#!/usr/bin/env python
# Owner: Mohamed Elsakhawy

# Date Created: July 8th 2013

# Primary Function: Script used to compete the sizes of two files , one is on Nissan SFTP and the other one is a local one

# Usage as follows
#./python_file_size_compare_sftp.py  SFTP_IP REMOTE_FILE_PATH LOCAL_FILE_PATH
# The script has two values in the exit codes : 10 for matching files and 15 for non matching files
import sys, paramiko, os

hostname = sys.argv[1]
remote_path = sys.argv[2]
local_path = sys.argv[3]

username = "adfeed"
password = "7U$K&^-o&eNh"
port = 22
try:
    t = paramiko.Transport((hostname, port))
    t.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(t)
    remote_size = sftp.stat(remote_path).st_size
    local_size = os.path.getsize(local_path)
    if remote_size == local_size:
        print "match"
        # Exit with exit code 10
        sys.exit(10)
    else:
        print "no match"
        # Exist with Exit Code 15
        sys.exit(15)

finally:
    t.close()
