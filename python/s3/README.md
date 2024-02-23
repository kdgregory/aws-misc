# S3

This module provides utilities for performing common S3 tasks.


## list_keys

Generator function that returns one object key at a time, invoking the `ListObjectsV2` API
as needed.

```
s3.list_keys(client, bucket, prefix=None)
```

* `client`: a Boto3 `s3` client.
* `bucket`: name of the bucket to list.
* `prefix`: if provided, only provides keys that start with this prefix. If omitted, provides
  all keys in the bucket.


## list_children

Generator function that returns the immediate child components of a given prefix, using the
specified delimiter, and invoking the `ListObjectsV2` API as needed. This function s intended
to replicate traversing a filesystem directory tree, and is _not_ a simple wrapper.

Example: given the prefix `"foo/"`, and keys `"foo.txt"`, `"foo/bar.txt"`, and `"foo/bar/baz.txt"`,
this function returns `"bar.txt"`, and `"bar/"`.

```
s3.list_children(client, bucket, prefix="", delimiter="/"):
```

* `client`: a Boto3 `s3` client.
* `bucket`: name of the bucket to list.
* `prefix`: if provided, only returns children of this prefix. If omitted, returns the
  top-level components in the bucket.
* `delimiter`: the delimiter between components of a key. By default this is a slash, but
  you can use anything (eg, `#` or `.`).


## get_object_data

Retrieves the contents of an object, closing the `StreamingBody`, and optionally decompressing
or converting to a string. 

```
s3.get_object_data(client, bucket, key, decompress=False, encoding=None):
```

* `client`: a Boto3 `s3` client.
* `bucket`: identifies the bucket.
* `key`: identifies the object in that bucket.
* `decompress`: if `True`, and the contents of the object appear to be a GZIP file, then
  returns the uncompressed data.
* `encoding`: if provided, this function calls the `bytes.decode()` function with the
  object contents (uncompressed) and the specified encoding.
