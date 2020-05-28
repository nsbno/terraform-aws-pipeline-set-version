variable "name_prefix" {
  description = "A prefix used for naming resources."
  type        = string
}

variable "tags" {
  description = "A map of tags (key-value pairs) passed to resources."
  type        = map(string)
  default     = {}
}

variable "lambda_s3_bucket" {
  description = "The name of the S3 bucket containing Lambda deployment packages to set versions for."
  type        = string
  default     = ""
}

variable "lambda_s3_prefix" {
  description = "The S3 prefix where Lambda deployment packages are stored."
  type        = string
  default     = ""
}

variable "ecr_repositories" {
  description = "The name of the ECR repositories containing Docker applications to set versions for."
  type        = list(string)
  default     = []
}
