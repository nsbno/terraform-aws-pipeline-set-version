# terraform-aws-pipeline-set-version
A Terraform module that creates a Lambda function that sets SSM parameters containing the latest _version_ for Docker and Lambda applications. The main use-case is to run the function as a task in a CD pipeline implemented using AWS Step Functions, and reference the parameters in Terraform code that is deployed at a later point in the pipeline.

It is assumed that the artifact stores, i.e., the ECR repositories and the S3 bucket containing Lambda deployment packages, exist in the same account as where the Lambda function is created.

## Versioning of Docker applications
The function assumes that each Docker application has a dedicated ECR repository where images are tagged with at least one tag `<commit-has>-SHA1`.

The function lists all ECR repositories in the current region of the current account, finds the most recently pushed image in each repository that is tagged with at least `<commit-hash>-SHA1` and sets an SSM parameter, either in the current account or by assuming a role in another account, with name `<name-of-ecr-repository>` and value `<commit-hash>`. Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent image in an ECR repository.

## Versioning of Lambda applications
The function assumes that each Lambda application exist in a given S3 bucket under a specific prefix, and is packaged as either a JAR or a ZIP file.

The function lists all Lambda deployment packages located in a given S3 bucket under a specific prefix (e.g., `<github_org>/<github_repo>/lambdas`) that follows the naming convention of `<application-name>/package.{jar,zip}`. An SSM parameter will be set per application with name `<application-name>` and value equal to the S3 version of the deployment package.

## Lambda Inputs
Most inputs are optional, but some of them will only have an effect if they are supplied together with one or more of the other inputs.

#### `account_id` (optional - requires `role_to_assume` to be set)
The id of the account that owns the role `role_to_assume`. If not supplied, the function will simply run using its execution role.

#### `ecr_image_tag_filters` (optional - requires `ecr_repositories` to be set)
Require that only images tagged with certain tags are included when looking for the most recent image in an ECR repository (if set, `ecr_repositories` must also be set).

#### `ecr_repositories` (optional)
The names of the ECR repositories containing Docker applications to set versions for.

#### `lambda_names` (optional - requires all `lambda_*` inputs to be set)
The names of the Lambda functions to set versions for.

#### `lambda_s3_bucket` (optional - requires all `lambda_*` inputs to be set)
The name of the S3 bucket containing Lambda deployment packages to set versions for.

#### `lambda_s3_prefix` (optional - requires all `lambda_*` inputs to be set)
The S3 prefix where Lambda deployment packages are stored.

#### `role_to_assume` (optional - requires `account_id` to be set)
The name of the role to assume. (Note: A policy should be attached to the the Lambda's execution role, exposed as an output in Terraform, that allows it to assume the role).

#### `ssm_prefix` (required)
The prefix to use when creating/updating SSM parameters. To avoid accidental overwrites of wrong SSM parameters, the function is only allowed to operate on SSM parameters with a prefix matching `"/${var.name_prefix}/*"`, where `var.name_prefix` is a Terraform variable. An example value of `ssm_prefix` is `trafficinfo`.
