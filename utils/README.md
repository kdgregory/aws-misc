This directory contains a collection of utility programs, mostly written in Python (3).

They're intended to be invoked from the command-line, but the core operations are exposed
as functions that can be imported by other programs.

Program             | Description
--------------------|-------------
`ef-env.py`         | Populates environment variables from the parameters and outputs of a CloudFormation stack.
`assume-role.py`    | Spawns a subshell with authentication credentials for a specified role.

Each program is documented fully in its header.

In addition to the Python standard libraries, you must have `boto3` installed and accessible
by the current user.

```
pip3 install boto3
```
