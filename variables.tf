variable "name_prefix" {
  description = "A prefix used for naming resources."
  type        = string
}

variable "ssm_prefix" {
  description = "The SSM prefix (without leading forward slash) to use for storing version parameters (e.g., `example/versions`)."
  type        = string
}

variable "tags" {
  description = "A map of tags (key-value pairs) passed to resources."
  type        = map(string)
  default     = {}
}
