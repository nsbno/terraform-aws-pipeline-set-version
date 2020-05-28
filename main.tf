# ------------------------------------------------------------------------------
# Resources
# ------------------------------------------------------------------------------
data "aws_caller_identity" "current-account" {}
data "aws_region" "current" {}

locals {
  current_account_id = data.aws_caller_identity.current-account.account_id
  current_region     = data.aws_region.current.name
  ecr_arns           = formatlist("arn:aws:ecr:${local.current_region}:${local.current_account_id}:repository/%s", var.ecr_repositories)
  s3_arn             = "arn:aws:s3:::${var.lambda_s3_bucket}"
}

data "archive_file" "lambda_src" {
  type        = "zip"
  source_file = "${path.module}/src/main.py"
  output_path = "${path.module}/src/bundle.zip"
}

resource "aws_lambda_function" "pipeline_set_version" {
  function_name = "${var.name_prefix}-pipeline-set-version"
  handler       = "main.lambda_handler"
  role          = aws_iam_role.lambda_exec.arn
  runtime       = "python3.7"
  filename      = data.archive_file.lambda_src.output_path
  environment {
    variables = {
      ECR_IMAGE_TAG_FILTERS = jsonencode(var.ecr_image_tag_filters)
      ECR_REPOSITORIES      = jsonencode(var.ecr_repositories)
      LAMBDA_NAMES          = jsonencode(var.lambda_names)
      LAMBDA_S3_BUCKET      = var.lambda_s3_bucket
      LAMBDA_S3_PREFIX      = var.lambda_s3_prefix
      SSM_PREFIX            = var.ssm_prefix
    }
  }
  source_code_hash = filebase64sha256(data.archive_file.lambda_src.output_path)
  timeout          = 20
  tags             = var.tags
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.name_prefix}-pipeline-set-version"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "logs_to_lambda" {
  policy = data.aws_iam_policy_document.logs_for_lambda.json
  role   = aws_iam_role.lambda_exec.id
}

resource "aws_iam_role_policy" "ssm_to_lambda" {
  policy = data.aws_iam_policy_document.ssm_for_lambda.json
  role   = aws_iam_role.lambda_exec.id
}

resource "aws_iam_role_policy" "s3_to_lambda" {
  policy = data.aws_iam_policy_document.s3_for_lambda.json
  role   = aws_iam_role.lambda_exec.id
}

resource "aws_iam_role_policy" "ecr_to_lambda" {
  policy = data.aws_iam_policy_document.ecr_for_lambda.json
  role   = aws_iam_role.lambda_exec.id
}
