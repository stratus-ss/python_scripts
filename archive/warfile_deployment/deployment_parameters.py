# Owner: Steve Ovens
# Date Created: Aug 2015
# Primary Function: This is a supporting function to parse configuration files for deploy_components.py
# this file will do nothing if run directly

class ParseDeploymentParameters:
    """ This class simply does the parsing of the config file
    """

    def __init__(self, config_file):
        # These are being initialized blank so that they are over written each time this function is called
        # This is what allows multiple configs to be passed in
        self.warfile_list = []
        self.server_list = []
        self.incoming_config_file = config_file
        for line in open(self.incoming_config_file).readlines():
            # Ignore blank spaces, this will only process lines with which have text
            if line.strip():
                if not line.startswith("#"):
                    value = line.split("=")[1].strip()
            if line.startswith("PATH_TO_WARFILE"):
                self.warfile_path = value
            elif line.startswith("OLD_WARFILE_PATH"):
                self.old_warfile_path = value
            elif line.startswith("WARFILE_NAME"):
                self.warfile_list.append(value)
            elif line.startswith("SERVERS"):
                self.server_list.append(value)
            elif line.startswith("TOMCAT_PORT"):
                self.tomcat_port = value
            elif line.startswith("RESTART_TOMCAT"):
                self.restart_tomcat = value
            elif line.startswith("TOMCAT_VERSION"):
                self.tomcat_version = value
            elif line.startswith("SSH_USER"):
                self.ssh_user = value
            elif line.startswith("MOVE_FILE"):
                self.move_file = value
            elif line.startswith("TOMCAT_RESTART_SCRIPT"):
                self.tomcat_restart_script = value
            elif line.startswith("TOMCATUSER"):
                self.tomcatuser = value
            elif line.startswith("TOMCATPASS"):
                self.tomcatpass = value
            elif line.startswith("NAGIOS_PUT_IN_DOWNTIME"):
                self.nagios_put_in_downtime = value
            elif line.startswith("NAGIOS_REMOVE_FROM_DOWNTIME"):
                self.nagios_remove_from_downtime = value
            elif line.startswith("NAGIOS_DOWNTIME_REMOVAL_DELAY"):
                self.nagios_downtime_removal_delay = value
            elif line.startswith("NAGIOS_DOWNTIME_DURATION"):
                self.nagios_downtime_duration = value
            elif line.startswith("NAGIOS_SERVER"):
                self.nagios_server = value
            elif line.startswith("NAGIOS_USER"):
                self.nagios_user = value
            elif line.startswith("NAGIOS_PASSWORD"):
                self.nagios_password = value
            elif line.startswith("TOMCAT_DIRECTORY"):
                self.tomcat_directory = value
            elif line.startswith("CPCODE_FILE"):
                self.cpcode_file = value
            elif line.startswith("AKAMAI_CRED_FILE"):
                self.akamai_cred_file = value
