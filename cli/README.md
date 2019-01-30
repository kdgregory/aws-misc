This directory contains useful bash shell commands. Divided by primary service, with general commands here.

----

Get current AWS account ID. Useful for substitution into other commands.

```
aws sts get-caller-identity --output text --query Account
```
