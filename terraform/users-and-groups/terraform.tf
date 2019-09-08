##
## This script creates the users and groups, assigns users to groups, and
## grants permissions to the groups.
##
## This should be run using a pre-created admin user in the master account.
##
## NOTE: you may need to run this script twice, once to create the users,
##       and once to apply the base user policy. This appears to be a case
##       where AWS hasn't really finished creating the user when the API
##       returns, and Terraform executes the subsequent policy operation
##       too quickly (albeit with correct implicit dependencies).
##
################################################################################

provider "aws" {}

data "aws_caller_identity" "current" {}


variable "account-ids" {
    type = map
    default = {
      "dev"  = "123456789012",
      "qa"   = "234567890123"
      "prod" = "345678901234"
    }
}


variable "users" {
    type = list
    default = [ "user1", "user2", "user3" ]
}


variable "groups" {
    type = list
    default = [ "developers", "ops" ]
}


variable "group_members" {
    type = map(list(string))
    default = {
      "user1"  = [ "developers", "ops" ],
      "user2"  = [ "developers" ],
      "user3"  = [ "ops" ]
    }
}

variable "group_permissions" {
    type = map(list(list(string)))
    default = {
      "developers"  = [
                        [ "dev",    "Management" ],
                        [ "dev",    "Destructive" ],
                        [ "prod",   "Management" ]
                      ],
      "ops"         = [
                        [ "dev",    "Administrator" ],
                        [ "qa",     "Administrator" ],
                        [ "prod",   "Administrator" ]
                      ]
    }
}

################################################################################
# this policy lets users do basic account maintenance tasks
################################################################################

data "aws_iam_policy_document" "base-user-policy" {
  statement {
    actions = [
      "iam:UploadSSHPublicKey",
      "iam:UpdateSSHPublicKey",
      "iam:UpdateAccessKey",
      "iam:List*",
      "iam:Get*",
      "iam:EnableMFADevice",
      "iam:DeleteSSHPublicKey",
      "iam:DeleteAccessKey",
      "iam:CreateAccessKey",
      "iam:ChangePassword"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/$${aws:username}"
    ]
  }
  statement {
    actions = [
      "iam:DeleteVirtualMFADevice"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:mfa/$${aws:username}"
    ]
  }
  statement {
    actions = [
      "iam:ListVirtualMFADevices",
      "iam:CreateVirtualMFADevice"
    ]
    resources = [
      "*"
    ]
  }
}

resource "aws_iam_policy" "base_user_policy" {
  name        = "BaseUserPolicy"
  description = "Grants users the ability to modify their accounts"
  policy      = "${data.aws_iam_policy_document.base-user-policy.json}" 
}

################################################################################
# all users have some basic configuration, but need to be enabled manually;
# force_destroy lets us remove users that have customized their logins
################################################################################

resource "aws_iam_user" "users" {
  count = length(var.users)
  name = "${var.users[count.index]}"
  force_destroy = true
}

resource "aws_iam_user_policy_attachment" "base_user_policy" {
  count      = length(var.users)
  user       = "${var.users[count.index]}"
  policy_arn = "${aws_iam_policy.base_user_policy.arn}"
}


################################################################################
## groups grant the ability to assume roles in child accounts
################################################################################

resource "aws_iam_group" "groups" {
  count = length(var.groups)
  name = "${var.groups[count.index]}"
}


resource "aws_iam_user_group_membership" "group-membership" {
  count = length(var.users)
  user  = "${var.users[count.index]}"
  groups = "${var.group_members[var.users[count.index]]}"
}


data "aws_iam_policy_document" "group-policies" {
  count = length(var.groups)
  statement {
    sid = "1"
    actions = [
        "sts:AssumeRole"
    ]
    resources = [
      for assoc in var.group_permissions[var.groups[count.index]]:
        "arn:aws:iam::${var.account-ids[assoc[0]]}:role/${assoc[1]}"
    ]
  }
}


resource "aws_iam_group_policy" "group-policies" {
  count = length(var.groups)
  name = "group-policies-${count.index}"
  group = "${var.groups[count.index]}"
  policy = "${data.aws_iam_policy_document.group-policies[count.index].json}" 
}
