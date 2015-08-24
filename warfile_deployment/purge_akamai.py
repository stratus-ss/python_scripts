class PurgeAkamai:
    """ This program was designed to clear all the cache automatically
     It will clear the akamai cache after a certain amount of time.
     It uses Akamai's new REST API and therefore requires the modules
     'requests' and 'json' to work properly"""

    def __init__(self, akamai_cred_file, cpcode_file):
        import requests
        import json
        import sys
        import datetime
        import pytz

        # Try except block that will bail if either of the inputs are missing or fail to open
        try:
            user_file = open(akamai_cred_file).readlines()
            cp_code_file = open(cpcode_file).readlines()
            # This section is a bit of a hack. I am testing to see if the second input file
            # Has the header indicating a previous purge request
        except:
            print("This script expects the user_file as the first argument and the cpcode file as the second argument")
            print("I.E. ./purge_akamai_restful.py user_file CB_uat_cpcodes")
            sys.exit()

        # Gather the user name and password from the user_file
        for line in user_file:
            if "username" in line:
                username = line.split("=")[1].strip()
            if "password" in line:
                password = line.split("=")[1].strip()

        # Since most of the servers have been converted to GMT, report time in GMT
        timezone = pytz.timezone("GMT")
        todays_date = datetime.datetime.now(timezone).strftime("%Y-%m-%d-%H:%M")

        # These urls were obtained from https://api.ccu.akamai.com/ccu/v2/docs/index.html
        akamai_base_url = "https://api.ccu.akamai.com"
        akamai_clear_url = akamai_base_url + "/ccu/v2/queues/default"

        credentials = (username, password)

        # These headers are important as they declare the post type to be json which akamai requires
        akamai_headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

        ###################### This is the purge section ######################
        # Only do this if we have a cp_code_file
        counter = 0
        # We need to subtract the number of lines with comments from the overall number of lines
        # in the config so that we can accurately count the CP codes
        # This could
        comment_counter = 0
        cp_code_list = ''
        for individual_cpcode in cp_code_file:
            if individual_cpcode.startswith("#"):
                comment_counter +=1
            else:
                if individual_cpcode[0].isdigit():
                    # Ignore trailing comments
                    individual_cpcode = individual_cpcode.split("#")[0]
                    counter +=1
                    #The rest API requires a comma separated list for CPCodes
                    #This section makes sure that all but the last CPCode has a comma after it
                    if counter < len(cp_code_file) - comment_counter:
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

        #This step is not needed because all it does is checks the status.
        #However it is a good way to verify that the request was sent and is being processed properly
        request_status = requests.get(akamai_purge_url, auth=credentials, headers=akamai_headers)

        response_to_status_request = json.loads(request_status.text)
        print("")
        print("Submitted by: " + response_to_status_request["submittedBy"])
        print("Purge ID: " + response_to_status_request["purgeId"])
        print("Status: " + response_to_status_request["purgeStatus"])
        print("")

        #Create the file so that we can check later
        request_file = open("/tmp/check_akamai_status", "w")
        request_file.write("#This is the PROGRESS URI of the request sent on %s GMT\n" % todays_date)
        request_file.write(akamai_response_to_clear_request["progressUri"])
        request_file.close()
