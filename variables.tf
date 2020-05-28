variable "name_prefix" {
  description = "A prefix used for naming resources."
  type        = string
}

variable "ssm_prefix" {
  description = "The SSM prefix (without leading forward slash) to use for storing version parameters (e.g., `example/versions`)."
  type        = string
}

variable "ecr_image_tag_filters" {
  description = "Require that only images tagged with certain tags are included when looking for the most recent image in an ECR repository."
  type        = list(string)
  default     = []
}

variable "ecr_repositories" {
  description = "The name of the ECR repositories containing Docker applications to set versions for."
  type        = list(string)
  default     = []
}

variable "lambda_names" {
  description = "The name of the Lambda functions to set versions for."
  type        = list(string)
  default     = []
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

variable "tags" {
  description = "A map of tags (key-value pairs) passed to resources."
  type        = map(string)
  default     = {}
}
