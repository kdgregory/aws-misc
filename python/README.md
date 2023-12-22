Each of these modules can be copied into a program's source tree, or the entire
directory zipped to form a Lambda layer. At some point I'll add a proper build
script, with a package namespace.

## Running Tests

First, create and activate a virtualenv:

```
python -m venv `pwd`/.venv
. .venv/bin/activate
```

Then, install dependencies:

```
pip install pytest boto3
```

Finally, run the tests:

```
PYTHONPATH=. pytest
```
