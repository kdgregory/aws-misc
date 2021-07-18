variable "name" {
  description = "The name of the Lambda; also used as the base name for its execution role"
  type        = string
}

variable "description" {
  description = "Describes the Lambda's purpose"
  type        = string
  default     = "FIXME - use a real description"
}

variable "runtime" {
  description = "The Lambda's runtime; see docs for allowed values"
  type        = string
}

variable "filename" {
  description = "The name of a local deployment bundle; mutually exlusive with s3_bucket/s3_key"
  type        = string
  default     = null
}

variable "s3_bucket" {
  description = "The name of the bucket holding the Lambda deployment bundle; mutually exlusive with filename"
  type        = string
  default     = null
}

variable "s3_key" {
  description = "The key of the Lambda deployment bundle in the bucket identified by s3_bucket; mutually exlusive with filename"
  type        = string
  default     = null
}

variable "source_code_hash" {
  description = "A Base64-encoded 256-bit hash value used to determine whether the Lambda code should be updated"
  type        = string
  default     = null
}

variable "handler" {
  description = "The fully qualified name of the Lambda's handler function"
  type        = string
}

variable "memory_size" {
  description = "The amount of memory to assign to the Lambda"
  type        = number
  default     = 1024
}

variable "timeout" {
  description = "The number of seconds that the Lambda is allowed to execute"
  type        = number
  default     = 60
}

variable "vpc_id" {
  description = "If specified, the Lambda is deployed in this VPC; must also provide subnet_ids"
  type        = string
  default     = null
}

variable "subnet_ids" {
  description = "The subnets where the Lambda should be deployed (must be within VPC identified by vpc_id)"
  type        = list(string)
  default     = null
}

variable "security_group_ids" {
  description = "If specified, identifies a list of security groups that are attached to the Lambda in addition to the one created by this module"
  type        = list(string)
  default     = []
}

variable "layers" {
  description = "The ARNs of layers to required by Lamba"
  type        = list(string)
  default     = null
}

variable "env" {
  description = "Environment variable definitions"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags that are applied to all resources"
  type        = map(string)
  default     = {}
}

variable "log_retention" {
  description = "The number of days to retain execution logs; see docs for allowed values"
  type        = number
  default     = 30
}
