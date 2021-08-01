This function parses Elastic Load Balancer log output, converts it to JSON, and uploads it to ElasticSearch.

It is triggered when the logfile is written to S3, and uses signed requests to the ElasticSearch bulk API.


## Lambda Configuration

6untime: Python 3.6

Required Memory: 256 MB

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

This Lambda requires the third-party `requests` and `aws-requests-auth` modules, so the first step is
retrieving them (actually, the first step is ensuring that you have `pip` installed).

```
pip install -t build -r requirements.txt
```

Next, build the Lambda bundle:

```
cp lambda_function.py build/

cd build
zip -r ../lambda.zip .
cd ..
```

At this point you can either manually create the Lambda function, with permissions and
environment variables described above, or you can upload it to S3 and use the provided
CloudFormation template.


## Deploying with CloudFormation



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
