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

def mock_shard_id(idx):
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

    def __init__(self, shards, read_limit):
        # at this point in development there should only be a single shard
        # but we're given a dict, so hack out the value
        for k,v in shards.items():
            self._shard_id = k
            self._records = v
        self._current_idx = 0
        self._read_limit = read_limit

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
        ending_offset = min(starting_offset + self._read_limit, len(self._records))
        for idx in range(starting_offset, ending_offset):
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


def create_mock_client(shards, read_limit=999):
    impl = MockImpl(shards, read_limit)
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
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(shards={
        expected_shard_id: [
            MockRecord( 1500, "part1", "message 1" ),
            MockRecord( 1000, "part1", "message 2" ),
            MockRecord(  500, "part2", "message 3" ),
            ]
        })
    reader = KinesisReader(mock_client, "example", from_trim_horizon=True)
    assert_returned_record(reader.read(), 0, 500, "part1", b"message 1")
    assert_returned_record(reader.read(), 1, 500, "part1", b"message 2")
    assert_returned_record(reader.read(), 2, 500, "part2", b"message 3")
    assert reader.read() == None
    assert reader.shard_offsets() == [ { expected_shard_id: mock_sequence_number(2) } ]
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamName="example",
        ShardId=expected_shard_id,
        ShardIteratorType="TRIM_HORIZON")
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])


def test_single_shard_from_offsets():
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(shards={
        expected_shard_id: [
            MockRecord( 1500, "part1", "message 1" ),
            MockRecord( 1000, "part1", "message 2" ),
            MockRecord(  500, "part2", "message 3" ),
            ]
        })
    offsets = {
        expected_shard_id: mock_sequence_number(1)
    }
    reader = KinesisReader(mock_client, "example", from_offsets=offsets)
    assert_returned_record(reader.read(), 2, 500, "part2", b"message 3")
    assert reader.read() == None
    assert reader.shard_offsets() == [ { expected_shard_id: mock_sequence_number(2) } ]
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamName="example",
        ShardId=expected_shard_id,
        ShardIteratorType="AFTER_SEQUENCE_NUMBER",
        StartingSequenceNumber=mock_sequence_number(1))
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 2)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])


def test_single_shard_repeated_reads():
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(shards={
        expected_shard_id: [
            MockRecord( 1500, "part1", "message 1" ),
            MockRecord( 1000, "part1", "message 2" ),
            MockRecord(  500, "part2", "message 3" ),
            ]
        },
        read_limit = 1
        )
    reader = KinesisReader(mock_client, "example", from_trim_horizon=True)
    assert_returned_record(reader.read(), 0, 1500, "part1", b"message 1")
    assert_returned_record(reader.read(), 1, 1000, "part1", b"message 2")
    assert_returned_record(reader.read(), 2,  500, "part2", b"message 3")
    assert reader.read() == None
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_has_calls([
        # for this test the reader will reuse the shard iterator to retrieve more records
        call(StreamName="example", ShardId=expected_shard_id, ShardIteratorType="TRIM_HORIZON"),
        ])
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 1)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 2)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])


def test_expired_shard_iterator(monkeypatch):
    def alt_get_records(ShardIterator):
        # message copied from actual exception; class is generated by boto so can't be used for test
        raise Exception("An error occurred (ExpiredIteratorException) when calling the GetRecords operation")

    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(shards={
        expected_shard_id: [
            MockRecord( 1500, "part1", "message 1" ),
            MockRecord( 1000, "part1", "message 2" ),
            MockRecord(  500, "part2", "message 3" ),
            ]
        },
        # must use read limit so that we're not just reading cached records
        read_limit = 1
        )
    reader = KinesisReader(mock_client, "example", from_trim_horizon=True)
    # we'll have one successful read
    assert_returned_record(reader.read(), 0, 1500, "part1", b"message 1")
    # then simulate an expired iterator
    with monkeypatch.context() as mp:
        mp.setattr(mock_client.get_records, 'side_effect', alt_get_records)
        assert reader.read() == None
    # then verify that the reader picks up where it left off
    assert_returned_record(reader.read(), 1, 1000, "part1", b"message 2")
    assert_returned_record(reader.read(), 2,  500, "part2", b"message 3")
    assert reader.read() == None
    mock_client.list_shards.assert_called_once_with(
        StreamName="example")
    mock_client.get_shard_iterator.assert_has_calls([
        call(StreamName="example", ShardId=expected_shard_id, ShardIteratorType="TRIM_HORIZON"),
        call(StreamName="example", ShardId=expected_shard_id, ShardIteratorType="AFTER_SEQUENCE_NUMBER", StartingSequenceNumber=mock_sequence_number(0)),
        ])
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 1)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 1)),  # retry after failure to read
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 2)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])
