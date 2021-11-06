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


### List organization accounts, sorting by name

Will return an error if the account is not a member of the organization or is not allowed to
get the account list (really, if it's not the root account).

```
aws organizations list-accounts --output table --query 'sort_by(Accounts[],&Name)[].[Id,Name]'
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


## EC2 / VPC

### List all EC2 regions.

Useful as a driver for other commands.

```
aws ec2 describe-regions --query 'Regions[].RegionName | sort(@)' --output text
```

### List all VPCs and Subnets in current region

This outputs the list as a table showing VPC ID, Subnet ID, Availability Zone, and Subnet Name.
The output is sorted by VPC and availability zone (assuming the sort_by operation is stable).

```
aws ec2 describe-subnets --query "sort_by(sort_by(Subnets, &AvailabilityZone), &VpcId)[*].[VpcId, SubnetId, AvailabilityZone, Tags[?Key=='Name'].Value|[0]]" --output table
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
