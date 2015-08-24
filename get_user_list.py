#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: Jan 29, 2014
# Primary Function: Takes a file with a list of groups as input and produces the users in that group as out in a file

import grp
import os
import sys


old_stdout = sys.stdout

try:
    files = open(sys.argv[1]).readlines()
except:
    print "USAGE: ./get_user_list.py <file with group names>"
    sys.exit()

sys.stdout = open("group_memberships.out", "w")    
all_groups = []

for x in files:
    all_groups.append(x.replace("\\", "").replace("..", "").replace("%", "").rstrip())

group_users_list = []
for group in all_groups:
    for group_records in grp.getgrall():
        if group.lower() in group_records[0].lower():
            print group_records[0]
            print ""
            group_users_list = group_records[3]
            group_users_list.sort()
            for user in group_users_list:
                print user
            print "========================"
            
