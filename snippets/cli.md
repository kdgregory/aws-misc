# Useful snippets for the AWS CLI


## IAM / STS

### Get current AWS account ID.

Useful for substitution into other commands.

```
aws sts get-caller-identity --output text --query Account
```

### Decode authorization error message.

For those API calls that return a message, it’s a stringified JSON structure and should
be passed through jq to be readable.

```
aws sts decode-authorization-message --encoded-message 'MESSAGE' | jq '.DecodedMessage|fromjson'
```

### List all customer-managed policies

This can be a first step in deleting policies.

```
aws iam list-policies --scope Local --query 'Policies[].Arn'
```


## Cloudwatch Logs

### List all log groups in the current region. 

Easier to copy-paste than using console.

```
aws logs describe-log-groups --query 'logGroups[].logGroupName'
```


### Delete all log groups that match a grep expression.

As written here, used for cleanup after log4j-aws-appenders integration tests:

```
for r in 'us-east-1' 'us-east-2' 'us-west-1' 'us-west-2' ; \
    do for g in $(aws logs describe-log-groups --region $r --query 'logGroups[].logGroupName' | grep IntegrationTest | sed -e 's/[ ",]*//g') ; \
        do echo $r " - " $g
        aws logs delete-log-group --region $r --log-group-name $g ; \
    done ; \
done
```


## EC2

### List all EC2 regions.

Useful as a driver for other commands.

```
aws ec2 describe-regions --query 'Regions[].RegionName | sort(@)' --output text
```

### List all instances running in the current region.

```
aws ec2 describe-instances --query 'Reservations[].Instances[].[LaunchTime, PublicIpAddress, InstanceId, KeyName, InstanceType]' --output table
```

### Iterate through all regions, listing the instances in each.

A useful check to make sure you (or someone else!) hasn't started something and then forgotten about it.

```
for r in $(aws ec2 describe-regions --query 'Regions[].RegionName | sort(@)' --output text) ; \
    do echo $r ; \
    aws ec2 describe-instances --region $r --query 'Reservations[].Instances[].[LaunchTime, PublicIpAddress, InstanceId, KeyName, InstanceType]' --output table ; \
done
```
