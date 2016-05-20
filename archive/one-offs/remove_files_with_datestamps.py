#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: Apr 2, 2015
# Primary Function: This script assumes that files have datestamps in the file name
#                   in order to sort the files properly. It will then remove all
#                   files up to the number specified. I.E. if you call the script
#                   with --keep-files 25, it will remove all but 25 of the most
#                   recent files

import os
import sys
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-k", "--keep-files", dest="keep_this_number_of_files",
                  help="How many files to keep")
parser.add_option("-d", "--directory-to-purge", dest="purge_this_dir",
                  help="Specify which directory to clean")
(options, args) = parser.parse_args()

if options.keep_this_number_of_files is None:
    print("The number of files to keep has not been specified")
    parser.print_help()
    sys.exit()

if options.purge_this_dir is None:
    print("The directory you want to clean has not been specified")
    parser.print_help()
    sys.exit()


directory_to_purge = options.purge_this_dir
number_of_files_in_dir = len([name for name in os.listdir(directory_to_purge) \
                        if os.path.isfile(os.path.join(directory_to_purge, name))])
number_of_files_to_keep = int(options.keep_this_number_of_files)
list_of_files = os.listdir(directory_to_purge)
list_of_files.sort()

print("Starting purge of %s" % directory_to_purge)
print("Keeping latest files: %s " % number_of_files_to_keep)
for files in list_of_files[:-number_of_files_to_keep]:
    full_path_to_file = directory_to_purge + os.sep + files
    os.unlink(full_path_to_file)

print("Purge of %s completed" % directory_to_purge)
