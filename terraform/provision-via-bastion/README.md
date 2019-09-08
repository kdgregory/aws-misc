This script is an example of running a (simple) provisioning step on an EC2 instance
when you need to connect via a bastion host.

I originally wrote it in response to a Stack Overflow question, when I realized that
there weren't any good examples (at least easily Google-able ones) available.
Unfortunately, the schmuck who asked the question deleted it after I posted the
answer (perhaps because it was clear that he didn't understand what he was doing).
Fortunately, I saved teh codez.

Personally, I don't particularly like provisioning via Terraform. I think a far better
approach is to pre-bake your AMI, and let it pull whatever per-instance configuration
it needs. 


## Configuration

There are a lot of variables; either hardcode them to suit your environment or
pass on the command-line:

* `keypair_name` 
  The name of an existing EC2 keypair. Both the bastion host and the provisioned host
  will be configured to use this keypair.

* `ssh_private_key_path` 
  The path to your the SSH private key file associated with this keypair. This is needed
  for the provisioner to access the hosts; it is _not_ uploaded anywhere (unless the
  remove provisioner has a back door that I don't know about). This must be specified as
  a full path, rather than using `$HOME`, because [Terraform does not allow expressions
  to use environment variables](https://github.com/hashicorp/terraform/pull/14166).

* `vpc_id` 
   The ID of the VPC where these hosts are deployed. Used to create security group.

* `bastion_subnet` 
   The public subnet where the bastion host will be deployed.

* `private_subnet` 
   The private subnet where the provisioned host will be deployed.

* `ami_id` 
   The AMI to use for both bastion and provisioned hosts. This should be the
   region-appropriate AWS Linux AMI.

* `local_cidr` 
  Your IP address, formatted as a /32 CIDR. This is used to enable access to
  the bastion host.

An additional piece of configuration is the EC2 instance type. It is hardcoded
as `t2.micro`.


## Resources

EC2 Instances:

* Bastion host
* Provisioned host

Security Groups:

* `Bastion`: applied to the bastion host, allows connections from your local IP.
* `Provisioned`: applied to the provisioned host, allows connections only from
  the bastion host (via security group association).


## Provisioning

The provisioning step is very simple: it creates a file on the destination, using
the `remote-exec` provisioner. I run provisioning on both the bastion and the
"provisioned" instance, using slightly different commands. The only real difference
is the `connection`: the "provisioned" host has a `bastion_host` attribute.
