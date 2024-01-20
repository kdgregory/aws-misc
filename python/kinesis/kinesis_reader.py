# Copyright 2023, Keith D Gregory
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


import boto3
import json
import logging
import re
import time


logger = logging.getLogger("KinesisReader")
logger.setLevel(logging.DEBUG)


class Record:
    """ A helper that holds retrieved messages. This contains all of the
        individual record fields returned by get_records(), along with the
        "millis behind latest" value for the shard. The data field is
        converted to binary, and uncompressed if it was originally GZipped.
        """

    # TODO - consider replacing with a namedtuple

    def __init__(self, src_record, millis_behind_latest):
        self.sequence_number = src_record['SequenceNumber']
        self.arrival_timestamp = src_record['ApproximateArrivalTimestamp']
        self.millis_behind_latest = millis_behind_latest
        self.partition_key = src_record['PartitionKey']
        self.data = src_record['Data'] # FIXME - convert this and uncompress if necessary


class KinesisReader:

    def __init__(self, client, stream, starting_at="LATEST", log_actions=False):
        """ Initializes a new reader. This will call Kinesis to get information
            about the shards in the stream, and will throw if unable to do so
            (for example, if the stream doesn't exist).

            client          The Kinesis client.
            stream          The name or ARN of the Kinesis stream to read.
            starting_at     "LATEST" or "TRIM_HORIZON"
            log_actions     
            """
        self._client = client
        # TODO - get stream description, only store ARN
        if stream.startswith("arn:"):
            self._stream_name = re.sub(r".*:", "", stream)
            self._stream_param = { "StreamARN": stream }
        else:
            self._stream_name = stream
            self._stream_param = { "StreamName": stream }
        self._log_actions = log_actions
        self._shards = self._retrieve_shards(starting_at)
        self._current_shard_idx = 0
        self._current_shard = None


    def read(self):
        """ Returns the next available record, None if there are none available
            after examining all shards.

            Note that Kinesis may have gaps, in which you can attempt to read a
            shard multiple times and get nothing. This method does not attempt
            to compensate for that.
            """
        if self._current_shard and self._current_shard.has_records():
            return self._current_shard.read()
        for idx in self._shards_to_read():
            self._current_shard_idx = idx
            self._current_shard = self._shards[idx]
            rec = self._current_shard.read()
            if rec:
                return rec


    def _retrieve_shards(self, starting_at):
        """ Retrieves the stream's shards from Kinesis.
            """
        result = []
        args = dict(self._stream_param)
        while True:
            resp = self._client.list_shards(**args)
            # TODO - handle hierarchy
            for shard in resp['Shards']:
                result.append(Shard(self._client, self._stream_param, shard['ShardId'], starting_at))
            if resp.get('NextToken'):
                args['NextToken'] = resp.get('NextToken')
            else:
                return result


    def _shards_to_read(self):
        """ Generates a list of shard indexes that will allow us to iterate
            all shards once.
            """
        next_idx = self._current_shard_idx + 1
        last_idx = self._current_shard_idx + len(self._shards) + 1
        return [idx % len(self._shards) for idx in range(next_idx, last_idx)]


class Shard:
    """ An internal helper class that encapsulates all shard functionality.
        """

    def __init__(self, client, stream_param, shard_id, iterator_type):
        self._client = client
        self._shard_id = shard_id
        self._stream_param = stream_param
        self._iterator_type = iterator_type
        self._current_shard_iterator = None
        self._current_records = []
        self._millis_behind_latest = None


    def read(self):
        if not self._current_records:
            self._retrieve_records()
        if not self._current_records:
            return None
        result = Record(self._current_records[0], self._millis_behind_latest)
        self._current_records = self._current_records[1:]
        # TODO - retain current record's sequence number
        return result


    def has_records(self):
        """ Returns True if there are currently records in-memory for this shard.
            """
        return not not self._current_records == []


    def _retrieve_shard_iterator(self):
        # TODO - deal with different iterator types
        # TODO - stream param will turn into StreamARN, can create dict as literal
        args = dict(self._stream_param, ShardId=self._shard_id, ShardIteratorType=self._iterator_type)
        resp = self._client.get_shard_iterator(**args)
        self._current_shard_iterator = resp['ShardIterator']


    def _retrieve_records(self):
        # TODO - handle shard iterator expiration
        if not self._current_shard_iterator:
            self._retrieve_shard_iterator()
        resp = self._client.get_records(ShardIterator=self._current_shard_iterator)
        self._current_records = resp['Records']
        self._current_shard_iterator = resp['NextShardIterator']
        self._millis_behind_latest = resp['MillisBehindLatest']
