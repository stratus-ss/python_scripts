#!/usr/bin/env python3
# This script should put objects into S3 using boto3 installed from pypi
# steve [dot] ovens [at] redhat [dot] com
# July 2019
# This script assumes that you have a ~/.aws/credentials file as per
# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#configuration
import argparse, boto3

parser = argparse.ArgumentParser()
parser.add_argument('--bucket-name', action='store', dest='bucket_name', help='Specify the S3 bucket name which will contain the file upload', required=True)
parser.add_argument('--file-name', action='store', dest='file_name', help='Specify the file which will be uploaded to S3', required=True)
options = parser.parse_args()



s3 = boto3.resource('s3')
print("Attempting to put %s into the %s bucket" % (options.file_name, options.bucket_name))
data = open('%s' % options.file_name, 'rb')
print(s3.Bucket('%s' % options.bucket_name).put_object(Key='%s' % options.file_name, Body=data))

