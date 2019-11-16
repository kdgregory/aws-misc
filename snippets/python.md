# Useful Python functions

## IAM / STS

### Get a boto client, optionally assuming a role

This is primarily intended for code that needs to look at resources in multiple places
(for example, a cleanup script). Will return either a low-level client or a resource.

```
import boto3
import uuid


def create_boto_client(service, region=None, roleArn=None, duration=None, policy=None, lowLevel=False):
    """ Creates a Boto3 client or resource, optionally assuming a role.
    
        service  - the name of the service (eg, 'iam')
        region   - the name of the region (required if not available from configuration/environment)
        roleArn  - optional role to assume
        duration - optional duration for role assumption (too high and call will fail)
        policy   - optional policy that will be used to limit role permissions
        lowLevel - if True, returns a low-level client; otherwise returns a resource

        Credentials/region are provided by default profile or environment.
    """
    clientArgs = {}
    if roleArn:
        stsClient = boto3.client('sts')
        assumeRoleArgs = {}
        assumeRoleArgs['RoleArn'] = roleArn
        assumeRoleArgs['RoleSessionName'] = str(uuid.uuid4())
        if duration:
            assumeRoleArgs['DurationSeconds'] = duration
        if policy:
            assumeRoleArgs['Policy'] = policy
        creds = stsClient.assume_role(**assumeRoleArgs)['Credentials']
        clientArgs['aws_access_key_id'] = creds['AccessKeyId']
        clientArgs['aws_secret_access_key'] = creds['SecretAccessKey']
        clientArgs['aws_session_token'] = creds['SessionToken']
    if region:
        clientArgs['region_name'] = region
    if lowLevel:
        return boto3.client(service, **clientArgs)
    else:
        return boto3.resource(service, **clientArgs)
```

Examples:

* Create a high-level client for accessing EC2 resources, using default region:

  ```
  client = create_boto_client('ec2')
  ```

* Create a high-level client for accessing EC2 resources in us-east-2:

  ```
  client = create_boto_client('ec2', 'us-east-2')
  ```

* Create a high-level client using an assumed role with limited duration:

  ```
  client = create_boto_client('ec2', 'us-east-1', 'arn:aws:iam::123456789012:role/ExampleAssumableRole', 900)
  ```

* Create a high-level client using an assumed role with default duration and region:

  ```
  client = create_boto_client('ec2', roleArn='arn:aws:iam::123456789012:role/ExampleAssumableRole')
  ```

* Create a low-level client in default region (CloudWatch Logs does not currently have a high-level
  client, so omitting `lowLevel` will result in an exception):

  ```
  client = create_boto_client('logs', lowLevel=True)
  ```

* Create a high-level client with a policy restriction (`ExampleAssumableRole` must grant `s3:PutObject` with a 
  less-restrictive resource constraint):

  ```
  pol = json.dumps({
          "Version": "2012-10-17",
          "Statement": [
              {
                  "Effect": "Allow",
                  "Action": "s3:PutObject",
                  "Resource": "arn:aws:s3:::mybucket/example.txt"
              }
          ]
      })

  client = create_boto_client('s3', roleArn='arn:aws:iam::123456789012:role/ExampleAssumableRole', policy=pol)
  ```

  After doing this, this operation will succeed:

  ```
  client.Bucket('mybucket').upload_file('/tmp/example.txt', 'example.txt')
  ```

  But this one fails with an "Access Denied" error:

  ```
  client.Bucket('mybucket').upload_file('/tmp/example.txt', 'example2.txt')
  ```
