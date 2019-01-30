## Cloudwatch Logs

List all log groups in the current region. Easier to copy-paste than using console.

```
aws logs describe-log-groups --query 'logGroups[].logGroupName'
```


Delete all log groups that match a grep expression. As written here, used for cleanup after
log4j-aws-appenders integration tests:

```
for r in 'us-east-1' 'us-east-2' 'us-west-1' 'us-west-2' ; \
    do for g in $(aws logs describe-log-groups --region $r --query 'logGroups[].logGroupName' | grep IntegrationTest | sed -e 's/[ ",]*//g') ; \
        do echo $r " - " $g
        aws logs delete-log-group --region $r --log-group-name $g ; \
    done ; \
done
```
