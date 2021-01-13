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

Reads and prints all records from a Kinesis stream, starting at the end of the
stream. This is useful to monitor streams that are actively being updated.

Invocation:

    kinesis_reader.py STREAM_NAME

Where:

    STREAM_NAME is the stream that you want to monitor (be in current account/region).

"""

import boto3
import json
import time
import sys


client = boto3.client('kinesis')


def retrieve_shards(stream_name):
    """ Retrieves information about all shards for the specified stream.
    """
    result = []
    paginator = client.get_paginator('describe_stream')
    for page in paginator.paginate(StreamName=stream_name):
        result += page['StreamDescription']['Shards']
    return result


def retrieve_shard_iterators(stream_name, shards, iterator_type='LATEST'):
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
            result.append(rec)
        iterators[shard_id] = resp['NextShardIterator']
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    stream_name = sys.argv[1]
    shards = retrieve_shards(stream_name)
    iterators = retrieve_shard_iterators(stream_name, shards)
    while True:
        for rec in retrieve_records(iterators):
            print(rec)
        time.sleep(10)
