#!/usr/bin/python
# Owner: Steve Ovens
# Date Created: August 2015
# Primary Function: This is intended to be used as part deploy_components.py.
# However, this nagios module can be run as a standalone script as well
# Log Location: Logging dumps to stdout
# Script notes: Adds/removes a server from down time in nagios

import requests
import calendar
import time
import datetime
import re


class DownTimeHandler:

    """This Class does not require instantiation as both functions within are static.
    The purpose of this class is to interact with Nagios' external command module which is exposed via port 80
    on each nagios server. Both static methods take in an artbitrary number of of keyword arguments in order to
    provide more flexibilty in the future. At the time of writing it only expects server name, hostname/host list,
    and a username"""

    @staticmethod
    def put_host_in_downtime(**nagios_information ):
        write_downtime_id_here = "/tmp/%s.downtimeID" % nagios_information['hostname'].lower()
        downtime_id = calendar.timegm(time.gmtime())
        downtime_start_time = datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")
        downtime_end_time = (datetime.datetime.now().strptime(downtime_start_time, "%m-%d-%Y %H:%M:%S") + \
                             datetime.timedelta(minutes=int(nagios_information['minutes_in_downtime'])))\
                             .strftime("%m-%d-%Y %H:%M:%S")
        downtime_request = "http://%s:80/nagios/cgi-bin/cmd.cgi?cmd_typ=55&cmd_mod=2&host=%s&com_author=%s&" \
                           "com_data=Downtime-Script (ID:%s)&trigger=0&start_time=%s&end_time=%s" \
                           "&fixed=1&childoptions=1&btnSubmit=Commit" % (nagios_information['nagios_server'],
                                                                         nagios_information['hostname'],
                                                                         nagios_information['username'],
                                                                         downtime_id,
                                                                         downtime_start_time, downtime_end_time)
        send_the_request = requests.get(downtime_request, auth = (nagios_information['username'],
                                                                  nagios_information['password']))
        print(send_the_request)
        if send_the_request.status_code == 200:
            print("The request has been accepted by the nagios server for %s." % nagios_information['hostname'])
        else:
            print("There was a problem with the request. It was sent but did not return the expected return status")
            print("Try putting this url into your browser to debug further")
            print(downtime_request)
        id_file = open(write_downtime_id_here, 'a')
        id_file.write(str(downtime_id))
        id_file.write("\n")
        id_file.close()

    @staticmethod
    def remove_host_from_downtime(**nagios_information):
        import sys
        import fileinput
        # This regex will find any table data that has only digits in it.
        # This is presumed to be the nagios downtime ID
        regex = ur"<td CLASS='downtime\w+'>(\d+)</td>"
        find_all_hosts_in_downtime = "http://%s:80/nagios/cgi-bin/extinfo.cgi?type=6" % \
                                     nagios_information['nagios_server']
        downtime_timestamp_file = "/tmp/%s.downtimeID" % nagios_information['hostname'].lower()
        # This will get the last line of the file which is presumably the most recent downtime ID and it strips the
        # newline character
        try:
            most_recent_downtime_timestamp = open(downtime_timestamp_file).readlines()[-1].strip()
        except IndexError:
            print("There does not appear to be a downtime ID in %s" % downtime_timestamp_file)
        send_the_request_for_downtime_ids = requests.get(find_all_hosts_in_downtime,
                                                         auth = (nagios_information['username'],
                                                                 nagios_information['password']))
        try:
            for lines in send_the_request_for_downtime_ids._content.split("\n"):
                if most_recent_downtime_timestamp in lines:
                    downtime_id_from_nagios = re.findall(regex, lines)[0]
            print("The downtime ID is: %s" % downtime_id_from_nagios)
        except UnboundLocalError:
            print("There was a problem retrieving the downtime ID from nagios. Without this I cannot complete your"
                  " request")
            print("I could not find a downtime id in the temporary file or in the nagios comments")
            sys.exit()
        clear_downtime_request = "http://%s:80/nagios/cgi-bin/cmd.cgi?cmd_typ=78&cmd_mod=2&down_id=%s&btnSubmit=Commit"\
                             % (nagios_information['nagios_server'], downtime_id_from_nagios)
        send_the_clear_request = requests.get(clear_downtime_request, auth = (nagios_information['username'],
                                                              nagios_information['password']))
        if send_the_clear_request.status_code == 200:
            print("The request has been accepted by the nagios server for %s." % nagios_information['hostname'])
            # This removes the last id from the file so that if the host has multiple downtime metrics, the script can
            # be used to clear all of them
            for line in fileinput.FileInput(downtime_timestamp_file, inplace = 1):
                if most_recent_downtime_timestamp in line:
                    pass
                else:
                    print(line),


if __name__ == "__main__":

    def handle_multiple_hosts(downtime_option):

        for host in open(options.list_of_hosts).readlines():
                if host.strip():
                    # This section ignores any comments in the file
                    if host.startswith("#"):
                        pass
                    else:
                        if downtime_option == "add":
                            DownTimeHandler.put_host_in_downtime(username=options.username, password=get_password,
                                                                 nagios_server=options.nagios_server,
                                                                 hostname=host.split()[0],
                                                                 minutes_in_downtime=options.amount_of_downtime)
                            # Since the id matching is done via time stamp, we need to introduce a slight delay or else
                            # each server ends up with the same or almost the same id
                            time.sleep(1)
                        else:
                            DownTimeHandler.remove_host_from_downtime(username=options.username, password=get_password,
                                                                      nagios_server=options.nagios_server,
                                                                      hostname=host.split()[0])

    from optparse import OptionParser
    import getpass
    import sys

    parser = OptionParser()
    parser.add_option('-H', '--host', dest='hostname', help='Host to put in down time')
    parser.add_option('-L', '--host-list', dest='list_of_hosts', help='List of hosts to put in down time')
    parser.add_option('-o', '--option', dest='downtime_option', help='Add or remove host from nagios downtime')
    parser.add_option('-n', '--nagios-server', dest='nagios_server', help='nagios server fqdn')
    parser.add_option('-t', '--time', dest='amount_of_downtime', help='Duration of downtime (in minutes)')
    parser.add_option('-u', '--username', dest='username', help='username')

    (options, args) = parser.parse_args()

    if options.username is None:
        print("No username provided. You will not be able to authenticate without a username")
        parser.print_help()
        sys.exit()

    if options.nagios_server is None:
        print("Nagios server specified. Which server do you wish to interact with?")
        parser.print_help()
        sys.exit()

    if options.downtime_option is None:
        print("Are you putting a server in downtime or making it active? You have not specified")
        parser.print_help()
        sys.exit()

    if options.hostname is None and options.list_of_hosts is None:
        print("You didn't provide a list of hosts or a single host. Which server(s) need to be in down time")
        parser.print_help()
        sys.exit()

    print("Please enter the password for the nagios server:")
    get_password = getpass.getpass()

    if "add" in options.downtime_option:
        if options.amount_of_downtime is None:
            print("Amount of downtime not specified. Please use the web UI if you wish to put a server into downtime"
                  " for an indefinite time period")
            parser.print_help()
            sys.exit()

        # If there is no host list passed in, just run a single host else loop over the list and ignore
        if options.list_of_hosts is None:
            DownTimeHandler.put_host_in_downtime(username=options.username, password=get_password,
                                                 nagios_server=options.nagios_server, hostname=options.hostname.upper(),
                                                 minutes_in_downtime=options.amount_of_downtime)
        else:
            handle_multiple_hosts("add")
    else:
        if options.list_of_hosts is None:
            DownTimeHandler.remove_host_from_downtime(username=options.username, password=get_password,
                                                      nagios_server=options.nagios_server,
                                                      hostname=options.hostname.upper())
        else:
            handle_multiple_hosts("remove")