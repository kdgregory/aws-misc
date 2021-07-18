terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 3.40.0"
    }
  }
}


locals {
  aws_account_id              = data.aws_caller_identity.current.account_id
  aws_region                  = data.aws_region.current.name

  has_dlq                     = var.retry_count != null
  dlq_iter                    = local.has_dlq ? toset(["1"]) : toset([])
  redrive_policy              = local.has_dlq ? jsonencode({
                                  deadLetterTargetArn = aws_sqs_queue.dlq["1"].arn
                                  maxReceiveCount     = var.retry_count
                                  }) : null
  dlq_retention_days          = (var.dlq_retention_days != null) ? var.dlq_retention_days : var.message_retention_days

  consumer_policy_statement   = {
                                  Effect   = "Allow"
                                  Action = [
                                      "sqs:ChangeMessageVisibility",
                                      "sqs:DeleteMessage",
                                      "sqs:GetQueueAttributes",
                                      "sqs:GetQueueUrl",
                                      "sqs:ReceiveMessage"
                                  ]
                                  Resource = concat(
                                    [ aws_sqs_queue.primary.arn ],
                                    (local.has_dlq ? [ aws_sqs_queue.dlq["1"].arn ] : [])
                                  )
                                }
  producer_policy_statement   = {
                                  Effect   = "Allow"
                                  Action = [
                                      "sqs:GetQueueAttributes",
                                      "sqs:GetQueueUrl",
                                      "sqs:SendMessage"
                                  ]
                                  Resource = [
                                    aws_sqs_queue.primary.arn
                                  ]
                                }
}


data "aws_caller_identity" "current" {}
data "aws_region" "current" {}


resource "aws_sqs_queue" "primary" {
  name                        = var.name
  visibility_timeout_seconds  = var.visibility_timeout_seconds
  message_retention_seconds   = floor(var.message_retention_days * 86400)
  redrive_policy              = local.redrive_policy

  tags                        = var.tags
}


resource "aws_sqs_queue" "dlq" {
  for_each                    = local.dlq_iter

  name                        = "${var.name}-dlq"
  visibility_timeout_seconds  = var.visibility_timeout_seconds
  message_retention_seconds   = floor(local.dlq_retention_days * 86400)

  tags                        = var.tags
}


resource "aws_iam_policy" "consumer_policy" {
  name        = "${var.name}-${local.aws_region}-consumer"
  path        = "/"
  description = "Allows retrieving messages from the ${var.name} SQS queue and its dead-letter queue (if any)"
  policy      = jsonencode({
                  Version = "2012-10-17"
                  Statement = [ local.consumer_policy_statement ]
                })
  tags        = var.tags
}


resource "aws_iam_policy" "producer_policy" {
  name        = "${var.name}-${local.aws_region}-producer"
  path        = "/"
  description = "Allows sending messages to the ${var.name} SQS queue"
  policy      = jsonencode({
                  Version = "2012-10-17"
                  Statement = [ local.producer_policy_statement ]
                })
  tags        = var.tags
}
