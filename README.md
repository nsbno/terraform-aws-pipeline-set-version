# terraform-aws-pipeline-set-version
A Terraform module that creates a Lambda function that can either fetch and return the latest application versions, update SSM parameters with the latest application versions, or both. The Lambda supports fetching versions of applications hosted in ECR or S3 (e.g., Docker, Lambda and static frontend applications).

The main use-case is to run the function as a task in a CD pipeline implemented using AWS Step Functions, and reference the parameters in Terraform code that is deployed at a later point in the pipeline.

It is assumed that the artifact stores, i.e., the ECR repositories and the S3 bucket containing Lambda deployment packages and frontend bundles, exist in the same account as where the function is created.

## Versioning of Docker applications
The function assumes that each Docker application has a dedicated ECR repository where images are tagged with at least one tag `<commit-hash>-SHA1`.

The function lists all ECR repositories in the current region of the current account, finds the most recently pushed image in each repository that is tagged with at least `<commit-hash>-SHA1` and sets an SSM parameter, either in the current account or by assuming a role in another account, with name `<name-of-ecr-repository>` and value `<commit-hash>`. Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent image in an ECR repository.

## Versioning of frontend applications
The function assumes that each frontend application exist in a given S3 bucket under a specific prefix, is packaged as a ZIP file and has user-defined metadata `tags` containing at least the value `["<commit-hash>-SHA1"]`.

The function lists all frontend bundles located in a given S3 bucket under a specific prefix (e.g., `<github_org>/<github_repo>/frontends`) that follows the naming convention of `<application-name>/<commit-hash>.zip`, where `<commit-hash>` is the first seven characters of a commit hash.

## Versioning of Lambda applications
The function assumes that each Lambda application exist in a given S3 bucket under a specific prefix, is packaged as either a JAR or a ZIP file and has user-defined metadata `tags` containing at least the value `["<commit-hash>-SHA1"]`.

The function lists all Lambda deployment packages located in a given S3 bucket under a specific prefix (e.g., `<github_org>/<github_repo>/lambdas`) that follows the naming convention of `<application-name>/<commit-hash>.{jar,zip}`, where `<commit-hash>` is the first seven characters of a commit hash.

An SSM parameter will be set per application with name `<application-name>` and value equal to the commit hash of the deployment package.

## Lambda Inputs
Most inputs are optional, but some of them will only have an effect if they are supplied together with one or more of the other inputs.

#### `account_id` (optional - requires `role_to_assume` to be set)
The id of the account that owns the role `role_to_assume`. If not supplied, the function will simply run using its execution role.

#### `ecr_image_tag_filters` (optional - requires `ecr_repositories` to be set)
Require that only images tagged with certain tags are included when looking for the most recent image in an ECR repository.

#### `ecr_repositories` (optional)
The names of the ECR repositories containing Docker applications to set versions for.

#### `frontend_names` (optional - requires all `frontend_*` inputs to be set)
The names of the frontend applications to set versions for.

#### `frontend_s3_bucket` (optional - requires all `frontend_*` inputs to be set)
The name of the S3 bucket containing frontend bundles to set versions for.

#### `frontend_s3_prefix` (optional - requires all `frontend_*` inputs to be set)
The S3 prefix where frontend bundles are stored.

#### `frontend_tag_filters` (optional - requires all `frontend_*` inputs to be set)
Require that only artifacts that contains specific tags in the user-defined metadata `tags` are included when looking for the most recent artifact.

#### `lambda_names` (optional - requires all `lambda_*` inputs to be set)
The names of the Lambda functions to set versions for.

#### `lambda_s3_bucket` (optional - requires all `lambda_*` inputs to be set)
The name of the S3 bucket containing Lambda deployment packages to set versions for.

#### `lambda_s3_prefix` (optional - requires all `lambda_*` inputs to be set)
The S3 prefix where Lambda deployment packages are stored.

#### `lambda_tag_filters` (optional - requires all `lambda_*` inputs to be set)
Require that only artifacts that contains specific tags in the user-defined metadata `tags` are included when looking for the most recent artifact.

#### `role_to_assume` (optional - requires `account_id` to be set)
The name of the role to assume. (Note: A policy should be attached to the the Lambda's execution role, exposed as an output in Terraform, that allows it to assume the role).

#### `ssm_prefix` (optional - required if `set_versions` is `True`)
The prefix to use when creating/updating SSM parameters. To avoid accidental overwrites of wrong SSM parameters, the function is only allowed to operate on SSM parameters with a prefix matching `"/${var.name_prefix}/*"`, where `var.name_prefix` is a Terraform variable. An example value of `ssm_prefix` is `trafficinfo`.

#### `set_versions` (optional)
If this is set to `false`, the Lambda will only fetch and return the latest versions of all applications -- no SSM parameters will be updated. If set to `true`, however, SSM parameters will be updated using either versions supplied as input using the `versions` parameter or by fetching during runtime.

#### `versions` (optional)
An object containing application versions to set, e.g., `{ "versions": { "ecr": { "<app-name>": "abcd123" } } }`. If `versions` is set, the Lambda will not fetch versions for the application type (e.g., `ecr`) supplied and instead use the versions that have been passed in.
