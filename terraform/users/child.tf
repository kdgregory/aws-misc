##
## This script creates sample roles for an application that uses EC2 and RDS.
##
##   Administrator - Uses the predefined Administrator role
##   Destructive   - Allows destroying instances/database servers
##   Management    - Allows creating or modifying the same
##   ReadOnly      - Allows listing objects (including some that are not
##                   directly associated with EC2/RDS).
##
## These roles are composed of like-named policies with the same names; the
## difference is that policies are stacked to form roles (ie, the Destructive
## role consists of Destructive, Managment, and ReadOnly policies).
##
## This script should be run using an existing admin user in the child account.
## The master account ID can either be hardcoded or passed at invocation.
##
################################################################################
##
## Note: these roles/policies are meant to be illustrative. Actual policies will
##       be dependent on the particular deployment environment and application.
##
################################################################################

provider "aws" {}


variable "master-account-id" {
    type = "string"
    default = "CHANGEME"
}


################################################################################
# all roles are built up from managed policies, specified as a policy document
################################################################################

data "aws_iam_policy_document" "read-only" {
  statement {
    sid = "1"
    effect = "Allow"
    actions = [
        "acm:Describe*",
        "acm:List*",
        "autoscaling:Describe*",
        "cloudformation:Describe*",
        "cloudformation:Detect*",
        "cloudformation:Get*",
        "cloudformation:List*",
        "cloudwatch:Describe*",
        "cloudwatch:Get*",
        "cloudwatch:List*",
        "ec2:Describe*",
        "ec2:Get*",
        "elasticloadbalancing:Describe*",
        "iam:Get*",
        "iam:List*",
        "logs:Describe*",
        "logs:Filter*",
        "logs:Get*",
        "logs:List*",
        "logs:StartQuery",
        "logs:StopQuery",
        "rds:Describe*",
        "s3:Get*",
        "s3:List*"
    ]
    resources = [ "*" ]
  }
}

resource "aws_iam_policy" "read-only" {
  name        = "ReadOnly"
  description = "Allows users to examine the environment"
  policy = "${data.aws_iam_policy_document.read-only.json}" 
}

###

data "aws_iam_policy_document" "management" {
  statement {
    sid = "1"
    effect = "Allow"
    actions = [
        "autoscaling:Attach*",
        "autoscaling:CompleteLifecycleAction",
        "autoscaling:Create*",
        "autoscaling:Detach*",
        "autoscaling:Put*",
        "autoscaling:Resume*",
        "autoscaling:Suspend*",
        "autoscaling:Update*",
        "cloudformation:Cancel*",
        "cloudformation:Create*",
        "cloudformation:Update*",
        "cloudwatch:Put*",
        "ec2:AttachVolume",
        "ec2:Copy*",
        "ec2:CreateImage*",
        "ec2:CreateLaunch*",
        "ec2:CreateSnapshot*",
        "ec2:CreateTags",
        "ec2:CreateVolume",
        "ec2:DeleteTags",
        "ec2:DeleteVolume",
        "ec2:ImportKeyPair",
        "ec2:ModifyLaunchTemplate",
        "ec2:ModifyVolume",
        "ec2:RebootInstances",
        "ec2:RegisterImage",
        "ec2:Run*",
        "ec2:StartInstances",
        "elasticloadbalancing:Create*",
        "elasticloadbalancing:Modify*",
        "elasticloadbalancing:Register*",
        "elasticloadbalancing:Set*",
        "logs:Create*",
        "logs:Put*",
        "rds:Add*",
        "rds:Copy*",
        "rds:Create*",
        "rds:Modify*",
        "rds:Promote*",
        "rds:Restore*",
        "rds:Start*",
        "s3:Create*",
        "s3:Put*",
        "s3:Replicate*",
        "s3:Restore*"
    ]
    resources = [ "*" ]
  }
}

resource "aws_iam_policy" "management" {
  name        = "ResourceManagement"
  description = "Allows resource creation and modification"
  policy = "${data.aws_iam_policy_document.management.json}" 
}

###

data "aws_iam_policy_document" "destruction" {
  statement {
    sid = "1"
    effect = "Allow"
    actions = [
        "autoscaling:Delete*",
        "cloudformation:Delete*",
        "cloudwatch:Delete*",
        "ec2:DeleteLaunch*",
        "ec2:DeleteSnapshot",
        "ec2:DeregisterImage ",
        "ec2:DetachVolume",
        "ec2:StopInstances",
        "ec2:TerminateInstances",
        "elasticloadbalancing:Delete*",
        "logs:Delete*",
        "rds:Delete*",
        "rds:Reboot*",
        "rds:Remove*",
        "rds:Stop*",
        "s3:Delete*"
    ]
    resources = [ "*" ]
  }
}

resource "aws_iam_policy" "destruction" {
  name        = "ResourceDestruction"
  description = "Allows developers to destroy resources"
  policy = "${data.aws_iam_policy_document.destruction.json}" 
}


################################################################################
## This policy document is used by all roles
################################################################################

data "aws_iam_policy_document" "assume-role-policy" {
  statement {
    sid = "1"
    actions = [ "sts:AssumeRole" ]
    principals {
      type = "AWS"
      identifiers = [ "${var.master-account-id}" ]
    }
  }
}


################################################################################
## role definitions
################################################################################

resource "aws_iam_role" "read-only" {
  name = "ReadOnly"
  description = "Allows read-only access to system state"
  assume_role_policy = "${data.aws_iam_policy_document.assume-role-policy.json}" 
}

resource "aws_iam_role_policy_attachment" "developer-describe-environment" {
  role = "${aws_iam_role.read-only.id}"
  policy_arn = "${aws_iam_policy.read-only.arn}"
}

###

resource "aws_iam_role" "management" {
  name = "ResourceManagement"
  description = "Allows creation and modification of resources"
  assume_role_policy = "${data.aws_iam_policy_document.assume-role-policy.json}" 
}

resource "aws_iam_role_policy_attachment" "management-read-only" {
  role = "${aws_iam_role.management.id}"
  policy_arn = "${aws_iam_policy.read-only.arn}"
}

resource "aws_iam_role_policy_attachment" "management-manage" {
  role = "${aws_iam_role.management.id}"
  policy_arn = "${aws_iam_policy.management.arn}"
}

###

resource "aws_iam_role" "destruction" {
  name = "ResourceDestruction"
  description = "Allows stopping/terminating instances and destruction of related resources"
  assume_role_policy = "${data.aws_iam_policy_document.assume-role-policy.json}" 
}

resource "aws_iam_role_policy_attachment" "destruction-read-only" {
  role = "${aws_iam_role.destruction.id}"
  policy_arn = "${aws_iam_policy.read-only.arn}"
}

resource "aws_iam_role_policy_attachment" "destruction-manage" {
  role = "${aws_iam_role.destruction.id}"
  policy_arn = "${aws_iam_policy.management.arn}"
}

resource "aws_iam_role_policy_attachment" "destruction-destroy" {
  role = "${aws_iam_role.destruction.id}"
  policy_arn = "${aws_iam_policy.destruction.arn}"
}


################################################################################
## AWS provides a "do anything" policy, so we'll use it for the admin role
################################################################################

resource "aws_iam_role" "administrator-access" {
  name = "Administrator"
  description = "Allows complete access to the child account"
  assume_role_policy = "${data.aws_iam_policy_document.assume-role-policy.json}" 
}

resource "aws_iam_role_policy_attachment" "administrator-access" {
  role = "${aws_iam_role.administrator-access.id}"
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
