import base64
import gzip
import json
import logging
import pytest
import re

from unittest.mock import Mock, ANY

import newline_transform, json_transform


###
### Mocks and helpers
###

def create_json_record(message, idx, gzipped):
    record = json.loads(
        """
        {
            "approximateArrivalTimestamp": 1703334983841,
            "kinesisRecordMetadata": {
                "sequenceNumber": "66497449473164937499911881783178893338002328605532524290",
                "subsequenceNumber": 0,
                "partitionKey": "1703334968.9894173",
                "shardId": "shardId-000000000000",
                "approximateArrivalTimestamp": 1703334983841
            }
        }
        """)
    message_bytes = message.encode()
    if gzipped:
        message_bytes = gzip.compress(message_bytes)
    record['recordId'] = f"message-{idx:03d}"
    record['data'] = base64.b64encode(message_bytes).decode()
    return record


def create_event(messages, gzipped):
    event = json.loads(
        """
        {
            "invocationId": "8499d49f-d144-46f2-9019-af29b427dccd",
            "sourceKinesisStreamArn": "arn:aws:kinesis:us-east-1:123456789012:stream/example",
            "deliveryStreamArn": "arn:aws:firehose:us-east-1:123456789012:deliverystream/KDS-S3-whavi",
            "region": "us-east-1",
            "records": []
        }
        """)
    event['records'] = [create_json_record(message, idx, gzipped) for idx,message in enumerate(messages)]
    return event


def invoke_and_extract(lambda_module, messages, gzipped=False):
    event = create_event(messages, gzipped)
    raw_result = lambda_module.lambda_handler(event, {})
    result = []
    for rec in raw_result['records']:
        record_id = rec.get('recordId')
        status = rec.get('result')
        data = rec.get('data')
        if data:
            data = base64.b64decode(data).decode()
        result.append((record_id, status, data))
    return result

###
### Test cases -- note that I test all transforms in this file, in order to reuse helpers
###

def test_newline_basic_operation(caplog):
    caplog.set_level(logging.DEBUG)
    assert invoke_and_extract(newline_transform, ["test 1", "test 2"]) == [
                ("message-000", "Ok", "test 1\n"),
                ("message-001", "Ok", "test 2\n"),
            ]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].msg == "processed 2 records"
                    


def test_newline_leaves_other_whitespace():
    assert invoke_and_extract(newline_transform, ["  test 1  \n", "  test 2 \r\n\r"]) == [
                ("message-000", "Ok", "  test 1  \n"),
                ("message-001", "Ok", "  test 2 \n"),
            ]


def test_json_basic_operation(caplog):
    s1 = json.dumps({"foo": 123})
    s2 = json.dumps({"bar": 456})
    caplog.set_level(logging.DEBUG)
    assert invoke_and_extract(json_transform, [s1, s2]) == [
                ("message-000", "Ok", s1 + "\n"),
                ("message-001", "Ok", s2 + "\n"),
            ]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert re.match(f"processed 2 records.* 2 successful.* 0 dropped.* 0 failed", 
                    caplog.records[0].msg)


def test_json_gzipped():
    s1 = json.dumps({"foo": 123})
    s2 = json.dumps({"bar": 456})
    assert invoke_and_extract(json_transform, [s1, s2], gzipped=True) == [
                ("message-000", "Ok", s1 + "\n"),
                ("message-001", "Ok", s2 + "\n"),
            ]


def test_json_non_objects():
    assert invoke_and_extract(json_transform, ["123", '"abc"']) == [
                ("message-000", "Ok", "123\n"),
                ("message-001", "Ok", "\"abc\"\n"),
            ]


def test_json_bogus():
    results = invoke_and_extract(json_transform, ["123", "abc"])
    assert results == [
                ("message-000", "Ok", "123\n"),
                ("message-001", "ProcessingFailed", "abc"),
            ]


def test_failure_logging(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("LOG_FAILURES", "anything")
    results = invoke_and_extract(json_transform, ["123", "abc"])
    assert results == [
                ("message-000", "Ok", "123\n"),
                ("message-001", "ProcessingFailed", "abc"),
            ]
    assert len(caplog.records) == 2
    assert caplog.records[0].levelname == "DEBUG"
    assert caplog.records[0].msg == "unable to process: b'abc'"
    assert caplog.records[1].levelname == "INFO"
    assert re.match(f"processed 2 records.* 1 successful.* 0 dropped.* 1 failed", 
                    caplog.records[1].msg)


def test_failure_logging_not_enabled(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    # logging only happens when the envar is set
    results = invoke_and_extract(json_transform, ["123", "abc"])
    assert results == [
                ("message-000", "Ok", "123\n"),
                ("message-001", "ProcessingFailed", "abc"),
            ]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert re.match(f"processed 2 records.* 1 successful.* 0 dropped.* 1 failed", 
                    caplog.records[0].msg)


def test_json_dropping(caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("LOG_FAILURES", "anything")
    monkeypatch.setattr(json_transform, "should_drop", lambda x: x.get("foo"))
    s1 = json.dumps({"foo": 123})
    s2 = json.dumps({"bar": 456})
    results = invoke_and_extract(json_transform, [s1, s2])
    assert results == [
                ("message-000", "Dropped", None),
                ("message-001", "Ok", s2 + "\n"),
            ]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "INFO"
    assert re.match(f"processed 2 records.* 1 successful.* 1 dropped.* 0 failed", 
                    caplog.records[0].msg)
