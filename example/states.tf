locals {
  state_definition = <<-EOF
{
  "Comment": "Example State Machine",
  "StartAt": "Bump Versions",
  "States": {
    "Bump Versions": {
      "Comment": "Update SSM parameters in a given account to contain latest versions of Docker and Lambda applications",
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${module.set_version_lambda.function_name}",
        "Payload": {
          "get_versions": true,
          "set_versions": true,
          "ssm_prefix": "${local.name_prefix}"
          "ecr_image_tag_filters": ["master-branch"],
          "ecr_repositories": ["${local.name_prefix}-docker-app"],
          "frontend_names": ["${local.name_prefix}-frontend-app"],
          "frontend_tag_filters": ["master-branch"],
          "frontend_s3_bucket": "example-bucket",
          "frontend_s3_prefix": "frontends",
          "lambda_names": ["${local.name_prefix}-lambda-app"],
          "lambda_tag_filters": ["master-branch"],
          "lambda_s3_bucket": "example-bucket",
          "lambda_s3_prefix": "lambdas",
        }
      },
      "End": true
    }
  }
}
EOF
}
