# Copyright 2018-2021 Keith D Gregory
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

""" Writes load balancer log records to an Elasticsearch cluster. Invoked via S3
    notification.

    See https://www.kdgregory.com/index.php?page=aws.loggingPipeline#elb for more
    information.
    """

import boto3
import gzip
import hashlib
import io
import json
import os
import re

from functools import lru_cache

import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth

from elb_parsers import ALBParser, CLBParser


# fail fast if missing required configuration
ES_HOSTNAME = os.environ["ELASTIC_SEARCH_HOSTNAME"]

# the rest have defaults
ELB_TYPE = os.environ.get("ELB_TYPE", "ALB")
ES_INDEX_PREFIX = os.environ.get("INDEX_PREFIX", "elb")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "1000")) * 2


def lambda_handler(event, context):
    """ The entry point for the Lambda function.
        """
    for rec in event["Records"]:
        s3_bucket = rec["s3"]["bucket"]["name"]
        s3_key = rec["s3"]["object"]["key"]
        process_file(s3_bucket, s3_key)
        
        
def process_file(s3_bucket, s3_key):
    """ Downloads, parses, and uploads; extracted for testing
        """
    # each Elasticsearch record needs a unique ID, so we'll hash the bucket and filename
    base_id = hashlib.sha256((s3_bucket + s3_key).encode('utf-8')).hexdigest()
    print(f"processing s3://{s3_bucket}/{s3_key}; base ID {base_id}")
    obj = s3().Object(s3_bucket, s3_key)
    buffer = io.BytesIO()
    obj.download_fileobj(buffer)
    entries = parser().parse(buffer)
    upload(base_id, entries)


def upload(base_id, entries):
    """ Uploads a list of dicts to Elasticsearch, breaking them into batches if needed.
        """
    batch = []
    for idx, entry in enumerate(entries):
        batch += process_record(base_id, idx, entry)
        if len(batch) % BATCH_SIZE == 0:
            do_upload(batch)
            batch = []
    do_upload(batch)

    
def process_record(base_id, recnum, data):
    """ Converts a single log entry into an Elasticsearch bulk-update record
        """
    index_name = f"{ES_INDEX_PREFIX}-{data['timestamp'][0:10]}"
    record_id = f"{base_id}-{recnum}"
    return [
        json.dumps({ "index": { "_index": index_name, "_type": "elb_access_log", "_id": record_id }}),
        json.dumps(data)
        ]


def do_upload(batch):
    """ Combines a list of updates into a single ElasticSearch request.
        Note: the division in the log message is because each record translates
              to two separate lines (index and data) in the upload.
        """
    print(f"uploading {int(len(batch)/2)} records")
    rsp = requests.post(f"https://{ES_HOSTNAME}/_bulk",
                        headers={"Content-Type": "application/x-ndjson"},
                        auth=request_auth(),
                        data="\n".join(batch) + "\n")
    if rsp.status_code != 200:
        raise Exception(f"unable to upload: {rsp.text}")


@lru_cache(maxsize=1)
def s3():
    return boto3.resource("s3")


@lru_cache(maxsize=1)
def request_auth():
    # session token only exists when running in Lambda, so must construct args
    auth_args = {}
    auth_args['aws_access_key']         = os.environ["AWS_ACCESS_KEY_ID"]
    auth_args['aws_secret_access_key']  = os.environ["AWS_SECRET_ACCESS_KEY"]
    auth_args['aws_region']             = os.environ["AWS_REGION"]
    auth_args['aws_service']            = "es"
    auth_args['aws_host']               = ES_HOSTNAME
    if "AWS_SESSION_TOKEN" in os.environ:
        auth_args["aws_token"]          = os.environ["AWS_SESSION_TOKEN"]
    return AWSRequestsAuth(**auth_args)


@lru_cache(maxsize=1)
def parser():
    if ELB_TYPE == "CLB":
        return CLBParser()
    else:
        return ALBParser()
