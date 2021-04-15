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

    kinesis_reader.py STREAM_NAME [STARTING_AT [POLL_INTERVAL]]

Where:

    STREAM_NAME   is the stream that you want to monitor.
    STARTING_AT   identfiies where to start reading the stream. May be LATEST
                  (the default), TRIM_HORIZON, or AT_TIMESTAMP. The last requires
                  an additional argument; see below.
    POLL_INTERVAL is the number of seconds to wait between read attempts.
                  Default is 10.

Notes:

    To use the AT_TIMESTAMP shared iterator type, you must provide an additional
    argument, which may be either an ISO-8601-formatted UTC timestamp without
    fractional seconds (eg, "2021-04-15T01:23:45") or a numeric value representing
    seconds since epoch (which may have fractional seconds).

    Output is JSON, with the following fields:

        ApproximateArrivalTimestamp     the time that the message was stored in
                                        the stream, as an ISO-8601 UTC string.
        Data                            the message data; see below.
        PartitionKey                    the partition key for this message.
        SequenceNumber                  the message's unique sequence number.

    The message data is assumed to be a UTF-8-encoded string. If not, you must
    update retrieve-record() to apply whatever encoding/decoding is needed.

    If the data record is itself a stringified JSON object, you can extract
    it by piping output into jq with the query '.Data|fromjson'.

    For multi-shard streams, all message from a single shared are retrieved
    before moving to the next shard.
"""

import boto3
import calendar
import json
import time
import sys

from datetime import timezone


client = boto3.client('kinesis')


def parse_timestamp(value):
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
        try:
            return calendar.timegm(time.strptime(value, fmt))
        except ValueError:
            pass
    try:
        return float(value)
    except:
        raise ValueError(f"invalid timestamp: {value}")


def retrieve_shards(stream_name):
    """ Retrieves information about all shards for the specified stream.
    """
    result = []
    paginator = client.get_paginator('describe_stream')
    for page in paginator.paginate(StreamName=stream_name):
        result += page['StreamDescription']['Shards']
    return result


def retrieve_shard_iterators(stream_name, shards, iterator_type, timestamp=None):
    """ Returns a map of shard ID to iterator.
    """
    result = {}
    for shard in shards:
        shard_id = shard['ShardId']
        if timestamp:
            resp = client.get_shard_iterator(StreamName=stream_name, ShardId=shard_id, ShardIteratorType=iterator_type, Timestamp=timestamp)
        else:
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
    if len(sys.argv) < 2 or len(sys.argv) > 5:
        print(__doc__)
        sys.exit(1)

    stream_name = sys.argv[1]
    iterator_type = sys.argv[2] if len(sys.argv) > 2 else 'LATEST'
    timestamp = parse_timestamp(sys.argv.pop(3)) if iterator_type == 'AT_TIMESTAMP' else None
    poll_interval = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    shards = retrieve_shards(stream_name)
    iterators = retrieve_shard_iterators(stream_name, shards, iterator_type, timestamp)
    while True:
        for rec in retrieve_records(iterators):
            print(json.dumps(rec))
        time.sleep(poll_interval)


