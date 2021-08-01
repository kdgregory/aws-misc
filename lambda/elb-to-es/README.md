This function parses Elastic Load Balancer log output, converts it to JSON, and uploads it to ElasticSearch.

It is triggered when the logfile is written to S3, and uses signed requests to the ElasticSearch bulk API.


## Configuration

You can deploy the Lambda either inside or outside of a VPC. As a general rule, deploy it wherever you've
deployed your Elasticsearch cluster. If deployed inside a VPC, it must be able to access files stored on
S3, either via NAT or VPC Gateway. 

Basic Lambda configuration:

  * Runtime: Python 3.6+
  * Required Memory: 512 MB (driven more by CPU allotment than actual memory usage)
  * Timeout: 30 sec

IAM Permissions:

* `AWSLambdaBasicExecutionRole`/`AWSLambdaVPCAccessExecutionRole` or equivalent explicit policies.
* `es:ESHttpPost`
* `s3:GetObject`

Environment variables:

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the ElasticSearch cluster

* `BATCH_SIZE`: the number of logfile lines that will be posted as a single batch. This is dependent on
  the memory assigned to the Lambda function: the default is sufficient for 1,000 or more rows.

* IAM session identity: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`.
  These are used to configure the `aws-requests-auth` module. They are provided by the Lambda runtime
  but must be explicitly configured if you want to run locally.


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

The template [cloudformation.yml](cloudformation.yml) creates the Lambda from a deployment
bundle stored on S3.  It also creates the Lambda's execution role and configures its
environment variables.

There are several parameters that you must configure for this template. For example, using
my [cf-runner](../../utils/cf-runner.py) script to deploy:

```
cf-runner.py ALB-To-Elasticsearch \
             cloudformation.yml \
             SourceBucket=com-example-deployment \
             SourceKey=alb-to-es.zip \
             LogsBucket=com-example-logs \
             LogsPrefix=LoadBalancer/ \
             ElasticsearchHostName=search-logs-9hwrfm5ip2md537eqpt5jspqm.us-east-1.es.amazonaws.com \
             ElasticsearchArn=arn:aws:es:us-east-1:123456789012:domain/logs
```

One thing that the template does _not_ do is configure the bucket to notify the Lamdba.
With CloudFormation, notifications must be configured at the time you create the bucket.
The simplest solution to this problem is to update the Lambda's trigger in the Console.
While you _could_ create the Lambda before the bucket, and then set up the notification
when creating the bucket, [that has its own caveats](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket-notificationconfig.html).


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
