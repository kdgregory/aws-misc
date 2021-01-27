#!/usr/bin/env python3
################################################################################
# Copyright 2019 Keith D Gregory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

"""

Reads and prints all records from a Kinesis stream, starting at either the
trim horizon or end of the stream.

Invocation:

    kinesis_reader.py STREAM_NAME [ITERATOR_TYPE [POLL_INTERVAL]]

Where:

    STREAM_NAME   is the stream that you want to monitor.
    ITERATOR_TYPE is either LATEST (the default) or TRIM_HORIZON.
    POLL_INTERVAL is the number of seconds to wait between read attempts.
                  Default is 10.

Notes:

    Assumes that the stream contains UTF-8 encoded messages.

    For multi-shard streams, processes all message from a single shared
    before moving to the next shard.

    Pipe output into jq '.Data|fromjson' to parse JSON data records (which
    can then be passed to jq for additional processing).

"""

import boto3
import json
import time
import sys

from datetime import timezone


client = boto3.client('kinesis')


def retrieve_shards(stream_name):
    """ Retrieves information about all shards for the specified stream.
    """
    result = []
    paginator = client.get_paginator('describe_stream')
    for page in paginator.paginate(StreamName=stream_name):
        result += page['StreamDescription']['Shards']
    return result


def retrieve_shard_iterators(stream_name, shards, iterator_type):
    """ Returns a map of shard ID to iterator.
    """
    result = {}
    for shard in shards:
        shard_id = shard['ShardId']
        resp = client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id, ShardIteratorType=iterator_type)
        result[shard_id] = resp['ShardIterator']
    return result


def retrieve_records(iterators):
    """ Retrieves all records for the provided iterator map, updating the map with new iterators.
    """
    result = []
    for shard_id, itx in iterators.items():
        resp = client.get_records(ShardIterator=itx)
        for rec in resp['Records']:
            result.append({
                'SequenceNumber':               rec['SequenceNumber'],
                'ApproximateArrivalTimestamp':  rec['ApproximateArrivalTimestamp'].astimezone(timezone.utc).isoformat(),
                'Data':                         rec['Data'].decode('utf-8'),
                'PartitionKey':                 rec['PartitionKey']
                })
        iterators[shard_id] = resp['NextShardIterator']
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print(__doc__)
        sys.exit(1)

    stream_name = sys.argv[1]
    iterator_type = sys.argv[2] if len(sys.argv) > 2 else 'LATEST'
    poll_interval = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    shards = retrieve_shards(stream_name)
    iterators = retrieve_shard_iterators(stream_name, shards, iterator_type)
    while True:
        for rec in retrieve_records(iterators):
            print(json.dumps(rec))
        time.sleep(poll_interval)
