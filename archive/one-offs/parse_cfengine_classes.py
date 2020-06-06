#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: 19 June 2015
# Primary Function:
# This script checks the promises.cf and env_promises.cf file for environments
# It then parses the output and prints out a readable association between the
# environment types, server classifications and server name.
# i.e. the promises.cf file has "f_gmu_pr" this is the environment type.
# the env_promises file for f_gmu_pr is then parsed and returns the class (log_servers)
# as well as the the server names "classified" for them
# It can take in optional arguments to search for specific hosts and specify location
# of the master_files directory


import re
import os
import sys
from optparse import OptionParser

parser = OptionParser()
parser.add_option('-s', dest='server_to_search_for', help='Use this flag to specify a server to search for to narrow results')
parser.add_option('-m', dest='master_files_directory', help='OPTIONAL: Use this flag to specify the location of the master_files dir')
(options, args) = parser.parse_args()

if options.server_to_search_for is None:
    print("Please specify what to output")
    print("Options: all or hostname")
    parser.print_help()
    sys.exit()

# These are the default options

if options.master_files_directory is None:
    master_files_directory = "/code/bzr/cfengine/master_files"
else:
    master_files_directory = options.master_files_directory

# This regex matches anything between 'or =>' and '};'
regex_to_match_classified_hosts = 'or =>(.*?)};'

env_promises_file = "env_promises.cf"
promises_file = master_files_directory + os.sep + "promises.cf"


def find_server_names(file_to_parse, regex):
    # This function is used to extract the server names from the classification blocks in cfengine
    list_of_servers = []
    for server in re.findall(regex, open(file_to_parse).read(), re.S):
        # This funkiness is removing white spaces, brackets and braces
        server_names = re.sub(r'\s+', '', server.replace('"', "").replace(")", "").replace("{", "").strip())
        server_list = server_names.split()
        counter = 0
        # I want to remove any of the hosts which have been commented out
        # Currently that means that any host that starts with #classify needs to be popped out of the list
        for classified_server in server_list:
            if "#" in classified_server:
                server_list.pop(counter)
            counter +=1
        server_names = " ".join(server_list).replace("classify(", "")
        list_of_servers.append(server_names)
    return(list_of_servers)

def find_classification_type(file_to_parse):
    # Classification type could either be the class itself (i.e. xws_servers) or it could be
    # the definition as found in the promises.cf file (i.e. f_gmu_pr). This function parses both
    list_of_classifications = []
    try:
        for line in open(file_to_parse).readlines():
            if "or =>" in line and "#" not in line:
                classification_type = line.split(" or")[0].strip().replace('"', '')
                list_of_classifications.append(classification_type)
    except IOError:
        print("Could not find %s...skipping" % file_to_parse)
    return(list_of_classifications)

list_of_environments = find_classification_type(promises_file)

# This dictionary is a multi-dimensional array (or nested dictionary if you prefer)
# Its' primary key is the definition as found in the promises.cf file
# The nested key is the class type (i.e. xws_servers)
# The nested value is the server(s) which belong to the class type
server_classifications_dict = {}

for environment in list_of_environments:
    try:
        search_this_file = master_files_directory + os.sep + environment + os.sep + env_promises_file
        cfengine_classification_type = find_classification_type(search_this_file)
        servers_that_match_cfengine_classification = find_server_names(search_this_file,
                                                                       regex_to_match_classified_hosts)
        counter = 0
        for classification in cfengine_classification_type:
            if environment in server_classifications_dict:
                server_classifications_dict[environment][cfengine_classification_type[counter]] = \
                    servers_that_match_cfengine_classification[counter]
            else:
                server_classifications_dict[environment] = {cfengine_classification_type[counter]:
                                                            servers_that_match_cfengine_classification[counter]}
            counter += 1
    except IOError:
        # If an IOError is encountered, it is because there are servers and/or definitions which exist
        # in the promises.cf file but don't appear to have an associated env_promises file
        # We are passing over this error because its handled inside of the find_classification_type_function
        pass


print("")
previous_environment = ""


if options.server_to_search_for.lower() == "all":
    for environment, classifications in server_classifications_dict.iteritems():
        print("%s has the following classes:" % environment)
        for classes, servers in server_classifications_dict[environment].iteritems():
            print("    %s:    %s" % (classes, servers))
        print("")
else:
    for environment, classifications in server_classifications_dict.iteritems():
        for classes, servers in server_classifications_dict[environment].iteritems():
            if options.server_to_search_for.lower() in servers:
                if previous_environment != environment:
                    print("")
                    print("%s has the following classes:" % environment)
                print("    %s:    %s" % (classes, servers))
                previous_environment = environment
