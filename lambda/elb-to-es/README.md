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

This must be done on a non-Debian Linux (because Debian [broke pip's -t option](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=830892)).
If that doesn't match what you have, I recommend spinning up a `t2.micro` EC2 instance, running Amazon Linux.

You'll need to have Python 3 with PIP, along with WGet and Zip. If you're running Amazon Linux, this will get them:

```
sudo yum install python3 python3-pip wget zip
```

Now you can create the deployment directory, download the Lambda source, install necessary modules, and zip it into an upload bundle.

```
mkdir elb-to-es
cd elb-to-es

wget https://raw.githubusercontent.com/kdgregory/aws-misc/master/elb-to-es/lambda_function.py

pip3 install -t `pwd` requests aws-requests-auth

zip -r /tmp/elb-to-es.zip .
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
