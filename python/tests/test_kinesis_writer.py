import logging
import pytest
import re
import time
import uuid

from unittest.mock import Mock, ANY

from kinesis_writer import KinesisWriter

###
### Mocks and helpers
###

DEFAULT_STREAM_NAME = "example"
DEFAULT_STREAM_ARN  = f"arn:aws:kinesis:us-east-2:123456789012:stream/{DEFAULT_STREAM_NAME}"

THROTTLING_MESSAGE  = "throttled!"  # in the real world, the message identifies account/stream/shard


def happy_mock_client():
    def invocation_handler(Records, StreamName=None, StreamARN=None):
        returned_records = []
        for record in Records:
            returned_records.append({
                # neither of these values are checked by the writer
                'ShardId': "zippy",
                'SequenceNumber': str(uuid.uuid4()),
            })
        return {
            'FailedRecordCount': 0,
            'Records': returned_records
        }
    mock = Mock(spec=["put_records"])
    mock.put_records.side_effect = invocation_handler
    return mock


def partial_mock_client():
    def invocation_handler(Records, StreamName=None, StreamARN=None):
        returned_records = []
        failed_count = 0
        for idx,record in enumerate(Records):
            if idx % 2 == 0:
                returned_records.append({
                    # neither of these values are checked by the writer
                    'ShardId': "zippy",
                    'SequenceNumber': str(uuid.uuid4()),
                })
            else:
                failed_count += 1
                returned_records.append({
                    'ErrorCode': "ProvisionedThroughputExceededException",
                    'ErrorMessage': THROTTLING_MESSAGE,
                })
        return {
            'FailedRecordCount': failed_count,
            'Records': returned_records
        }
    mock = Mock(spec=["put_records"])
    mock.put_records.side_effect = invocation_handler
    return mock


def throttled_mock_client():
    def invocation_handler(Records, StreamName=None, StreamARN=None):
        returned_records = []
        for _ in enumerate(Records):
            returned_records.append({
                'ErrorCode': "ProvisionedThroughputExceededException",
                'ErrorMessage': THROTTLING_MESSAGE,
            })
        return {
            'FailedRecordCount': len(Records),
            'Records': returned_records
        }
    mock = Mock(spec=["put_records"])
    mock.put_records.side_effect = invocation_handler
    return mock


def queue_and_record(writer, expected_records, message, partition_key=None):
    if partition_key == None:
        partition_key = ANY
    expected_records.append( {
        'Data': message.encode(),
        'PartitionKey': partition_key
    })
    writer.enqueue(message, partition_key)


def queued_records(writer):
    return [rec.request_form for rec in writer._queue]


def queued_record(writer, idx):
    return (
           writer._queue[idx].request_form['Data'],
           writer._queue[idx].request_form['PartitionKey']
           )

###
### Test cases
###

def test_basic_operation():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    now = time.time()
    expected_records = [
        {
            'Data': b"message 1",
            'PartitionKey': "argle"
        },
        {
            'Data': b"message 2",
            'PartitionKey': ANY # check manually
        },
    ]
    writer.enqueue("message 1", "argle")
    writer.enqueue(b"message 2")
    assert queued_records(writer) == expected_records
    (_, m2_partkey) = queued_record(writer, 1)
    assert float(m2_partkey) >= now
    assert writer.flush() == False
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records)
    assert writer._queue == []
    assert writer.last_batch_size == 2
    assert writer.last_batch_success_count == 2
    assert writer.last_batch_failure_messages == set()


def test_auto_flush_by_count():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    expected_records = []
    for x in range(600):
        queue_and_record(writer, expected_records, f"message {x}")
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records[:500])
    assert queued_records(writer) == expected_records[500:]
    assert writer.last_batch_size == 500
    assert writer.last_batch_success_count == 500
    assert writer.last_batch_failure_messages == set()


def test_partial_batches():
    client = partial_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    expected_records = []
    for x in range(5):
        queue_and_record(writer, expected_records, f"message {x}")
    # first attempt
    assert writer.flush() == True
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records)
    assert writer.last_batch_size == 5
    assert writer.last_batch_success_count == 3
    assert writer.last_batch_failure_messages == set([THROTTLING_MESSAGE])
    del expected_records[4]
    del expected_records[2]
    del expected_records[0]
    assert queued_records(writer) == expected_records
    # second attempt
    client.reset_mock()
    assert writer.flush() == True
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records)
    assert writer.last_batch_size == 2
    assert writer.last_batch_success_count == 1
    assert writer.last_batch_failure_messages == set([THROTTLING_MESSAGE])
    del expected_records[0]
    assert queued_records(writer) == expected_records
    # third attempt
    client.reset_mock()
    assert writer.flush() == False
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records)
    assert writer.last_batch_size == 1
    assert writer.last_batch_success_count == 1
    assert writer.last_batch_failure_messages == set()
    assert writer._queue == []


def test_fully_throttled_batches():
    client = throttled_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    expected_records = []
    for x in range(499):
        queue_and_record(writer, expected_records, f"message {x}")
    # at this point the queue is full; next enqueue will trigger flush()
    client.assert_not_called()
    assert queued_records(writer) == expected_records
    queue_and_record(writer, expected_records, "over the top")
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records[:500])
    assert len(writer._queue) == 500
    # the next call should try to flush again, with same set of 500 records
    client.reset_mock()
    queue_and_record(writer, expected_records, "piling on")
    client.put_records.assert_called_once_with(StreamName=DEFAULT_STREAM_NAME, Records=expected_records[:500])
    assert len(writer._queue) == 501


def test_empty_flush():
    client = Mock(spec=[]) # fail if any method called
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    assert writer.flush() == False


def test_utf8():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    message = "\u00C0" * 5
    partkey = "\u00C1" * 5
    writer.enqueue(message, partkey)
    assert queued_records(writer) == [
        {
            'Data': message.encode(),
            'PartitionKey': partkey
        }
    ]


def test_non_string_partition_key():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    writer.enqueue("irrelevant", 123)
    assert queued_records(writer) == [
        {
            'Data': b"irrelevant",
            'PartitionKey': "123"
        }
    ]


def test_oversize_message():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    partition_key = "testmessage"
    good_length = 1024 * 1024 - len(partition_key)
    good_message = "A" * good_length
    writer.enqueue(good_message, partition_key)
    with pytest.raises(ValueError, match=r"message too large.*") as excinfo:
        writer.enqueue(good_message + "B", partition_key)
    assert len(writer._queue) == 1
    assert queued_record(writer,0) == (good_message.encode(), ANY)


def test_oversize_partition_key():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    good_partition_key = "A" * 256
    writer.enqueue("irrelevant", good_partition_key)
    with pytest.raises(ValueError, match=r"partition key too large.*") as excinfo:
        writer.enqueue("irrelevant", good_partition_key + "B")
    assert len(writer._queue) == 1
    assert queued_record(writer,0) == (ANY, good_partition_key)


def test_oversize_partition_key_utf8():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    good_partition_key = "\u00C0" * 128
    writer.enqueue("irrelevant", good_partition_key)
    with pytest.raises(ValueError, match=r"partition key too large.*") as excinfo:
        writer.enqueue("irrelevant", good_partition_key + "B")
    assert len(writer._queue) == 1
    assert queued_record(writer,0) == (ANY, good_partition_key)


def test_convert_non_string_to_json():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    writer.enqueue({"foo": 123})
    assert queued_record(writer,0) == (b'{"foo": 123}', ANY)


def test_batch_logging_enabled(caplog):
    client = partial_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME, log_batches=True)
    caplog.set_level(logging.DEBUG)
    for x in range(5):
        writer.enqueue(f"message {x}")
    writer.flush()
    assert len(caplog.records) == 2
    assert re.match(f"sending 5.*to stream {DEFAULT_STREAM_NAME}", 
                    caplog.records[0].msg)
    assert re.match(f"sent 5.*to stream {DEFAULT_STREAM_NAME}; 3 successful; errors.*{THROTTLING_MESSAGE}",
                    caplog.records[1].msg)


def test_batch_logging_disabled(caplog):
    client = partial_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_NAME)
    caplog.set_level(logging.DEBUG)
    for x in range(5):
        writer.enqueue(f"message {x}")
    writer.flush()
    assert len(caplog.records) == 0


def test_stream_arn():
    client = happy_mock_client()
    writer = KinesisWriter(client, DEFAULT_STREAM_ARN)
    expected_records = [
        {
            'Data': b"something",
            'PartitionKey': "else"
        },
    ]
    writer.enqueue("something", "else")
    assert queued_records(writer) == expected_records
    assert writer.flush() == False
    client.put_records.assert_called_once_with(StreamARN=DEFAULT_STREAM_ARN, Records=expected_records)
