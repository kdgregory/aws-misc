Creates users and groups for a multi-account organization, with the following characteristics:

* All users exist within a "master" account.
* All users have a "basic login policy," which allows them to change their password and
  enable a device for two-factor-auth.
* To perform actions in the child account(s), a user must assume a role in that account.
* The ability to assume a role is granted by membership in a group in the parent account.

Creating the roles in the child accounts are outside the scope of this example.


## Configuration

This script is completely table driven: you don't need to edit any of the resource-creation
code. Instead, you modify the following variables:

* `account-ids` is a lookup table that associates organizational account IDs with 
  names, to make the `group_permissions` table (qv) easier to read.

  ```
  variable "account-ids" {
      type = map
      default = {
          "dev"  = "123456789012",
          "qa"   = "234567890123"
          "prod" = "345678901234"
      }
  }
  ```

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

* `group_members` defines which groups are associated with which users:

  ```
  variable "group_members" {
      type = map(list(string))
      default = {
        "user1"  = [ "developers", "ops" ],
        "user2"  = [ "developers" ],
        "user3"  = [ "ops" ]
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


## Running

To run the script you'll need to update these variables with the users, groups, and account
IDs for your organization. Then run `terraform apply` as an administrator in the master
account.

You may need to run the script twice: AWS will consider users and groups "created"  but not
ready for modification. If this happens you'll see a "no such entity" error.
