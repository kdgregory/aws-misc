This is a module that enables JSON output from the standard Python `logging` library.
It is intended to be uploaded as (or part of) a Lambda layer, and will include Lambda
execution information in the JSON output.

The module itself is [jsonlogging.py](python/jsonlogging.py); it lives in the `python`
directory because that's how Lambda wants to see modules in layers. There are two parts
to this module:

* `JSONFormatter` is a formatter for the Python logging framework that converts a
  `LogRecord` into JSON, using a format similar to the `JSONLayout` class from my
  [AWS appenders for Java](https://github.com/kdgregory/log4j-aws-appenders) (because
  high-level consistency is important in structured logging).
* `configure_logging()` is a function that is intended to be called from the Lambda
  handler. It ensures that the logging framework uses `JSONFormatter` (by default it
  uses its own formatter), and extracts information from the current invocation
  context (which is why it's called from the _inside_ the handler, and _not_ as part
  of the Lambda initialization code).

To prepare this for use, simply ZIP it up (possibly with other modules) and upload as
a [layer](https://console.aws.amazon.com/lambda/home#/layers):

```
zip /tmp/layer.zip python/jsonlogging.py
```

Next, write your Lambda function to use this layer. I've included a [sample](lambda_function.py)
that expects the "Hello World" test event as input:

```
import json
import jsonlogging
import logging


def lambda_handler(event, context):
    jsonlogging.configure_logging(context, tags={'argle': 'bargle'})
    logging.info("key 1 = " + event.get('key1'))
    return None
```

When you run it, you get this as output:

```
START RequestId: 700c98fd-6f76-4837-9abf-13a73766402f Version: $LATEST
{"timestamp": "2019-10-04T10:57:29.432Z", "level": "INFO", "logger": "root", "message": "key 1 = value1", "processId": 7, "thread": "MainThread", "locationInfo": {"fileName": "lambda_function.py", "lineNumber": 8}, "tags": {"argle": "bargle"}, "lambda": {"requestId": "700c98fd-6f76-4837-9abf-13a73766402f", "functionName": "LoggingExample", "functionVersion": "$LATEST"}}
END RequestId: 700c98fd-6f76-4837-9abf-13a73766402f
REPORT RequestId: 700c98fd-6f76-4837-9abf-13a73766402f	Duration: 6.85 ms	Billed Duration: 100 ms	Memory Size: 128 MB	Max Memory Used: 55 MB	Init Duration: 125.07 ms	
```

Note that the JSON output is surrounded by standard Lambda invocation report messages; to get
rid of them you need to transform the CloudWatch output, [perhaps while writing it somewhere
else](https://github.com/kdgregory/aws-misc/tree/master/lambda/cloudwatch-log-transform).
