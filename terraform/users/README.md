Creates users, groups, and roles in a multi-account organization, with the following characteristics:

* All users exist within the "master" account.
* To perform actions in the child account(s), a user must assume a role in that account.
* The ability to assume a role is granted by membership in a group in the parent account.

To that end, there are two Terraform scripts:

* [child.tf](child.tf) defines the roles/permissions for a single account. You must
  create one copy of it for each child account.
* [master.tf](master.tf) defines the users and groups in the master account.

Each of the scripts is intended to be stored in its own sub-directory (multiple sub-directories
for `child.tf`), and the corresponding `tfstate` file checked into source control.


## Configuration

The roles and policies in `child.tf` are defined explicitly, as is normal for Terraform:

* An `aws_iam_policy_document` data source that defines the policy.
* An `aws_iam_policy` resource to create a managed policy from this data source.
* An `aws_iam_role` resource to create a role.
* An `aws_iam_role_policy_attachment` to assign managed policies to a role.

By comparison, `master.tf` is completely table driven: you don't need to edit any
of the resource-creation code. Instead, you modify the following variables:

* `users` is a list of all the users in your organization:

  ```
  variable "users" {
      type = list
      default = [ "user1", "user2", "user3" ]
  }
  ```

* `groups` is a list of all the groups in your organization:

  ```
  variable "groups" {
      type = list
      default = [ "developers", "ops" ]
  }
  ```

* `group_members` defines which users belong to which groups:

  ```
  variable "group_members" {
      type = map(list(string))
      default = {
        "developers"  = [ "user1", "user2" ],
        "ops"         = [ "user3" ]
      }
  }
  ```

* `group_permissions` defines which child-account roles are assigned to which groups. To
  make these associations more readable, each child is given a name, which is associated
  with its associated with its account via the `child-account-ids` variable (qv).

  ```
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
  ```

Lastly, there is one variable in each script that contains account IDs:

* `child.tf` needs to know the account ID of the parent; this is used
  when granting `sts:assumeRole`.

  ```
  variable "master-account-id" {
      type = "string"
      default = "CHANGEME"
  }
  ```

* `master.tf` needs to know the account IDs of each of its children. These are
  used to create the role ARNs driven by `group_permissions`.

  ```
  variable "child-account-ids" {
      type = map
      default = {
          "child1" = "CHANGEME",
          "child2" = "CHANGEME"
      }
  }
  ```

Edit the scripts to replace `CHANGEME` with actual account IDs, or pass them on the command line.


## Running

As mentioned above, each script should have its own sub-directory, to allow Terraform to maintain
state (and the state files should be checked into source control along with the scripts).

These scripts need to be run as a user with administrator rights. That can either be a dedicated user
in each account (including child accounts), or a master account user that's authorized to use the
[organization access role](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_accounts_access.html).

Run the child scripts first, as they create the roles referenced by the master script (if you edited
the script to provide hardcoded values for the account ID, there's no need to pass it on the command
line):

```
terraform apply -var 'master-account-id=012345678901'
```

Then run the master script:

```
terraform apply -var 'child-account-ids={dev=123456789012,stage=234567890123}'
```

The master script may need to be run twice, because IAM resources appear to be eventually consistent.
In particular, groups may not be ready to accept users immediately after they're created:

```
Error putting IAM group policy group-policies-0: NoSuchEntity: The group with name developers cannot be found.
```
