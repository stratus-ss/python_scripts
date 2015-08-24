#!/usr/bin/python
# This program was designed to clear all the cache automatically
# It will clear the akamai cache after a certain amount of time.
# It uses Akamai's new REST API and therefore requires the modules
# 'requests' and 'json' to work properly
# Written by Steve Ovens
# Created on: July 2014

import requests
import json
import sys
import datetime
import pytz

#Try except block that will bail if either of the inputs are missing or fail to open
try:
    user_file = open(sys.argv[1]).readlines()
    input_file = open(sys.argv[2]).readlines()
    #This section is a bit of a hack. I am testing to see if the second input file
    #Has the header indicating a previous purge request
    for line in input_file:
        if "PROGRESS URI" in line:
            #The status check contains the date of the original purge request
            status_check = str(line.split("on ")[1])
        if not line.startswith("#") and 'status_check' in globals():
            check_akamai_status = line.strip()
    #I am checking the list of global variables. If I cant find the check_akamai_status
    #assume that this is a new purge request and the second argument is the cp code list        
    if not 'check_akamai_status' in globals():
        cp_code_file = input_file
except:
    print("This script expects the user_file as the first argument and the cpcode file as the second argument")
    print("I.E. ./purge_akamai_restful.py user_file CB_uat_cpcodes")
    print("or ./purge_akamai_restful.py user_file /tmp/check_akamai_status")
    sys.exit()

#Gather the user name and password from the user_file
for line in user_file:
    if "username" in line:
        username = line.split("=")[1].strip()
    if "password" in line:
        password = line.split("=")[1].strip()

#Since most of the servers have been converted to GMT, report time in GMT
timezone = pytz.timezone("GMT")
todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d-%H:%M")

#These urls were obtained from https://api.ccu.akamai.com/ccu/v2/docs/index.html
akamai_base_url = "https://api.ccu.akamai.com"
akamai_clear_url = akamai_base_url + "/ccu/v2/queues/default"

credentials = (username, password)

#These headers are important as they declare the post type to be json which akamai requires
akamai_headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

###################### This is the purge section ######################
#Only do this if we have a cp_code_file

if 'cp_code_file' in globals():
    counter = 0
    cp_code_list = ''
    for individual_cpcode in cp_code_file:
        #Ignore commented lines
        if not individual_cpcode.startswith("#"):
            counter +=1
            #The rest API requires a comma separated list for CPCodes
            #This section makes sure that all but the last CPCode has a comma after it
            if counter < len(cp_code_file):
                cp_code_list += '"%s",' % individual_cpcode.strip()
            else:
                cp_code_list += '"%s"' % individual_cpcode.strip()
        
    #Construct the dict to send to akamai, it should look something like this:
    #{ "type" : "cpcode", "objects" : [ "334455" ] }
    data = '{"objects": [%s], "type": "cpcode"}' % cp_code_list

    #Send the purge request
    request_clear = requests.post(akamai_clear_url, data=data, auth=credentials, headers=akamai_headers)

    #I am turning the json object into a python dictionary so I can extract the Uri
    akamai_response_to_clear_request = json.loads(request_clear.text)

    print("Time until purge completion: " + str(akamai_response_to_clear_request["estimatedSeconds"]))
    print("Status: " + akamai_response_to_clear_request["detail"])
    akamai_purge_url = akamai_base_url + akamai_response_to_clear_request["progressUri"]

else:
    akamai_purge_url = akamai_base_url + check_akamai_status

#This step is not needed because all it does is checks the status.
#However it is a good way to verify that the request was sent and is being processed properly
request_status = requests.get(akamai_purge_url, auth=credentials, headers=akamai_headers)

response_to_status_request = json.loads(request_status.text) 
print("")
print("Submitted by: " + response_to_status_request["submittedBy"])
print("Purge ID: " + response_to_status_request["purgeId"])
print("Status: " + response_to_status_request["purgeStatus"])
print("")

if not 'cp_code_file' in globals():
    print("The original purge request was sent on: " + status_check)
    
if 'cp_code_file' in globals():
    #Create the file so that we can check later
    request_file = open("/tmp/check_akamai_status", "w")
    request_file.write("#This is the PROGRESS URI of the request sent on %s GMT\n" % todays_date)
    request_file.write(akamai_response_to_clear_request["progressUri"])
    request_file.close()
