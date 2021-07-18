variable "name" {
  description = "The name of the queue; also used as the base name for its policies and dead-letter queue"
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "The number of seconds that a consumer has to process a message before another consumer can read it"
  type        = number
  default     = 30
}

variable "message_retention_days" {
  description = "The number of days that a message will remain in the primary queue without being processed"
  type        = number
  default     = 4
}

variable "dlq_retention_days" {
  description = "The number of days that a message will remain in the dead letter queue without being processed"
  type        = number
  default     = null
}

variable "retry_count" {
  description = "The number of times to retry delivery of a message before moving it to the dead-letter queue"
  type        = number
  default     = null
}

variable "tags" {
  description = "Tags that are applied to all resources"
  type        = map(string)
  default     = null
}
