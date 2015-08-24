#!/usr/bin/python
#This script removes all the blanks from a file
import fileinput
import sys
import os

if len(sys.argv) < 2 or sys.argv[1] == "-h":
    print """
    This script will remove any blank lines from a file
    It expects to be used in the following method:
    
    remove_blank_lines.py <file to edit>
    """
    exit()


file_to_edit = sys.argv[1]

os.popen("cp %s	/tmp" %	file_to_edit)
print "copying %s to /tmp" % file_to_edit

for line in fileinput.FileInput(file_to_edit, inplace = 1):
    if line.isspace():
        pass
    else:
        print line,

