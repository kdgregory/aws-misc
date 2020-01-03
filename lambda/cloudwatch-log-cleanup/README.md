Lambda function to delete CloudWatch log streams that have exceeded their group's
retention period. This is needed because CloudWatch will delete the messages but
not the streams; in an environment that creates lots of streams (like Lambda), you
will end up with lots of empty streams.

## Lambda Configuration

* Runtime: Python 3.7
* Default memory (128M) should be sufficient unless you have an extraordinary
  number of groups/streams.
* Timeout depends on the number of groups/streams, but 60 seconds should be
  more than sufficient.
* Run outside of VPC; needs access to CloudWatch Logs endpoint.
* Trigger via scheduled CloudWatch Event.

## Permissions Required

* `logs:DeleteLogStream`
* `logs:DescribeLogGroups`
* `logs:DescribeLogStreams`
* `logs:GetLogEvents`
