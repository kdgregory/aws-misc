# Copyright 2024, Keith D Gregory
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

import gzip
import io
import logging
import pytest
import re
import time
import uuid

from botocore.response import StreamingBody
from unittest.mock import Mock, ANY, call

import s3


###
### Mocks and helpers
###

TEST_BUCKET = "example"

# this is how we assert that the StreamingBody was closed
get_object_body_mock = None

class MockImpl:

    def __init__(self, keys, objects, max_items):
        self._keys = keys
        self._max_items = max_items
        self._objects = objects if objects else {}


    def get_object(self, Bucket=None, Key=None):
        global get_object_body_mock
        data = self._objects[Key]  # let this throw if a bad test
        body = StreamingBody(io.BytesIO(data), len(data))
        get_object_body_mock = Mock()
        get_object_body_mock.__enter__ = Mock(side_effect=lambda *args, **kwargs: body.__enter__(*args, **kwargs))
        get_object_body_mock.__exit__ = Mock(side_effect=lambda *args, **kwargs: body.__exit__(*args, **kwargs))
        return {
            'Body': get_object_body_mock
        }


    def list_objects_v2(self, Bucket=None, Prefix="", Delimiter=None, ContinuationToken=None):
        if Prefix:
            keys = [ key for key in self._keys if key.startswith(Prefix) ]
            prefix_length = len(Prefix)
        else:
            keys = [ key for key in self._keys ]
            prefix_length = 0
        if Delimiter:
            sans_prefix = [ key[prefix_length:] for key in keys ]
            # this step uses an explicit loop to ensure order remains
            seen = set()
            filtered = []
            for key in sans_prefix:
                if key.find(Delimiter) > 0:
                    key = key[:key.find(Delimiter) + 1]
                    if not key in seen:
                        filtered.append(key)
                        seen.add(key)
                else:
                    filtered.append(key)
            keys = [ f"{Prefix}{key}" for key in filtered ]
        keys, next_token = self._apply_continuation_token(keys, ContinuationToken)
        result = {}
        if Delimiter:
            result['Contents'] = [ {'Key': key } for key in keys if not key.endswith(Delimiter)]
            result['CommonPrefixes'] = [ {'Prefix': key } for key in keys if key.endswith(Delimiter)]
        else:
            result['Contents'] = [ {'Key': key } for key in keys]
            result['CommonPrefixes'] = []
        # S3 only provides the child elements that have data; easier to delete after the fact
        if not result['Contents']:
            del result['Contents']
        if not result['CommonPrefixes']:
            del result['CommonPrefixes']
        if next_token:
            result['IsTruncated'] = True
            result['NextContinuationToken'] = next_token
        return result


    def _apply_continuation_token(self, values, token):
        if token:
            start = int(token)
        else:
            start = 0
        count = min(len(values) - start, self._max_items)
        finish = start + count
        if finish >= len(values):
            return values[start:], None
        else:
            return values[start:finish], str(finish)


def create_mock_client(keys=None, objects=None, max_items=99999):
    impl = MockImpl(keys=keys, objects=objects, max_items=max_items)
    mock = Mock(spec=["get_object", "list_objects_v2"])
    mock.get_object.side_effect = lambda *args, **kwargs: impl.get_object(*args, **kwargs)
    mock.list_objects_v2.side_effect = lambda *args, **kwargs: impl.list_objects_v2(*args, **kwargs)
    return mock


###
### Test cases
###

def test_list_keys_basic_operation():
    expected_keys = [ "argle", "foo/bar", "foo/baz" ]
    client = create_mock_client(keys=expected_keys)
    keys = [key for key in s3.list_keys(client, TEST_BUCKET)]
    assert keys == expected_keys
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
    ])


def test_list_keys_with_prefix():
    all_keys = [ "argle", "foo/bar", "foo/baz" ]
    expected_keys = [ "foo/bar", "foo/baz" ]
    client = create_mock_client(keys=all_keys)
    keys = [key for key in s3.list_keys(client, TEST_BUCKET, "foo/")]
    assert keys == expected_keys
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/"),
    ])


def test_list_keys_pagination():
    expected_keys = [ "argle", "foo/bar", "foo/baz" ]
    client = create_mock_client(keys=expected_keys, max_items=2)
    keys = [key for key in s3.list_keys(client, TEST_BUCKET)]
    assert keys == expected_keys
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
        call(Bucket=TEST_BUCKET, ContinuationToken="2")
    ])


def test_list_keys_empty():
    expected_keys = []
    client = create_mock_client(keys=expected_keys)
    keys = [key for key in s3.list_keys(client, TEST_BUCKET)]
    assert keys == expected_keys
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
    ])


def test_list_children_basic_operation():
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    expected_result = [ "argle", "foo/" ]
    client = create_mock_client(keys=keys)
    result = [prefix for prefix in s3.list_children(client, TEST_BUCKET)]
    assert result == expected_result
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delimiter="/"),
    ])


def test_list_children_with_prefix():
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    expected_prefixes = [ "boffo", "bar/", "biff/" ]
    client = create_mock_client(keys=keys)
    prefixes = [prefix for prefix in s3.list_children(client, TEST_BUCKET, prefix="foo/")]
    assert prefixes == expected_prefixes
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/"),
    ])


def test_list_children_paginated():
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo/baz" ]
    expected_prefixes = [ "bar/", "biff/", "boffo/" ]
    client = create_mock_client(keys=keys, max_items=2)
    prefixes = [prefix for prefix in s3.list_children(client, TEST_BUCKET, prefix="foo/")]
    assert prefixes == expected_prefixes
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/"),
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/", ContinuationToken="2"),
    ])


def test_list_children_empty():
    keys = []
    expected_prefixes = []
    client = create_mock_client(keys=keys)
    prefixes = [prefix for prefix in s3.list_children(client, TEST_BUCKET)]
    assert prefixes == expected_prefixes
    client.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delimiter="/"),
    ])


def test_get_object_basic_operation():
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    client = create_mock_client(objects={test_key: test_data})
    assert s3.get_object_data(client, TEST_BUCKET, test_key) == test_data
    get_object_body_mock.__exit__.assert_called()
    client.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_decompress():
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    client = create_mock_client(objects={test_key: gzip.compress(test_data)})
    assert s3.get_object_data(client, TEST_BUCKET, test_key, decompress=True) == test_data
    get_object_body_mock.__exit__.assert_called()
    client.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_nodecompress():
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    client = create_mock_client(objects={test_key: gzip.compress(test_data)})
    assert s3.get_object_data(client, TEST_BUCKET, test_key) == gzip.compress(test_data)
    get_object_body_mock.__exit__.assert_called()
    client.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_decode_string():
    global last_get_object_body
    test_key = "foo"
    test_str = 'this is something'
    test_data = test_str.encode()
    client = create_mock_client(objects={test_key: test_data})
    assert s3.get_object_data(client, TEST_BUCKET, test_key, encoding='utf-8') == test_str
    get_object_body_mock.__exit__.assert_called()
    client.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_nodecode_string():
    global last_get_object_body
    test_key = "foo"
    test_str = 'this is something'
    test_data = test_str.encode()
    client = create_mock_client(objects={test_key: test_data})
    assert s3.get_object_data(client, TEST_BUCKET, test_key) == test_data
    get_object_body_mock.__exit__.assert_called()
    client.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])
