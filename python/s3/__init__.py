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

import boto3
import gzip


def list_keys(client, bucket, prefix=None):
    """ A generator function that invokes ListObjectsV2 as needed to list all
        keys with a given prefix.

        client  - The Boto3 S3 client
        bucket  - The name of the bucket
        prefix  - The prefix for keys to be retrieved.
        """
    args = {}
    args['Bucket'] = bucket
    if prefix:
        args['Prefix'] = prefix
    while True:
        print(f"calling list_objects: {args}")
        resp = client.list_objects_v2(**args)
        for rec in resp['Contents']:
            yield rec['Key']
        if resp.get('IsTruncated'):
            args['ContinuationToken'] = resp['NextContinuationToken']
        else:
            break


def list_children(client, bucket, prefix="", delimiter="/"):
    """ A generator function that invokes ListObjectsV2 as needed to list all
        immediate children of the provided prefix.

        This function is intended to imited filesystem traversal, so unlike
        ListObjectsV2, the provided prefix (if any) is stripped from the
        results. For example, given a prefix of "foo/", and with keys "foo.txt",
        "foo/bar.txt" and "foo/bar/baz.txt", this function will return "bar.txt"
        and "bar/".

        client      - The Boto3 S3 client
        bucket      - The name of the bucket
        prefix      - The leading component of the child prefix; omit to
                      retrieve prefixes from the root of the bucket.
        delimiter   - The delimited between prefix components. Only specify if
                      you do something other than mimicing a directory tree.
        """
    args = {}
    args['Bucket'] = bucket
    args['Delimiter'] = delimiter
    if prefix:
        args['Prefix'] = prefix
    while True:
        print(f"calling list_objects: {args}")
        resp = client.list_objects_v2(**args)
        for rec in resp['Contents']:
            yield rec['Key'][len(prefix):]
        for rec in resp['CommonPrefixes']:
            yield rec['Prefix'][len(prefix):]
        if resp.get('IsTruncated'):
            args['ContinuationToken'] = resp['NextContinuationToken']
        else:
            break


def get_object_data(client, bucket, key, decompress=False, encoding=None):
    """ Retrieves a file from S3, optionally uncompressing it (GZip only) and
        decoding it as a string. Beware that retrieving large files may cause
        out-of-memory errors.

        client      - The Boto3 S3 client
        bucket      - The name of the bucket
        prefix      - The key to retrieve.
        uncompress  - If True, and the file uses a recognized compression format
                      (at present, only GZip), it will be uncompressed.
        encoding    - If provided, this function will attempt to convert the
                      retrieved bytes into a string with the specified encoding.
        """
    resp = client.get_object(Bucket=bucket, Key=key)
    with resp['Body'] as body:
        data = body.read()
        if decompress and data.startswith(b'\x1f\x8b'):
            data = gzip.decompress(data)
        if encoding:
            data = data.decode(encoding=encoding)
        return data
