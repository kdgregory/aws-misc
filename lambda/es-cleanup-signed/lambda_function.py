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
# This function removes old Elasticsearch indexes. It is configured with a base
# index name, and the number of indexes to keep, and deletes older indexes until
# it reaches the desired number (note: requires indexes to be sortable by age).
#
# Contains example code from https://github.com/DavidMuller/aws-requests-auth
#
################################################################################

import json
import os
import requests

from aws_requests_auth.aws_auth import AWSRequestsAuth

def lambda_handler(event, context):
    es_host = os.environ['ELASTIC_SEARCH_HOSTNAME']
    num_indexes_to_keep = int(os.environ['NUM_INDEXES_TO_KEEP'])
    index_prefix = os.environ['INDEX_PREFIX']
    
    auth = AWSRequestsAuth(aws_access_key=os.environ['AWS_ACCESS_KEY_ID'],
                           aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                           aws_token=os.environ['AWS_SESSION_TOKEN'],
                           aws_region=os.environ['AWS_REGION'],
                           aws_service='es',
                           aws_host=es_host)

    indexResponse = requests.get('https://' + es_host + '/*', auth=auth)
    if (indexResponse.status_code != 200):
        raise Exception('failed to retrieve indexes: ' + indexResponse.text)
        
    indexData = indexResponse.json()
    indexNames = sorted([x for x in indexData.keys() if x.startswith(index_prefix)])
    indexesToDelete = indexNames[0 : max(0, len(indexNames) - num_indexes_to_keep)]
    
    for idx in indexesToDelete:
        deleteResponse = requests.delete('https://' + es_host + '/' + idx, auth=auth)
        if deleteResponse.status_code == 200:
            print("deleted " + idx)
        else:
            raise Exception("failed to delete " + idx + ": " + deleteResponse.text)
