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

import http.client
import json
import os

def lambda_handler(event, context):
    es_host = os.environ['ELASTIC_SEARCH_HOSTNAME']
    num_indexes_to_keep = int(os.environ['NUM_INDEXES_TO_KEEP'])
    index_prefix = os.environ['INDEX_PREFIX']
    
    cxt = http.client.HTTPConnection(es_host);
    
    cxt.request('GET', '/*')
    indexResponse = cxt.getresponse()
    indexResponseBody = indexResponse.read().decode("utf-8")
    if (indexResponse.status != 200):
        raise Exception('failed to retrieve indexes: ' + indexResponseBody)

    indexData = json.loads(indexResponseBody)
    indexNames = sorted([x for x in indexData.keys() if x.startswith(index_prefix)])
    indexesToDelete = indexNames[0 : max(0, len(indexNames) - num_indexes_to_keep)]

    for idx in indexesToDelete:
        cxt.request('DELETE', "/" + idx)
        deleteResponse = cxt.getresponse()
        deleteResponseBody = deleteResponse.read().decode("utf-8")
        if deleteResponse.status == 200:
            print("deleted " + idx)
        else:
            raise Exception("failed to delete " + idx + ": " + deleteResponseBody)

