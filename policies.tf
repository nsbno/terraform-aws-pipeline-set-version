data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

data "aws_iam_policy_document" "logs_for_lambda" {
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup"]
    resources = ["arn:aws:logs:${local.current_region}:${local.current_account_id}:*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:${local.current_region}:${local.current_account_id}:log-group:/aws/lambda/${aws_lambda_function.pipeline_set_version.function_name}*"
    ]
  }
}

# TODO: Make this policy more strict
data "aws_iam_policy_document" "ssm_for_lambda" {
  statement {
    effect = "Allow"
    actions = [
      "ssm:*",
    ]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "ecr_for_lambda" {
  # TODO: Restrict permissions to specific resources
  statement {
    effect    = "Allow"
    actions   = ["ecr:Get*"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["ecr:List*"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["ecr:Describe*"]
    resources = ["*"]
  }
}


data "aws_iam_policy_document" "s3_for_lambda" {
  # TODO: Restrict permissions to specific resources
  statement {
    effect    = "Allow"
    actions   = ["s3:ListObjects"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["*"]
  }
}
