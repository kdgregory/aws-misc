This function parses Elastic Load Balancer log output, converts it to JSON, and uploads it to ElasticSearch.

It is triggered when the logfile is written to S3, and uses signed requests to the ElasticSearch bulk API.


## Lambda Configuration

Runtime: Python 3.6

Required Memory: 128 MB

Timeout: 30 sec


## Environment variables

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the ElasticSearch cluster
* `BATCH_SIZE`: the number of logfile lines that will be posted as a single batch. This is dependent on
  the memory assigned to the Lambda function: the default is sufficient for 250 or so rows.
* IAM session identity: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`


## Permissions Required

* `AWSLambdaBasicExecutionRole`
* `es:ESHttpPost`
* `s3:GetObject`


## Building the Deployment Bundle

```
pip install aws-requests-auth -t `pwd`

zip -r /tmp/elb_to_es.zip .
```


## Additional Information

The logfile is retrieved from S3 and stored in the Lambda's temporary directory. This means
that it can only process files that are smaller than approximately 512 MB.

The ElasticSearch cluster must grant permission to the Lambda function. Assuming that your
cluster currently grants access by IP, you can add a statement like the following (changing
`ACCOUNT_ID`, `ROLE_NAME`, and `CLUSTER_NAME`):

```
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
  },
  "Action": "es:ESHttpPost",
  "Resource": "arn:aws:es:us-east-1:ACCOUNT_ID:domain/CLUSTER_NAME/*"
}
```
