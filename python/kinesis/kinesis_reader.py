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

from collections import namedtuple


logger = logging.getLogger("KinesisReader")
logger.setLevel(logging.DEBUG)


KinesisRecord = namedtuple('KinesisRecord', ['sequence_number', 'arrival_timestamp', 'partition_key', 'data'])


class KinesisReader:

    def __init__(self, client, stream, from_trim_horizon=False, from_offsets=None, log_actions=False):
        """ Initializes a new reader. This will call Kinesis to get information
            about the shards in the stream, and will throw if unable to do so
            (for example, if the stream doesn't exist).

            By default, this reader will start at the end of the stream, and read
            only records that have been added after its creation. The various "from"
            parameters modify this behavior; you can only specify one such parameter
            when creating the reader.

            client              The Kinesis client.
            stream              The name or ARN of the Kinesis stream to read.
            from_trim_horizon   If True, the reader will start reading from the beginning
                                of the stream.
            from_offsets        If provided, this is a dict of shard ID to sequence number,
                                as returned by get_offsets(). The reader will start reading
                                from the record AFTER the provided sequence number.
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
        self._retrieve_shards(from_trim_horizon, from_offsets)


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


    def shard_offsets(self):
        """ Returns a dict containing the sequence number for the most recently
            read record in each shard (key is shard ID). 
            """
        return dict([(s.shard_id, s.last_sequence_number) for s in self._shards])

    
    def millis_behind_latest(self, by_shard=False):
        """ By default, returns the maximum millis-behind value from all shards.
            If the by_shard parameter is True, returns a map containing the value
            for each shard.
            """
        if by_shard:
            return dict([(s.shard_id, s.millis_behind_latest) for s in self._shards])
        else:
            max_behind = 0
            for s in self._shards:
                if s.millis_behind_latest is None:
                    # we can't give an answer until all shards have been checked
                    return None
                max_behind = max(max_behind, s.millis_behind_latest)
            return max_behind


    def _retrieve_shards(self, from_trim_horizon, from_offsets):
        """ Retrieves the stream's shards from Kinesis.
            """
        self._shards = []
        self._current_shard_idx = 0
        self._current_shard = None
        args = dict(self._stream_param)
        while True:
            resp = self._client.list_shards(**args)
            for shard in resp['Shards']:
                # TODO - only retain top level of hierarchy
                self._shards.append(Shard(self._client, self._stream_param, shard['ShardId'], from_trim_horizon, from_offsets))
            if resp.get('NextToken'):
                args['NextToken'] = resp.get('NextToken')
            else:
                return


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

    def __init__(self, client, stream_param, shard_id, from_trim_horizon=None, from_offsets=None):
        self.shard_id = shard_id
        self.last_sequence_number = None
        self.millis_behind_latest = None
        self._client = client
        self._shard_iterator_args = dict(stream_param)
        self._shard_iterator_args['ShardId'] = shard_id
        if from_offsets:
            self._shard_iterator_args['ShardIteratorType'] = 'AFTER_SEQUENCE_NUMBER'
            self._shard_iterator_args['StartingSequenceNumber'] = from_offsets[shard_id]
        elif from_trim_horizon:
            self._shard_iterator_args['ShardIteratorType'] = 'TRIM_HORIZON'
        else:
            self._shard_iterator_args['ShardIteratorType'] = 'LATEST'
        self._current_shard_iterator = None
        self._current_records = []


    def read(self):
        if not self._current_records:
            self._retrieve_records()
        if not self._current_records:
            return None
        result = self._transform_rec(self._current_records[0])
        self.last_sequence_number = result.sequence_number
        self._current_records = self._current_records[1:]
        return result


    def has_records(self):
        """ Returns True if there are currently records in-memory for this shard.
            """
        return not not self._current_records == []


    def _retrieve_records(self):
        if not self._current_shard_iterator:
            self._retrieve_shard_iterator()
        try:
            resp = self._client.get_records(ShardIterator=self._current_shard_iterator)
            self._current_records = resp['Records']
            self._current_shard_iterator = resp['NextShardIterator']
            self.millis_behind_latest = resp['MillisBehindLatest']
        except Exception as ex:
            if "ExpiredIteratorException" in str(ex):
                self._current_records = []
                self._current_shard_iterator = None
            else:
                raise


    def _retrieve_shard_iterator(self):
        if self.last_sequence_number:
            # indicates that we've already read something, so need to restart from there
            self._shard_iterator_args['ShardIteratorType'] = 'AFTER_SEQUENCE_NUMBER'
            self._shard_iterator_args['StartingSequenceNumber'] = self.last_sequence_number
        resp = self._client.get_shard_iterator(**self._shard_iterator_args)
        self._current_shard_iterator = resp['ShardIterator']



    @staticmethod
    def _transform_rec(src_rec):
        # TODO - uncompress data if necessary
        return KinesisRecord(src_rec['SequenceNumber'], src_rec['ApproximateArrivalTimestamp'], src_rec['PartitionKey'], src_rec['Data'])
