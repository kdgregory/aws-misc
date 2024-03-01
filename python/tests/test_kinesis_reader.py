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

TEST_STREAM_NAME = "example"
TEST_STREAM_ARN  = f"arn:aws:kinesis:us-east-1:123456789012:stream/{TEST_STREAM_NAME}"

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


class MockShard:

    def __init__(self, shard_id, records):
        self._id = shard_id
        self._records = records
        self._current_position = 0
        self._millis_behind = 0


    def select_records(self, starting_offset, ending_offset):
        result = []
        ending_offset = min(ending_offset, len(self._records))
        for idx in range(starting_offset, ending_offset):
            rec = self._records[idx]
            result.append({
                'SequenceNumber':               mock_sequence_number(idx),
                'ApproximateArrivalTimestamp':  rec.arrival_timestamp,
                'Data':                         rec.message,
                'PartitionKey':                 rec.partition_key,
                'EncryptionType':               "NONE"
            })
            self._millis_behind = rec.time_offset_ms
            self._current_position = idx + 1
        return result


    def millis_behind(self):
        return self._millis_behind


    def next_shard_iterator(self):
        return mock_shard_iterator(self._id, self._current_position)


    def get_shard_iterator(self, ShardIteratorType, StartingSequenceNumber, Timestamp):
        if ShardIteratorType == "LATEST":
            return mock_shard_iterator(self._id, len(self._records))
        elif ShardIteratorType == "TRIM_HORIZON":
            return mock_shard_iterator(self._id, 0)
        elif ShardIteratorType == "AFTER_SEQUENCE_NUMBER":
            _, prev_idx = decompose_mock_shard_iterator(StartingSequenceNumber)
            next_idx = min(prev_idx + 1, len(self._records))
            return mock_shard_iterator(self._id, next_idx)
        else:
            raise Exception(f"unsupported iterator type: {ShardIteratorType}")


class MockClientImpl:

    def __init__(self, shards, stream_status, read_limit):
        self._shards = dict([[k, MockShard(k,v)] for k,v in shards.items()])
        self._stream_status = stream_status
        self._read_limit = read_limit


    def describe_stream_summary(self, StreamName=None, StreamArn=None):
        # we only return the things that we use
        return {
            'StreamDescriptionSummary': {
                'StreamName': TEST_STREAM_NAME,
                'StreamARN': TEST_STREAM_ARN,
                'StreamStatus': self._stream_status,
            }
        }


    def list_shards(self, StreamName=None, StreamARN=None):
        # again, only the things that we use
        return {
            'Shards': [{'ShardId' : shard_id} for shard_id in self._shards.keys()]
        }


    def get_records(self, ShardIterator):
        shard_id, starting_offset = decompose_mock_shard_iterator(ShardIterator)
        ending_offset = starting_offset + self._read_limit
        shard = self._shards[shard_id]
        return {
            'Records':              shard.select_records(starting_offset, ending_offset),
            'MillisBehindLatest':   shard.millis_behind(),
            'NextShardIterator':    shard.next_shard_iterator()
        }


    def get_shard_iterator(self, ShardId, ShardIteratorType, StreamName=None, StreamARN=None, StartingSequenceNumber=None, Timestamp=None):
        shard = self._shards[ShardId]
        return {
            'ShardIterator': shard.get_shard_iterator(ShardIteratorType, StartingSequenceNumber, Timestamp)
        }


def create_mock_client(shards, stream_status="ACTIVE", read_limit=999):
    impl = MockClientImpl(shards, stream_status, read_limit)
    mock = Mock(spec=["describe_stream_summary", "list_shards", "get_shard_iterator", "get_records"])
    mock.describe_stream_summary.side_effect = lambda **args: impl.describe_stream_summary(**args)
    mock.list_shards.side_effect = lambda **args: impl.list_shards(**args)
    mock.get_shard_iterator.side_effect = lambda **args: impl.get_shard_iterator(**args)
    mock.get_records.side_effect = lambda **args: impl.get_records(**args)
    return mock


def assert_returned_record(rec, sequence_idx, partition_key, data):
    assert rec.sequence_number          == mock_sequence_number(sequence_idx)
    assert rec.arrival_timestamp        == ANY
    assert rec.partition_key            == partition_key
    assert rec.data                     == data


###
### Test cases
###

def test_single_shard_basic_operation(caplog):
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(
        shards={
            expected_shard_id: [
                MockRecord( 1500, "part1", "message 1" ),
                MockRecord( 1000, "part1", "message 2" ),
                MockRecord(  500, "part2", "message 3" ),
                ]
            })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    assert reader.millis_behind_latest() == None
    assert_returned_record(reader.read(), 0, "part1", b"message 1")
    assert_returned_record(reader.read(), 1, "part1", b"message 2")
    assert_returned_record(reader.read(), 2, "part2", b"message 3")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 500
    assert reader.millis_behind_latest(by_shard=True) == { expected_shard_id: 500 }
    assert reader.shard_offsets() == { expected_shard_id: mock_sequence_number(2) }
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN,
        ShardId=expected_shard_id,
        ShardIteratorType="TRIM_HORIZON")
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])
    assert len(caplog.records) == 0


def test_single_shard_basic_operation_with_logging(caplog):
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(
        shards={
            expected_shard_id: [
                MockRecord( 2000, "part1", "message 1" ),
                MockRecord( 1000, "part1", "message 2" ),
                MockRecord(    0, "part2", "message 3" ),
                ]
            })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True, log_actions=True)
    assert reader.millis_behind_latest() == None
    assert_returned_record(reader.read(), 0, "part1", b"message 1")
    assert_returned_record(reader.read(), 1, "part1", b"message 2")
    assert_returned_record(reader.read(), 2, "part2", b"message 3")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 0
    assert reader.millis_behind_latest(by_shard=True) == { expected_shard_id: 0 }
    assert reader.shard_offsets() == { expected_shard_id: mock_sequence_number(2) }
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN,
        ShardId=expected_shard_id,
        ShardIteratorType="TRIM_HORIZON")
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])
    assert len(caplog.records) == 7
    assert caplog.records[0].msg == f"verifying stream {TEST_STREAM_NAME}"
    assert caplog.records[1].msg == f"retrieving shards for {TEST_STREAM_ARN}"
    assert caplog.records[2].msg == f"retrieving shard iterator for {TEST_STREAM_ARN}: shard {expected_shard_id}, " \
                                    f"iterator type TRIM_HORIZON, sequence number None"
    assert caplog.records[3].msg == f"retrieving records from {TEST_STREAM_ARN}"
    assert caplog.records[4].msg == f"retrieved 3 records from {TEST_STREAM_ARN}"
    assert caplog.records[5].msg == f"retrieving records from {TEST_STREAM_ARN}"
    assert caplog.records[6].msg == f"retrieved 0 records from {TEST_STREAM_ARN}"


def test_single_shard_from_offsets():
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(
        shards={
            expected_shard_id: [
                MockRecord( 2000, "part1", "message 1" ),
                MockRecord( 1000, "part1", "message 2" ),
                MockRecord(    0, "part2", "message 3" ),
                ]
            })
    offsets = {
        expected_shard_id: mock_sequence_number(1)
    }
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_offsets=offsets)
    assert_returned_record(reader.read(), 2, "part2", b"message 3")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 0
    assert reader.shard_offsets() == { expected_shard_id: mock_sequence_number(2) }
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN,
        ShardId=expected_shard_id,
        ShardIteratorType="AFTER_SEQUENCE_NUMBER",
        StartingSequenceNumber=mock_sequence_number(1))
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 2)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])


def test_single_shard_repeated_reads():
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(
        read_limit = 1,
        shards={
            expected_shard_id: [
                MockRecord( 2000, "part1", "message 1" ),
                MockRecord( 1000, "part1", "message 2" ),
                MockRecord(    0, "part2", "message 3" ),
                ]
        })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    assert_returned_record(reader.read(), 0, "part1", b"message 1")
    assert reader.millis_behind_latest() == 2000
    assert_returned_record(reader.read(), 1, "part1", b"message 2")
    assert reader.millis_behind_latest() == 1000
    assert_returned_record(reader.read(), 2, "part2", b"message 3")
    assert reader.millis_behind_latest() == 0
    assert reader.read() == None
    assert reader.millis_behind_latest() == 0
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_has_calls([
        # for this test the reader will reuse the shard iterator to retrieve more records
        call(StreamARN=TEST_STREAM_ARN, ShardId=expected_shard_id, ShardIteratorType="TRIM_HORIZON"),
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
    mock_client = create_mock_client(
        # must use read limit so that we're not just reading cached records
        read_limit = 1,
        shards={
            expected_shard_id: [
                MockRecord( 1500, "part1", "message 1" ),
                MockRecord( 1000, "part1", "message 2" ),
                MockRecord(  500, "part2", "message 3" ),
                ]
            })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    # we'll have one successful read
    assert_returned_record(reader.read(), 0, "part1", b"message 1")
    assert reader.millis_behind_latest() == 1500
    # then simulate an expired iterator
    with monkeypatch.context() as mp:
        mp.setattr(mock_client.get_records, 'side_effect', alt_get_records)
        assert reader.read() == None
    # then verify that the reader picks up where it left off
    assert_returned_record(reader.read(), 1, "part1", b"message 2")
    assert_returned_record(reader.read(), 2, "part2", b"message 3")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 500
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_has_calls([
        call(StreamARN=TEST_STREAM_ARN, ShardId=expected_shard_id, ShardIteratorType="TRIM_HORIZON"),
        call(StreamARN=TEST_STREAM_ARN, ShardId=expected_shard_id, ShardIteratorType="AFTER_SEQUENCE_NUMBER", StartingSequenceNumber=mock_sequence_number(0)),
        ])
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 0)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 1)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 1)),  # retry after failure to read
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 2)),
        call(ShardIterator=mock_shard_iterator(expected_shard_id, 3)),
        ])


def test_stream_deleted_while_reading():
    expected_shard_id = mock_shard_id(0)
    mock_client = create_mock_client(
        shards={ "irrelevant": [] },
        stream_status="DELETING")
    with pytest.raises(Exception) as exc:
        reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    assert f"stream {TEST_STREAM_NAME} is not active" in str(exc)
    assert f"DELETING" in str(exc)


def test_multiple_shards_basic_operation(caplog):
    shard_0_id = mock_shard_id(0)
    shard_1_id = mock_shard_id(1)
    mock_client = create_mock_client(
        shards={
            shard_0_id: [
                MockRecord( 1500, "part1", "shard 0 message 1" ),
                MockRecord( 1000, "part1", "shard 0 message 2" ),
                MockRecord(  500, "part2", "shard 0 message 3" ),
                ],
            shard_1_id: [
                MockRecord( 2000, "part3", "shard 1 message 1" ),
                MockRecord( 1000, "part4", "shard 1 message 2" ),
                MockRecord(  500, "part4", "shard 1 message 3" ),
                MockRecord(    0, "part4", "shard 1 message 4" ),
                ]
            })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    assert reader.millis_behind_latest() == None
    assert_returned_record(reader.read(), 0, "part1", b"shard 0 message 1")
    assert_returned_record(reader.read(), 1, "part1", b"shard 0 message 2")
    assert_returned_record(reader.read(), 2, "part2", b"shard 0 message 3")
    assert_returned_record(reader.read(), 0, "part3", b"shard 1 message 1")
    assert_returned_record(reader.read(), 1, "part4", b"shard 1 message 2")
    assert_returned_record(reader.read(), 2, "part4", b"shard 1 message 3")
    assert_returned_record(reader.read(), 3, "part4", b"shard 1 message 4")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 500
    assert reader.millis_behind_latest(by_shard=True) == { shard_0_id: 500, shard_1_id: 0 }
    assert reader.shard_offsets() == { shard_0_id: mock_sequence_number(2), shard_1_id: mock_sequence_number(3) }
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_has_calls([
        call(StreamARN=TEST_STREAM_ARN,
             ShardId=shard_0_id,
             ShardIteratorType="TRIM_HORIZON"),
        call(StreamARN=TEST_STREAM_ARN,
             ShardId=shard_1_id,
             ShardIteratorType="TRIM_HORIZON")
        ])
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(shard_0_id, 0)),
        call(ShardIterator=mock_shard_iterator(shard_1_id, 0)),
        call(ShardIterator=mock_shard_iterator(shard_0_id, 3)),
        call(ShardIterator=mock_shard_iterator(shard_1_id, 4)),
        ])
    assert len(caplog.records) == 0


def test_multiple_shards_basic_operation(caplog):
    shard_0_id = mock_shard_id(0)
    shard_1_id = mock_shard_id(1)
    mock_client = create_mock_client(
        read_limit = 2,
        shards={
            shard_0_id: [
                MockRecord( 1500, "part1", "shard 0 message 1" ),
                MockRecord( 1000, "part1", "shard 0 message 2" ),
                MockRecord(  500, "part2", "shard 0 message 3" ),
                ],
            shard_1_id: [
                MockRecord( 2000, "part3", "shard 1 message 1" ),
                MockRecord( 1000, "part4", "shard 1 message 2" ),
                MockRecord(  500, "part4", "shard 1 message 3" ),
                MockRecord(    0, "part4", "shard 1 message 4" ),
                ]
            })
    reader = KinesisReader(mock_client, TEST_STREAM_NAME, from_trim_horizon=True)
    assert reader.millis_behind_latest() == None
    assert_returned_record(reader.read(), 0, "part1", b"shard 0 message 1")
    assert_returned_record(reader.read(), 1, "part1", b"shard 0 message 2")
    assert_returned_record(reader.read(), 0, "part3", b"shard 1 message 1")
    assert_returned_record(reader.read(), 1, "part4", b"shard 1 message 2")
    assert_returned_record(reader.read(), 2, "part2", b"shard 0 message 3")
    assert_returned_record(reader.read(), 2, "part4", b"shard 1 message 3")
    assert_returned_record(reader.read(), 3, "part4", b"shard 1 message 4")
    assert reader.read() == None
    assert reader.millis_behind_latest() == 500
    assert reader.millis_behind_latest(by_shard=True) == { shard_0_id: 500, shard_1_id: 0 }
    assert reader.shard_offsets() == { shard_0_id: mock_sequence_number(2), shard_1_id: mock_sequence_number(3) }
    mock_client.describe_stream_summary.assert_called_once_with(
        StreamName=TEST_STREAM_NAME)
    mock_client.list_shards.assert_called_once_with(
        StreamARN=TEST_STREAM_ARN)
    mock_client.get_shard_iterator.assert_has_calls([
        call(StreamARN=TEST_STREAM_ARN,
             ShardId=shard_0_id,
             ShardIteratorType="TRIM_HORIZON"),
        call(StreamARN=TEST_STREAM_ARN,
             ShardId=shard_1_id,
             ShardIteratorType="TRIM_HORIZON")
        ])
    mock_client.get_records.assert_has_calls([
        call(ShardIterator=mock_shard_iterator(shard_0_id, 0)),
        call(ShardIterator=mock_shard_iterator(shard_1_id, 0)),
        call(ShardIterator=mock_shard_iterator(shard_0_id, 2)),
        call(ShardIterator=mock_shard_iterator(shard_1_id, 2)),
        call(ShardIterator=mock_shard_iterator(shard_0_id, 3)),
        call(ShardIterator=mock_shard_iterator(shard_1_id, 4)),
        ])
    assert len(caplog.records) == 0
