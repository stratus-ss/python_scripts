# Owner: Steve Ovens
# Date Created: Aug 2015
# Primary Function: This is a file intended to be supporting functions in various scripts
# This file will do nothing if run directly

import sys

class textColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    HIGHLIGHT = '\033[96m'


class ImportHelper:

    """ This class simply allows for the dynamic loading of modules which are not apart of the stdlib.
     It specifies which module cannot be imported and provides the proper pip install command as output to the user.
    """

    @staticmethod
    def import_error_handling(import_this_module, modulescope):
        try:
            exec("import %s " % import_this_module) in modulescope
        except ImportError:
            print("This program requires %s in order to run. Please run" % import_this_module)
            print("pip install %s" % import_this_module)
            print("To install the missing component")
            sys.exit()


class DictionaryHandling:

    """ This class handles the adding to, and output formatting of dictionaries
    """

    @staticmethod
    def add_to_dictionary(dictionary, name_of_server, component, value):
        if name_of_server in dictionary:
            dictionary[name_of_server][component] = value
        else:
            dictionary[name_of_server] = {component: value}

    @staticmethod
    def format_dictionary_output(*args):
        temporary_dict = {}
        temp_list = []
        # This populates a temporary dictionary with the contents of all the dictionaries that have been passed in
        # as arguments
        for count, incoming_dictionary in enumerate(args):
            for server_name in incoming_dictionary.keys():
                for component_key in incoming_dictionary[server_name]:
                    DictionaryHandling.add_to_dictionary(temporary_dict, server_name, component_key,
                                                         incoming_dictionary[server_name][component_key])
        # This section prints the server name as a heading in the output
        for server_name in temporary_dict.keys():
            print("\n\t" + textColors.OKBLUE + server_name + textColors.ENDC)
            for incoming_dictionary in temporary_dict[server_name]:
                # I am turning the dictionaries into a list so that I can sort the output
                temp_var = server_name + " " + incoming_dictionary + " : " + \
                           str(temporary_dict[server_name][incoming_dictionary])
                temp_list.append(temp_var)
            temp_list.sort()

            # All dictionaries should have either True or False in order to be colourized
            # True will be coloured Green, False will be Red. Anything else will be highlighted
            for output in temp_list:
                if server_name in output.split()[0]:
                    if "True" in output:
                        # If the file has been modified mark it yellow as we cannot know whether it is correctly
                        # modified or not
                        if "sum" in output:
                            output = " :".join(output.split(":")[:-1])
                            print(textColors.WARNING + "\t\t" + " ".join(output.split()[1:]) + textColors.ENDC)
                        else:
                            print(textColors.OKGREEN + "\t\t" + " ".join(output.split()[1:]) + textColors.ENDC)
                    elif "False" in output or "None" in output or "" in output.split()[:-1] or "Missing" in output:
                        # If the file hasn't been modified, we want to throw the fail colour because default
                        # values will not work for OSE
                        if "sum" in output:
                            output = " :".join(output.split(":")[:-1])
                        print(textColors.FAIL + "\t\t" + " ".join(output.split()[1:]) + textColors.ENDC)
                    else:
                        print("\t\t" + " ".join(output.split()[1:]) + textColors.ENDC)
