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

  file_hash                   = (var.filename != null) ? filebase64sha256(var.filename) : null
  source_code_hash            = (var.source_code_hash != null) ? var.source_code_hash : local.file_hash

  deploy_in_vpc               = (var.vpc_id != null) ? toset(["1"]) : toset([])
  security_group_ids          = (var.vpc_id != null) ? concat([aws_security_group.marker["1"].id], var.security_group_ids) : null

  has_environment             = (length(var.env) > 0) ? toset(["1"]) : toset([])
}


data "aws_caller_identity" "current" {}
data "aws_region" "current" {}


resource "aws_lambda_function" "lambda" {
  function_name           = var.name
  description             = var.description
  role                    = aws_iam_role.execution_role.arn
  runtime                 = var.runtime
  filename                = var.filename
  source_code_hash        = local.source_code_hash
  s3_bucket               = var.s3_bucket
  s3_key                  = var.s3_key
  s3_object_version       = var.s3_version
  handler                 = var.handler
  memory_size             = var.memory_size
  timeout                 = var.timeout
  layers                  = var.layers

  dynamic "environment" {
    for_each              = local.has_environment
    content {
      variables           = var.env
    }
  }

  dynamic "vpc_config" {
    for_each              = local.deploy_in_vpc
    content {
      subnet_ids          = var.subnet_ids
      security_group_ids  = local.security_group_ids
    }
  }

  tags = var.tags
}


resource "aws_iam_role" "execution_role" {
  name = "${var.name}-${local.aws_region}-ExecutionRole"
  path = "/lambda/"

  assume_role_policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Principal": { "Service": "lambda.amazonaws.com" }
    }]
  })

  tags = var.tags
}


resource "aws_iam_role_policy" "logging_policy" {
  name    = "Logging"
  role    = aws_iam_role.execution_role.id

  policy  = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.log_group.arn,
          "${aws_cloudwatch_log_group.log_group.arn}:*"
        ]
      }
    ]
  })
}


resource "aws_iam_role_policy" "vpc_policy" {
  for_each  = local.deploy_in_vpc

  name      = "VPC_Attachment"
  role      = aws_iam_role.execution_role.id

  policy    = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ]
        Resource = "*"
      }
    ]
  })
}


resource "aws_security_group" "marker" {
  for_each            = local.deploy_in_vpc

  name                = var.name
  description         = "Marker security group assigned to Lambda"
  vpc_id              = var.vpc_id

  egress {
    from_port         = 0
    to_port           = 0
    protocol          = "-1"
    cidr_blocks       = ["0.0.0.0/0"]
    ipv6_cidr_blocks  = ["::/0"]
  }

  tags = merge({"Name" = var.name}, ((var.tags != null) ? var.tags : {}))
}


resource "aws_cloudwatch_log_group" "log_group" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention

  tags = var.tags
}
