Utility functions that are not associated with a particular service.


## create_client()

Creates a new AWS client using the default session, with various configuration options.

```
from aws_util import create_client

# creates a basic client, just like boto3.client(...)
logs_client = create_client("logs")

# creates a client for a specific region
logs_client = create_client("logs", region_name="us-west-2")

# assumes a role in the current account
logs_client = create_client("logs", role_name="Log4JAppenderTesting")

# assumes a role in the specified account (if allowed)
logs_client = create_client("logs", account="123456789012", role_name="Example")

# assumes a role with the specified ARN, using a specified session identifier
logs_client = create_client("logs", role_arn="arn:aws:iam::123456789012:role/Example", session_name="integration_test")
```


### Invocation

```
def create_client(service, *, region_name=None, account=None, role_name=None, role_arn=None, session_name=None, policy=None, duration=None, log_actions=False):
```

* `service`
  Name of the service, as you would pass to boto3.client()

* `region_name`
  The service region. May be omitted for global services (eg, S3), or if region is provided
  via default user profile or environment variables (note: boto can't determine region when
  running on EC2 with credentials provided by instance profile).

* `account`
  Used with `role_name` to identify an assumed role. If omitted, uses the current (invoking)
  account.

* `role_name`
  The name of a role to assume.

* `role_arn`
  The ARN of a role to assume. If used, do not provide account or role_name.

* `session_name`
  A session name for the role. If omitted, and the client is being created with long-term user
  credentials, then this function will combine the invoker's account and username. If invoked 
  from an existing assumed-role session, will use the name from that session.

* `policy`
  An optional IAM policy, used to restrict the permissions of the assumed role.

* `duration`
  The duration, in seconds, of the role session. May be omitted, in which case this function
  will retrieve the maximum duration for roles in the current account, or a predefined value
  of 8 hours. If the chosen duration is exceeds the roles maximum duration, it will be cut
  in half repeatedly until it is less than or equal to that maximum (this drives the default
  of 8 hours, which will end up at the minimum allowed role duration of 15 minutes).

* `log_actions`
  If True, then this function will log everything that it tries to do (at debug level).


### Caveats and Usage Notes

This function uses the default mechanism for creating internal IAM and STS clients, as well
as for creating clients where an assumed role is not specified.

All exceptions (such as no permission to assume role) are propagated to caller.

There is no attempt to refresh assumed-role credentials.
