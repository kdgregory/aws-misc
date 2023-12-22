# Kinesis Writer

This module provides the `KinesisWriter` class, which accumulates messages and calls
`put_records()` either manually or automatically. More important, it checks for partial
failures and requeues those messages for a future batch.


## Usage

Import the class:

```
from kinesis import KinesisWriter
```

Create a new instance of `KinesisWriter` for every stream that you'll write to:

```
client = boto3.client('kinesis')
writer = KinesisWriter(client, "example")
```

Write your messages. Partition key is optional; if omitted, the writer uses the
stringified value of `time.time()`.

```
writer.enqueue("test message", "test pkey")
writer.enqueue("message without explicit partition key")
```

The writer automatically flushes when it detects a full batch (either by number
of records or aggregate size). However, when you're done writing, there may still
be messages in the queue, so you'll need to call `flush()` manually. But, since
Kinesis may reject some records from a batch, you should call in a loop with a
pause between attempts:

```
while (writer.flush()):
    time.sleep(0.25)
```

### Additional Usage Information

You can pass either a stream name or ARN to the constructor.

The message passed to `enqueue()` may be a `str`, `bytes`, or any Python object
that is convertible to JSON.

You can enable debug-level logging of write attempts by passing `log_batches=True`
to the constructor. This uses the standard Python `logging` module, with a logger
named "KinesisWriter". Each batch is logged both before and after the call to
`put_records()`, and the "after" message reports any record-level errors from the
batch:

```
DEBUG:KinesisWriter:sending 500 messages to stream example
DEBUG:KinesisWriter:sent 500 messages to stream example; 25 successful; errors = {'Rate exceeded for shard shardId-000000000000 in stream example under account 123456789012.'}
```

Note: the writer's internal logger is configured as DEBUG level when enabled; there
is no need to set the root logger to the same level (and, in fact, it's not a good
idea, as you'll log boto3 internals).


### Warnings and Caveats

The stream's existence and your ability to write to it is not verified until the
first call to `flush()` (either explicit or via `enqueue()`).

No attempt is made to avoid throttling (doing so properly requires performing the
`put_records()` call on a background thread). The `PutRecords` API call will reject
records that exceed a shard's throughput, and those will be requeued for a subsequent
call. If you consistently exceed the throughput of your stream, then the queue will
grow until you run out of memory.

This class is not thread-safe. If you want to use from multiple threads, you
must explicitly synchronize access.
