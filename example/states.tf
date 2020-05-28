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
        "Payload": {}
      },
      "End": true
    }
  }
}
EOF
}
