output "lambda" {
  description = "The Lambda function"
  value       = aws_lambda_function.lambda
}


output "execution_role" {
  description = "The Lambda's execution role"
  value       = aws_iam_role.execution_role
}


output "security_group" {
  description = "The marker security group created for an in-VPC Lambda"
  value       = (var.vpc_id != null) ? aws_security_group.marker["1"].id : null
}
