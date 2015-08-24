#!/usr/bin/python
#
# Requres python & m2crypto
#
# Based off of work from phreakmonkey.com / phreakmonkey at gmail
#
# Returns information in the following format:
#
# Hostname: Expiration
#
# Owner: Steve Ovens
# Date re-Created: May 14, 2015
# Primary Function:
# This script checks the localhost for ssl expiration date

import socket
from M2Crypto import SSL
from __future__ import division
import datetime


def get_ssl_information(hostname):
    ssl_context = SSL.Context()
    # I am enabling unknown CA's to deal with self-signed certs
    ssl_context.set_allow_unknown_ca(True)
    ssl_context.set_verify(SSL.verify_none, 1)
    connect_to_server_over_https = SSL.Connection(ssl_context)
    connect_to_server_over_https.postConnectionCheck = None
    timeout = SSL.timeout(15)
    connect_to_server_over_https.set_socket_read_timeout(timeout)
    connect_to_server_over_https.set_socket_write_timeout(timeout)
    try:
        connect_to_server_over_https.connect((hostname, 443))
    except Exception, err:
        print("%s: %s" % (hostname, err))
        return

    cert = connect_to_server_over_https.get_peer_cert()

    try:
        cert_expiration_date = str(cert.get_not_after())
    except AttributeError:
        cert_expiration_date = "Error getting Expiration date"
        pass

    if type(cert_expiration_date) == datetime.datetime:
        todays_date = datetime.datetime.now()
        time_to_expiry = (cert_expiration_date - todays_date).days
        if time_to_expiry > 365:
            time_to_expiry = round((time_to_expiry / 365) , 2)

    connect_to_server_over_https.close



get_ssl_information(socket.gethostname())
