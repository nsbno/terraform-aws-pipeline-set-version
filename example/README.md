# Example
This folder contains an example that provisions an AWS Step Function that contains a single state `Bump Versions` that runs the Lambda function that sets SSM parameters.

The module is set up to look for:
- the most recent Docker image tagged with `<commit-hash>-SHA1` and `master-branch` in an ECR repository named `example-docker-app`.
- the most recent Lambda deployment package with metadata `["<commit-hash>-SHA1", "master-branch"]` in an S3 bucket `example-bucket` under the prefix `lambdas/<example-lambda-app>/`.
- the most recent frontend bundle with metadata `["<commit-hash>-SHA1", "master-branch"]` in an S3 bucket `example-bucket` under the prefix `frontends/<example-frontend-app>/`.

These values must be updated in `states.tf` to your specific values if you want to apply the example code.
