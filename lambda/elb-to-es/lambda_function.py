# Copyright 2018 Keith D Gregory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################
#
# Invoked when a Classic Load Balancer writes a logfile to S3. This function
# extracts the fields from the log lines and writes them to an Elasticsearch
# cluster.
#
# See https://www.kdgregory.com/index.php?page=aws.loggingPipeline#elb
#
# Contains example code from https://github.com/DavidMuller/aws-requests-auth
#
################################################################################

import boto3
import hashlib
import json
import os
import os.path
import re
import tempfile
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth

# configuration is via environment variables
es_hostname = os.environ["ELASTIC_SEARCH_HOSTNAME"]
batch_size = int(os.environ["BATCH_SIZE"])

# this regex pulls apart the ELB log line, using capturing groups
baseRE = re.compile(
    (
    r'^(\d{4}-\d{2}-\d{2}T\d+:\d+:\d+\.\d+Z) '    # timestamp
    r'([^ ]+) '                                   # elb_name
    r'(\d+\.\d+\.\d+\.\d+):(\d+) '                # client_ip, client_port
    r'(\d+\.\d+\.\d+\.\d+):(\d+) '                # backend_ip, backend_port
    r'([0-9.-]+) '                                # request_processing_time
    r'([0-9.-]+) '                                # backend_processing_time
    r'([0-9.-]+) '                                # response_processing_time
    r'(\d{3}) '                                   # elb_status_code
    r'(\d{3}) '                                   # backend_status_code
    r'(\d+) '                                     # received_bytes
    r'(\d+) '                                     # sent_bytes
    r'"([A-Z]+) '                                 # http_method
    r'([^ ]+) '                                   # http_url
    r'([^ ]+)" '                                  # http_version
    r'"(.+)" '                                    # user_agent
    r'(.+) '                                      # ssl_cipher
    r'(.+)$'                                      # ssl_protocol
    ))

# this regex extracts the host portion of the url
hostRE = re.compile(r'[Hh][Tt][Tt][Pp][Ss]?://([^:/]+).*')

# this regex is specific to my website, and is used to extract page IDs
pageRE = re.compile('.*page=')

# resources are created outside of the handler function so that they're shared
s3 = boto3.resource("s3")
auth = AWSRequestsAuth(aws_access_key=os.environ["AWS_ACCESS_KEY_ID"],
                       aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                       aws_token=os.environ["AWS_SESSION_TOKEN"],
                       aws_region=os.environ["AWS_REGION"],
                       aws_service="es",
                       aws_host=es_hostname)


def lambda_handler(event, context):
    """The entry point for the Lambda function."""
    for rec in event["Records"]:
        s3_bucket = rec["s3"]["bucket"]["name"]
        s3_key = rec["s3"]["object"]["key"]
        process_file(s3_bucket, s3_key)


def process_file(s3_bucket, s3_key):
    """Handles a single uploaded file, transforming its contents and writing to ElasticSearch."""
    print("processing: s3://" + s3_bucket + "/" + s3_key)
    base_id = hashlib.sha1(s3_key.encode('utf-8')).hexdigest()
    with tempfile.TemporaryDirectory() as tmpdir:
        srcFile = os.path.join(tmpdir, "elb_log.txt")
        s3.Bucket(s3_bucket).download_file(s3_key, srcFile)
        recnum = 0;
        batch = []
        with open(srcFile, "r") as src:
            for s in src:
                recnum += 1
                batch += process_record(base_id, recnum, s)
                if recnum % batch_size == 0:
                    do_upload(batch, recnum)
                    batch = []
            do_upload(batch, recnum)


def process_record(base_id, recnum, s):
    """Parses a single ELB log entry and creates an entry for the bulk upload."""
    data = parse(s)
    index_name = "elb-" + data["timestamp"][0:13].lower()
    record_id = base_id + "-" + str(recnum)
    return [
        json.dumps({ "index": { "_index": index_name, "_type": "elb_access_log", "_id": record_id }}),
        json.dumps(data)
        ]


def do_upload(batch, recnum):
    """Combines a list of updates into a single ElasticSearch request."""
    print("uploading batch ending at record " + str(recnum))
    rsp = requests.post("https://" + es_hostname + "/_bulk",
                        headers={"Content-Type": "application/x-ndjson"},
                        auth=auth,
                        data="\n".join(batch) + "\n")
    if rsp.status_code != 200:
        raise BaseException("unable to upload: " + rsp.text)


def parse(s):
    """Extracts fields from an ELB log entry and returns them in a map."""
    m = baseRE.search(s)
    result = {}
    result["timestamp"]                     = m.group(1)
    result["elb_name"]                      = m.group(2)
    result["client_ip"]                     = m.group(3)
    result["client_port"]                   = m.group(4)
    result["backend_ip"]                    = m.group(5)
    result["backend_port"]                  = m.group(6)
    try:
        result["request_processing_time"]   = float(m.group(7))
    except:
        pass
    try:
        result["backend_processing_time"]   = float(m.group(8))
    except:
        pass
    try:
        result["response_processing_time"]  = float(m.group(9))
    except:
        pass
    result["elb_status_code"]               = m.group(10)
    result["backend_status_code"]           = m.group(11)
    result["received_bytes"]                = int(m.group(12))
    result["sent_bytes"]                    = int(m.group(13))
    result["http_method"]                   = m.group(14)
    result["http_url"]                      = m.group(15)
    result["http_version "]                 = m.group(16)
    result["user_agent"]                    = m.group(17)
    result["ssl_cipher"]                    = m.group(18)
    result["ssl_protocol"]                  = m.group(19)

    result["host"] = hostRE.match(m.group(15)).group(1)

    if pageRE.match(m.group(15)):
        result["page"]                      = pageRE.sub("", m.group(15))

    return result

