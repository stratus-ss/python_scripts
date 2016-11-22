import ConfigParser
import os.path
import time
import getpass
import subprocess
import argparse
import shlex
import re
import urlparse
import tempfile

import log

class textColours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    HIGHLIGHT = '\033[96m'


def append_to_single_dimension_dict(dictionary, name_of_component, version):
    if name_of_component in dictionary:
        dictionary[name_of_component].append(version)
    else:
        dictionary[name_of_component] = [version]


def append_to_dual_dimension_dict(dictionary, name_of_component, environment_name, version):
    if name_of_component in dictionary:
        dictionary[name_of_component][environment_name] = version
    else:
        dictionary[name_of_component] = {environment_name: version}



