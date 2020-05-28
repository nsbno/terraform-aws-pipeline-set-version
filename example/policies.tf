data "aws_iam_policy_document" "state_machine_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      identifiers = ["states.amazonaws.com"]
      type        = "Service"
    }
  }
}

data "aws_iam_policy_document" "lambda_for_state_machine" {
  statement {
    effect = "Allow"
  }
  statement {
    effect  = "Allow"
    actions = ["lambda:*"]
    resources = [
      "arn:aws:lambda:${local.current_region}:${local.current_account_id}:function:${module.set_version_lambda.function_name}"
    ]
  }
}
