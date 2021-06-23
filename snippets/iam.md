# Roles

## Trust relationship: MFA-enforced assumable role

Requires an MFA token to be provided when assuming a role. Does not
work with roles assumed via AWS SSO.


```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        }
      }
    }
  ]
}
```


## Trust relationship: only allow assumption from named role

When specifying a [role as a trust policy principal](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html#principal-roles),
deleting and re-creating the role will break the trust policy (because AWS replaces the
literal role name with an internal identifier). If this causes a problem (eg, because of
a deployment mechanism that recreates roles), this is an alternative based on the name
and not the internal ID.

```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "ArnEquals": {
          "aws:PrincipalArn": "arn:aws:iam::123456789012:role/Example"
        }
      }
    }
  ]
}```


# Policies
