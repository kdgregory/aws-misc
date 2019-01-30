List all EC2 regions -- this is useful as a driver for other commands.

```
aws ec2 describe-regions --query 'Regions[].RegionName | sort(@)' --output text
```

List all instances running in the current region.

```
aws ec2 describe-instances --query 'Reservations[].Instances[].[LaunchTime, PublicIpAddress, InstanceId, KeyName, InstanceType]' --output table
```

Iterate through all regions, listing the instances in each. A useful check to make sure
you (or someone else!) hasn't started something and then forgotten about it.

```
for r in $(aws ec2 describe-regions --query 'Regions[].RegionName | sort(@)' --output text) ; \
    do echo $r ; \
    aws ec2 describe-instances --region $r --query 'Reservations[].Instances[].[LaunchTime, PublicIpAddress, InstanceId, KeyName, InstanceType]' --output table ; \
done
```
