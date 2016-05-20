#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: March 4, 2015
# Primary Function: This script will move the mysql_secret file (generated at
# installation) to a location specified by the DBAs
import os
import shutil
import grp, pwd

create_these_directories = ["/DATA/backups", "/DATA/logs/mysql", "/DATA/tmp", "/usr/local/dba/scripts"]
DBA_specified_mysql_secret_location = "/DATA/mysql_secret"
remove_this_my_cnf = "/etc/my.cnf"
live_my_cnf = "/usr/my.cnf"
backup_my_cnf = "/usr/my.cnf.bak"
original_mysql_secret_file = "/root/.mysql_secret"
mysql_uid = pwd.getpwnam("mysql").pw_uid
mysql_gid = grp.getgrnam("mysql").gr_gid

def create_directories():

    # Create the directories required by the DBAs
    for directory in create_these_directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

        os.chmod(directory, 0770)
        os.chown(directory, mysql_uid, mysql_gid)

def move_mysql_secret():

    # If the mysql_secret doesn't exist in DBA_specified_mysql_secret_location
    # check the default location, if the file exists, move it to the new location
    # Change the permissions to 'mysql'
    if not os.path.isfile(DBA_specified_mysql_secret_location):
        if os.path.isfile(original_mysql_secret_file):
            print("moving mysql_secret to /DATA")
            shutil.move(original_mysql_secret_file, DBA_specified_mysql_secret_location)
            print("Changing the ownership of %s" % DBA_specified_mysql_secret_location)
            os.chmod(DBA_specified_mysql_secret_location, 0600)
            os.chown(DBA_specified_mysql_secret_location, mysql_uid, mysql_gid)
        else:
            print("%s is missing" % original_mysql_secret_file)
    else:
        print("%s already exists!" % DBA_specified_mysql_secret_location)

def create_my_cnf_backup():

    shutil.copy2(live_my_cnf, backup_my_cnf)

def setup_my_cnf():

    # This function makes sure that we only have one my.cnf
    # and the /usr/my.cnf is the only one that exists
    if os.path.isfile(remove_this_my_cnf):
        print("Removing %s" % remove_this_my_cnf)
        os.remove(remove_this_my_cnf)
    # Create a backup of /usr/my.cnf and make mysql the owner
    if os.path.isfile(live_my_cnf):
        if os.path.isfile(backup_my_cnf):
            print("%s already exists!" % backup_my_cnf)
            overwrite_my_cnf = raw_input("Are you sure you want to overwrite this? (y/n)")
            if "y" in overwrite_my_cnf.lower():
                print("Overwriting %s" % backup_my_cnf)
                create_my_cnf_backup()
        else:
            print("Creating backup of %s to %s" % (live_my_cnf, backup_my_cnf))
            create_my_cnf_backup()
        os.chown(live_my_cnf, mysql_uid, 0)

create_directories()
move_mysql_secret()
setup_my_cnf()

