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


variable "child-account-ids" {
    type = map
    default = {
        "dev"   = "CHANGEME",
        "stage" = "CHANGEME"
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
      "developers"  = [ "user1", "user2" ],
      "ops"         = [ "user3" ]
    }
}


variable "group_permissions" {
    type = map(list(list(string)))
    default = {
      "developers"  = [
                        [ "dev",    "Management" ],
                        [ "dev",    "Destructive" ],
                        [ "stage",  "Management" ]
                      ],
      "ops"         = [
                        [ "dev",    "Administrator" ],
                        [ "stage",  "Administrator" ]
                      ]
    }
}


################################################################################
# all users have some basic configuration, but need to be enabled manually
# force_destroy lets us remove users that have customized their logins
################################################################################

resource "aws_iam_user" "users" {
  count = length(var.users)
  name = "${var.users[count.index]}"
  force_destroy = true
}


data "aws_iam_policy_document" "base-user-policy" {
  statement {
    sid = "1"
    actions = [
        "iam:ChangePassword",
        "iam:CreateAccessKey",
        "iam:CreateVirtualMFADevice",
        "iam:EnableMFADevice",
        "sts:GetCallerIdentity"
    ]
    resources = [
      "arn:aws:iam::*:user/$${aws:username}"
    ]
  }
}


resource "aws_iam_user_policy" "base-user-policy" {
  count = length(var.users)
  name  = "BaseUserPolicy"
  user = "${var.users[count.index]}"
  policy = "${data.aws_iam_policy_document.base-user-policy.json}" 
}


################################################################################
## groups grant the ability to assume roles in child accounts
################################################################################

resource "aws_iam_group" "groups" {
  count = length(var.groups)
  name = "${var.groups[count.index]}"
}


resource "aws_iam_group_membership" "group-membership" {
  count = length(var.groups)
  name = "group-membership-${count.index}"
  group = "${var.groups[count.index]}"
  users = "${var.group_members[var.groups[count.index]]}"
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
        "arn:aws:iam::${var.child-account-ids[assoc[0]]}:role/${assoc[1]}"
    ]
  }
}


resource "aws_iam_group_policy" "group-policies" {
  count = length(var.groups)
  name = "group-policies-${count.index}"
  group = "${var.groups[count.index]}"
  policy = "${data.aws_iam_policy_document.group-policies[count.index].json}" 
}
