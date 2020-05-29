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
          "ecr_image_tag_filters": ["master-branch"],
          "ecr_repositories": ["${local.name_prefix}-docker-app"],
          "lambda_names": ["${local.name_prefix}-lambda-app"],
          "lambda_s3_bucket": "example-bucket",
          "lambda_s3_prefix": "lambdas",
          "ssm_prefix": "${local.name_prefix}"
        }
      },
      "End": true
    }
  }
}
EOF
}
