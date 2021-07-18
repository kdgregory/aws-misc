output "primary_queue" {
  description = "The primary queue created by this module"
  value       = aws_sqs_queue.primary
}


output "dead_letter_queue" {
  description = "The dead-letter queue created by this module (null if unused)"
  value       = local.has_dlq ? aws_sqs_queue.dlq["1"] : null
}


output "consumer_policy_arn" {
  description = "IAM managed policy for consumers"
  value       = aws_iam_policy.consumer_policy.arn
}


output "producer_policy_arn" {
  description = "IAM managed policy for producers"
  value       = aws_iam_policy.producer_policy.arn
}


output "consumer_policy_statement" {
  description = "Policy statement for consumers"
  value       = local.consumer_policy_statement
}


output "producer_policy_statement" {
  description = "Policy statement for producers"
  value       = local.producer_policy_statement
}
