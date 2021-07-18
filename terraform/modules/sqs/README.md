Creates an SQS queue and optional dead-letter queue. In addition, creates managed
producer and consumer policies, and exposes IAM statements that can be composed
into an inline (or other) policy.


## Configuration

By default, this module just creates a single queue. If you specify a retry count
it creates a dead-letter queue and configures the primary queue's redrive policy.

* `name`

  The name of the primary queue. Also used as base name of the dead-letter queue,
  if used.

  Default: none; you must specify this.

* `visibility_timeout_seconds`

  The number of seconds that a message will be invisible to other consumers once
  retrieved.

  Default: 30 (SQS default)

* `message_retention_days`

  The number of days that the primary queue retains unprocessed messages. This module
  uses days for this value, rather than seconds, because I believe that it improves
  readability. You can use a decimal number (eg, 0.5 for half a day), although small
  numbers won't be exact (eg, if you want an hour, 0.0417 is 3602 seconds).

  Default: 4 (SQS default)

* `dlq_retention_days`

  The number of days that the dead letter queue retains unprocessed messages. As with
  `message_retention_days`, this is specified in days.

  Default: the value of `message_retention_days`

* `retry_count`

  The maximum number of times that a message should be delivered before moving
  to the dead-letter queue. Specifying this parameter is the way to create a
  dead-letter queue.

  Default: null (messages will be delivered indefinitely (until they time out
  due to the queue's retention limit).

* `tags`

  A map of name-value pairs that will be associated with the queues and managed
  policies created by this script as tags.

  Default: {}


## Outputs

This module provides the following outputs, for use by consuming modules. All outputs
refer to the created resource, so you can access all attributes of the resource (not
just its name or ARN).

* `primary`

  The primary queue. This is the `aws_sqs_queue` resource, so you will have access to
  all [documented attributes](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue).

* `dead_letter_queue`

  The dead-letter queue if it exists, null if it doesn't. This is also an `aws_sqs_queue`
  resource.

* `producer_policy_arn`

  The ARN of a managed policy that allows writing to the queue.

* `producer_statement`

  A map containing the policy statement that is wrapped by the producer policy. See
  [below](#) for more information.

* `consumer_policy_arn`

  The ARN of a managed policy that allows reading from the queue, updating message
  attributes, and deleting messages.

* `consumer_statement`

  A map containing the policy statement that is wrapped by the consumer policy. See
  [below](#) for more information.


## Examples

In all of the examples below, update `COMMIT` to an appropriate hash. Do not use `trunk`
unless you're OK with deployment configs that may change outside of your control.


### A basic queue

This queue might be appropriate for sending long-running tasks to a fleet of consumers
that are guaranteed to be able to process their messages.


```
module "sqs" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/sqs?ref=COMMIT"

  name                        = "example"
  visibility_timeout_seconds  = 300
  message_retention_days      = 1
}
```


### Enabling a dead-letter queue

This queue is intended for use with a Lambda, so follows the [AWS
recommendation](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#events-sqs-queueconfig)
that the queue's visibility timeout be based on the Lambda timeout (if you don't
do this, and specify a visibility timeout for the queue that's lower than the Lambda
timeout, your deployment will fail).


```
module "sqs" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/sqs?ref=COMMIT"

  name                        = "example"
  visibility_timeout_seconds  = local.lambda_timeout * 6
  message_retention_days      = 1
  retry_count                 = 5
}
```


### Using inline policy statements with a Lambda execution role

Assuming that you're using my [Lambda module](../lambda), this will add an inline
policy allowing reading from the queue. If you attach multiple queues to the same
Lambda, you can add their policy statements into the list of statements.

```
resource "aws_iam_role_policy" "lambda_queue_permissions" {
  role      = module.lambda.execution_role.id
  name      = "SQS_Permissions"
  policy    = jsonencode({
                Version = "2012-10-17"
                Statement = [
                  module.sqs.consumer_policy_statement
                ]
              })
}
```


## Implementation Notes

### Dead-Letter Queue

If you enable a dead-letter queue, it's named after the primary, with the suffix "-dql".
For example, with a primary `foo`, the DLQ is `foo-dlq`. This isn't configuable.

The consumer policy allows reading from both the primary and dead-letter queue. The
producer policy does _not_ permit writing to the DLQ; in most deployments, only SQS
should do that.


### Producer and Consumer Policies

This module creates managed policies for queue producers and consumers. In the simple
case, such as a Lambda that reads from and/or writes to a queue, this is sufficient:
attach the appropriate managed policy to your Lambda's execution role. In more complex
applications, however, you may have many queues, and attempting to control access via
managed policies will quickly exhaust the number of policies that can be attached to
a role.

The solution is to use inline policies: you can attach an unlimited number of inline
policies to a role, as long as the total size of those policies excluding whitespace
is less than 10,240 characters. The exported consumer policy statement (the larger of
the two) are around 250 characters, depending on the length of the queue name.

The drawback to using these policy statements is that they replicate the Effect and
Actions elements of the statement. If you use a truly large number of queues, you
can construct your own policy using a local variable definition like the following
(in which `queueN` refers to an instance of this module):

```
```
