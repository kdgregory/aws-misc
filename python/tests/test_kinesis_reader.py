import logging
import pytest
import re
import time
import uuid

from datetime import datetime, timedelta
from unittest.mock import Mock, ANY, call

from kinesis import KinesisReader


###
### Mocks and helpers
###
### We use a Python Mock to record calls, but the implementation is sufficiently 
### complex that we need a dedicated class to provide side-effects.
###

def mock_shard_name(idx):
    return f"shard-{idx:03d}"


def mock_sequence_number(offset):
    return f"sequence-{offset:06d}"


def mock_shard_iterator(shard_id, offset):
    return f"{shard_id}-{offset:06d}"


def decompose_mock_shard_iterator(s):
    m = re.match(r"(.+)-(\d+)", s)
    if m:
        return m.group(1), int(m.group(2))
    else:
        raise Exception("did not match") 


class MockRecord:

    def __init__(self, time_offset_ms, partition_key, message):
        self.time_offset_ms = time_offset_ms
        self.arrival_timestamp = datetime.now() - timedelta(milliseconds=time_offset_ms)
        self.partition_key = partition_key
        self.message = message.encode()


class MockImpl:

    def __init__(self, records):
        self._shard_id = mock_shard_name(0)
        self._records = records
        self._current_idx = 0

    def list_shards(self, StreamName=None, StreamArn=None):
        # we only return the things that we use
        return {
            'Shards': [
                {
                    'ShardId': self._shard_id
                },
            ],
        }

    def get_records(self, ShardIterator):
        records = []
        millis_behind = 0
        _, starting_offset = decompose_mock_shard_iterator(ShardIterator)
        for idx in range(starting_offset, len(self._records)):
            rec = self._records[idx]
            records.append({
                'SequenceNumber':               mock_sequence_number(idx),
                'ApproximateArrivalTimestamp':  rec.arrival_timestamp,
                'Data':                         rec.message,
                'PartitionKey':                 rec.partition_key,
                'EncryptionType':               "NONE"
            })
            millis_behind = rec.time_offset_ms
            self._current_idx = idx + 1
        return {
            'Records':              records,
            'MillisBehindLatest':   millis_behind,
            'NextShardIterator':    mock_shard_iterator(self._shard_id, self._current_idx)
        }


    def get_shard_iterator(self, ShardId, ShardIteratorType, StreamName=None, StreamARN=None, StartingSequenceNumber=None, Timestamp=None):
        if ShardIteratorType == "LATEST":
            result = mock_shard_iterator(ShardId, self._current_idx)
        elif ShardIteratorType == "TRIM_HORIZON":
            result = mock_shard_iterator(ShardId, 0)
        elif ShardIteratorType == "AFTER_SEQUENCE_NUMBER":
            _, prev_idx = decompose_mock_shard_iterator(StartingSequenceNumber)
            next_idx = min(prev_idx + 1, len(self._records))
            result = mock_shard_iterator(ShardId, next_idx)
        else:
            raise Exception("unsupported iterator type")
        return {
            'ShardIterator': result
        }


def create_mock_client(records):
    impl = MockImpl(records)
    mock = Mock(spec=["get_records", "get_shard_iterator", "list_shards"])
    mock.list_shards.side_effect = lambda **args: impl.list_shards(**args)
    mock.get_records.side_effect = lambda **args: impl.get_records(**args)
    mock.get_shard_iterator.side_effect = lambda **args: impl.get_shard_iterator(**args)
    return mock


def assert_returned_record(rec, sequence_idx, millis_behind_latest, partition_key, data):
    assert rec.sequence_number          == mock_sequence_number(sequence_idx)
    assert rec.arrival_timestamp        == ANY
    assert rec.millis_behind_latest     == millis_behind_latest
    assert rec.partition_key            == partition_key
    assert rec.data                     == data


###
### Test cases
###

def test_single_shard_basic_operation():
    mock_client = create_mock_client([
        MockRecord( 1500, "part1", "message 1" ),
        MockRecord( 1000, "part1", "message 2" ),
        MockRecord(  500, "part2", "message 3" ),
    ])
    reader = KinesisReader(mock_client, "example", from_trim_horizon=True)
    assert_returned_record(reader.read(), 0, 500, "part1", b"message 1")
    assert_returned_record(reader.read(), 1, 500, "part1", b"message 2")
    assert_returned_record(reader.read(), 2, 500, "part2", b"message 3")
    assert reader.read() == None
    assert reader.shard_offsets() == [ { mock_shard_name(0): mock_sequence_number(2) } ]
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamName="example",
        ShardId=mock_shard_name(0),
        ShardIteratorType="TRIM_HORIZON")
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=ANY),
        call(ShardIterator=ANY),
        ])


def test_single_shard_from_offsets():
    mock_client = create_mock_client([
        MockRecord( 1500, "part1", "message 1" ),
        MockRecord( 1000, "part1", "message 2" ),
        MockRecord(  500, "part2", "message 3" ),
    ])
    offsets = {
        mock_shard_name(0): mock_sequence_number(1)
    }
    reader = KinesisReader(mock_client, "example", from_offsets=offsets)
    assert_returned_record(reader.read(), 2, 500, "part2", b"message 3")
    assert reader.read() == None
    assert reader.shard_offsets() == [ { mock_shard_name(0): mock_sequence_number(2) } ]
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamName="example",
        ShardId=mock_shard_name(0),
        ShardIteratorType="AFTER_SEQUENCE_NUMBER",
        StartingSequenceNumber=mock_sequence_number(1))
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=ANY),
        call(ShardIterator=ANY),
        ])
