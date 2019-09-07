##
## Creates two EC2 instances, one in a public subnet, one in a private (which
## must have a NAT), and uses the first to access the second.
##
################################################################################

provider "aws" {}


variable "keypair_name" {
    description = "Name of an existing keypair that for the invoking user"
    type = string
    default = "CHANGEME"
}

variable "ssh_private_key_path" {
    description = "The user's private key file corresponding to the named keypair"
    type = string
    default = "/home/ME/.ssh/id_rsa"
}

variable "vpc_id" {
    description = "Identifies the VPC where we deploy"
    type = string
    default = "vpc-12345678"
}

variable "bastion_subnet" {
    description = "A public subnet where the bastion host will live"
    type = string
    default = "subnet-23456789"
}

variable "private_subnet" {
    description = "A private subnet where the provisioned host will live"
    type = string
    default = "subnet-34567890"
}

variable "ami_id" {
    description = "AMI to use for created instances (will be region-specific)"
    type = string
    default = "ami-0b898040803850657"
}

variable "local_cidr" {
    description = "The IP address of the person running this script, as a /32"
    type = string
    default = "1.2.3.4/32"
}


resource "aws_security_group" "bastion" {
  name        = "Bastion"
  description = "Allows connections from the local host"
  vpc_id      = "${var.vpc_id}"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [ "${var.local_cidr}" ]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks     = ["0.0.0.0/0"]
  }
}


resource "aws_security_group" "provisioned" {
  name        = "Provisioned"
  description = "Applied to host in private subnet, allows connections from the bastion host"
  vpc_id      = "${var.vpc_id}"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    security_groups = [ "${aws_security_group.bastion.id}" ]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks     = ["0.0.0.0/0"]
  }
}


resource "aws_instance" "bastion" {
  ami                         = "${var.ami_id}"
  instance_type               = "t2.micro"
  key_name                    = "${var.keypair_name}"
  subnet_id                   = "${var.bastion_subnet}"
  vpc_security_group_ids      = [ "${aws_security_group.bastion.id}" ]
  associate_public_ip_address = true
  tags = {
    Name                      = "Bastion"
  }

  provisioner "remote-exec" {
    inline = [
        "echo 'example provisioning command' > /tmp/irrelevant.txt"
    ]
    connection {
      type        = "ssh"
      host        = "${aws_instance.bastion.public_ip}"
      user        = "ec2-user"
      private_key = file("${var.ssh_private_key_path}")
    }
  }
}


resource "aws_instance" "provisioned" {
  ami                         = "${var.ami_id}"
  instance_type               = "t2.micro"
  key_name                    = "${var.keypair_name}"
  subnet_id                   = "${var.private_subnet}"
  vpc_security_group_ids      = [ "${aws_security_group.provisioned.id}" ]
  associate_public_ip_address = false
  tags = {
    Name                      = "Provisioned Host"
  }

  provisioner "remote-exec" {
    inline = [
        "echo 'example provisioning command' > /tmp/also_irrelevant.txt"
    ]
    connection {
      type          = "ssh"
      bastion_host  = "${aws_instance.bastion.public_ip}"
      host          = "${aws_instance.provisioned.private_ip}"
      user          = "ec2-user"
      private_key   = file("${var.ssh_private_key_path}")
    }
  }
}
