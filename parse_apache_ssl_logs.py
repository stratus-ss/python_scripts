#!/usr/bin/python
import sys
import urllib
import time

try:
    ssl_log = open(sys.argv[1]).readlines()
except:
    print("USAGE: parse_apache_ssl_logs.py <path to ssl log>")
    sys.exit()


ip_list = []
unique_ip = []
unique_countries = {}
request_summary = {}
unique_summary = []
all_summary = []
display_unique_ips = raw_input("Display unique IP list? (y/n): ")
display_request_path = raw_input("Display unique request paths? (y/n): ")
display_request_summary = raw_input("Display request path counts? (y/n): ")
display_country_summary = raw_input("Resolve IPs to a specific country? (y/n): ")
print("\n")

for line in ssl_log:
    ip = line.split()[0]
    ip_list.append(ip)
    http_request = line.split(' "')[1].split()[1].split(" HTTP")[0]
    all_summary.append(http_request)
    if not ip in unique_ip:
        unique_ip.append(ip)
    if not http_request in unique_summary:
        unique_summary.append(http_request)

if "y" in display_request_path.lower():
    for line in unique_summary:
        summary_count = all_summary.count(line)
        if line in request_summary:
            request_summary[line] += summary_count
        else:
            request_summary.update({line: summary_count})
        print(line)
    print("\n")
    if "y" in display_request_summary.lower():
        for requests, request_counts in request_summary.iteritems():
            print(("".join('%s   ====   %s' % (requests, request_counts))))
    print("\n")

if "y" in display_unique_ips.lower():
    ask_again = raw_input("There are %s unique ips, are you sure you want to display these? " % len(unique_ip))
    if "y" in ask_again.lower():
        unique_ip.sort()
        for ip in unique_ip:
            print(ip)
        print("\n")


##Include response size which is the last column... ask for the user if they want response size... if yes search for files greater
##Then what the user indicates. Also note the largest response size

if "y" in display_country_summary.lower():
    ask_again = raw_input("This will take approximately %s seconds to complete, do you want to resolve IPs? " % (len(unique_ip) * 2))
    if "y" in ask_again.lower():
        for ip_number in unique_ip:
                response = urllib.request.urlopen('http://api.hostip.info/get_html.php?ip=%s&position=true' % ip_number).read()
                for line in response.split("\n"):
                    if "Country:" in line:
                        country_name = line.split()[1].strip("(")
                        country_count = ip_list.count(ip_number)
                        if country_name in unique_countries:
                            unique_countries[country_name] += country_count
                        else:
                            unique_countries.update({country_name: country_count})
                time.sleep(2)
    print(unique_countries)


display_IP_count = raw_input("Count the number of times an IP shows up in the log (this will take additional time)? (y/n): ")

if "y" in display_IP_count.lower():
    counted_list = []
    for x in unique_ip:
        append_me = x + " (" + str(ip_list.count(x)) + ")"
        counted_list.append(append_me)
    counted_list.sort()

    redirect_to_file = raw_input("redirect the IP counts to a different file? (y/n): ")
    if "y" in redirect_to_file.lower():
        which_file = raw_input("Please specify file/path: ")
        sys.stdout = open(which_file, "w")
        for x in counted_list:
             print(x)

