# Copyright 2024-2025, Keith D Gregory
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

get_object_body_mock = None     # TODO - move this into the class, because we now inject an instance

class MockImpl:

    def __init__(self):
        pass


    def configure(self, keys=None, objects=None, max_items=9999999, delete_failure_keys=None, delete_failure_reason=None):
        self._keys = keys or []
        self._objects = objects or {}
        self._max_items = max_items
        self._delete_failure_keys = set(delete_failure_keys or [])
        self._delete_failure_reason = delete_failure_reason


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
        print(f"list_objects_v2 called: Bucket: {Bucket}, Prefix: {Prefix}, Delimiter: {Delimiter}, ContinuationToken: {ContinuationToken}")
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
        print(f"keys: {keys}")
        keys, next_token = self._apply_continuation_token(keys, ContinuationToken)
        result = {}
        if Delimiter:
            result['Contents'] = [ {'Key': key } for key in keys if not key.endswith(Delimiter)]
            result['CommonPrefixes'] = [ {'Prefix': key } for key in keys if key.endswith(Delimiter)]
        else:
            result['Contents'] = [ {'Key': key } for key in keys]
            result['CommonPrefixes'] = []
        # S3 only provides the child elements that have data, so delete those that don't for this call
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


    def delete_objects(self, Bucket, Delete):
        to_delete = set([obj['Key'] for obj in Delete.get('Objects', [])])
        deleted = []
        errors = []
        for key in to_delete:
            if key in self._delete_failure_keys:
                errors.append(key)
            elif key in self._keys:
                deleted.append(key)
                self._keys.remove(key)
        return {
            "Deleted": [{"Key": key} for key in deleted],
            "Errors": [{"Key": key, "Code": self._delete_failure_reason} for key in errors],
        }


@pytest.fixture
def mock_impl():
    return MockImpl()


@pytest.fixture
def mock(mock_impl):
    mock = Mock(spec=["delete_objects", "get_object", "list_objects_v2"])
    mock.delete_objects.side_effect = lambda *args, **kwargs: mock_impl.delete_objects(*args, **kwargs)
    mock.get_object.side_effect = lambda *args, **kwargs: mock_impl.get_object(*args, **kwargs)
    mock.list_objects_v2.side_effect = lambda *args, **kwargs: mock_impl.list_objects_v2(*args, **kwargs)
    return mock


###
### Test cases
###

def test_list_keys_basic_operation(mock, mock_impl):
    expected_keys = [ "argle", "foo/bar", "foo/baz" ]
    mock_impl.configure(keys=expected_keys)
    keys = [key for key in s3.list_keys(mock, TEST_BUCKET)]
    assert keys == expected_keys
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
    ])


def test_list_keys_with_prefix(mock, mock_impl):
    all_keys = [ "argle", "foo/bar", "foo/baz" ]
    expected_keys = [ "foo/bar", "foo/baz" ]
    mock_impl.configure(keys=all_keys)
    keys = [key for key in s3.list_keys(mock, TEST_BUCKET, "foo/")]
    assert keys == expected_keys
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/"),
    ])


def test_list_keys_pagination(mock, mock_impl):
    expected_keys = [ "argle", "foo/bar", "foo/baz" ]
    mock_impl.configure(keys=expected_keys, max_items=2)
    keys = [key for key in s3.list_keys(mock, TEST_BUCKET)]
    assert keys == expected_keys
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
        call(Bucket=TEST_BUCKET, ContinuationToken="2")
    ])


def test_list_keys_pagination_with_prefix(mock, mock_impl):
    expected_keys = [ "argle", "foo/bar", "foo/baz" ]
    mock_impl.configure(keys=expected_keys, max_items=1)
    keys = [key for key in s3.list_keys(mock, TEST_BUCKET)]
    assert keys == expected_keys
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
        call(Bucket=TEST_BUCKET, ContinuationToken="1"),
        call(Bucket=TEST_BUCKET, ContinuationToken="2")
    ])


def test_list_keys_empty(mock, mock_impl):
    expected_keys = []
    mock_impl.configure(keys=expected_keys)
    keys = [key for key in s3.list_keys(mock, TEST_BUCKET)]
    assert keys == expected_keys
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET),
    ])


def test_list_children_basic_operation(mock, mock_impl):
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    expected_result = [ "argle", "foo/" ]
    mock_impl.configure(keys=keys)
    result = [prefix for prefix in s3.list_children(mock, TEST_BUCKET)]
    assert result == expected_result
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delimiter="/"),
    ])


def test_list_children_with_prefix(mock, mock_impl):
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    expected_prefixes = [ "boffo", "bar/", "biff/" ]
    mock_impl.configure(keys=keys)
    prefixes = [prefix for prefix in s3.list_children(mock, TEST_BUCKET, prefix="foo/")]
    assert prefixes == expected_prefixes
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/"),
    ])


def test_list_children_paginated(mock, mock_impl):
    keys = [ "argle", "foo/bar/baz", "foo/biff/baz", "foo/boffo/baz" ]
    expected_prefixes = [ "bar/", "biff/", "boffo/" ]
    mock_impl.configure(keys=keys, max_items=2)
    prefixes = [prefix for prefix in s3.list_children(mock, TEST_BUCKET, prefix="foo/")]
    assert prefixes == expected_prefixes
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/"),
        call(Bucket=TEST_BUCKET, Prefix="foo/", Delimiter="/", ContinuationToken="2"),
    ])


def test_list_children_empty(mock, mock_impl):
    keys = []
    expected_prefixes = []
    mock_impl.configure(keys=keys)
    prefixes = [prefix for prefix in s3.list_children(mock, TEST_BUCKET)]
    assert prefixes == expected_prefixes
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delimiter="/"),
    ])


def test_get_object_basic_operation(mock, mock_impl):
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    mock_impl.configure(objects={test_key: test_data})
    assert s3.get_object_data(mock, TEST_BUCKET, test_key) == test_data
    get_object_body_mock.__exit__.assert_called()
    mock.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_decompress(mock, mock_impl):
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    mock_impl.configure(objects={test_key: gzip.compress(test_data)})
    assert s3.get_object_data(mock, TEST_BUCKET, test_key, decompress=True) == test_data
    get_object_body_mock.__exit__.assert_called()
    mock.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_nodecompress(mock, mock_impl):
    global last_get_object_body
    test_key = "foo"
    test_data = b'this is something'
    mock_impl.configure(objects={test_key: gzip.compress(test_data)})
    assert s3.get_object_data(mock, TEST_BUCKET, test_key) == gzip.compress(test_data)
    get_object_body_mock.__exit__.assert_called()
    mock.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_decode_string(mock, mock_impl):
    global last_get_object_body
    test_key = "foo"
    test_str = 'this is something'
    test_data = test_str.encode()
    mock_impl.configure(objects={test_key: test_data})
    assert s3.get_object_data(mock, TEST_BUCKET, test_key, encoding='utf-8') == test_str
    get_object_body_mock.__exit__.assert_called()
    mock.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_get_object_nodecode_string(mock, mock_impl):
    global last_get_object_body
    test_key = "foo"
    test_str = 'this is something'
    test_data = test_str.encode()
    mock_impl.configure(objects={test_key: test_data})
    assert s3.get_object_data(mock, TEST_BUCKET, test_key) == test_data
    get_object_body_mock.__exit__.assert_called()
    mock.get_object.assert_has_calls([
        call(Bucket=TEST_BUCKET, Key=test_key),
    ])


def test_delete_prefix_basic_operation(mock, mock_impl):
    print("test_delete_prefix_basic_operation")
    keys = [ "argle", "argle/bargle", "foo", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    mock_impl.configure(keys=keys)
    errors = s3.delete_prefix(mock, TEST_BUCKET, "foo/")
    assert len(errors) == 0
    assert list(s3.list_keys(mock, TEST_BUCKET)) == ["argle", "argle/bargle", "foo" ]
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/"),
    ])
    mock.delete_objects.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delete=ANY),
    ])


def test_delete_prefix_multiple_calls(mock, mock_impl):
    print("test_delete_prefix_multiple_calls")
    keys = [ "argle", "argle/bargle", "foo", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    mock_impl.configure(keys=keys, max_items=2)
    errors = s3.delete_prefix(mock, TEST_BUCKET, "foo/")
    assert len(errors) == 0
    assert list(s3.list_keys(mock, TEST_BUCKET)) == ["argle", "argle/bargle", "foo" ]
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/"),
    ])
    mock.delete_objects.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delete=ANY),
    ])


def test_delete_prefix_with_errors(mock, mock_impl):
    print("test_delete_prefix_with_errors")
    keys = [ "argle", "argle/bargle", "foo", "foo/bar/baz", "foo/biff/baz", "foo/boffo" ]
    delete_failure_keys = ["foo/biff/baz"]
    delete_failure_reason = "testing"
    mock_impl.configure(keys=keys, delete_failure_keys=delete_failure_keys, delete_failure_reason=delete_failure_reason)
    errors = s3.delete_prefix(mock, TEST_BUCKET, "foo/")
    assert len(errors) == 1
    assert errors["foo/biff/baz"] == delete_failure_reason
    assert list(s3.list_keys(mock, TEST_BUCKET)) == ["argle", "argle/bargle", "foo", "foo/biff/baz"]
    mock.list_objects_v2.assert_has_calls([
        call(Bucket=TEST_BUCKET, Prefix="foo/"),
    ])
    mock.delete_objects.assert_has_calls([
        call(Bucket=TEST_BUCKET, Delete=ANY),
    ])
