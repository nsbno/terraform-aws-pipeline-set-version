# terraform-aws-pipeline-set-version
A Terraform module that creates a Lambda function that can a) fetch the latest application versions based on a set of artifact repositories or b) update SSM parameters with fetched or user-supplied application versions. The Lambda supports fetching versions of artifacts hosted in ECR or S3 (e.g., Docker, Lambda and static frontend applications).

The main use-case is to run the function as a task in a CD pipeline implemented using AWS Step Functions, and reference the parameters in Terraform code that is deployed at a later point in the pipeline.

When the Lambda is configured to set versions, an optional role will be assumed (e.g., in a `test`, `stage` or `prod` account), and an SSM parameter will be set per application with name `<application-name>` and value equal to the commit hash of the application artifact. The application name is derived from the names of the ECR repositories for Docker applications and S3 prefixes for Lambda and frontend applications.

## Versioning of Docker applications
The function assumes that each Docker application has a dedicated ECR repository where images are tagged with at least one tag `<commit-hash>-SHA1`.

When the function is configured to fetch latest versions, it will list all ECR repositories in the current region of the current account and locate the most recently pushed image in each repository that is tagged with at least `<commit-hash>-SHA1`.

Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent image in an ECR repository.

## Versioning of frontend applications
The function assumes that each frontend application exist in a given S3 bucket under a specific prefix, is packaged as a ZIP file and has user-defined S3 metadata `tags` containing at least the value `["<commit-hash>-SHA1"]`. The metadata values can be added by using the `--metadata` flag of the `aws-cli` when uploading the artifact, e.g., `aws s3 cp <commit-hash>.zip s3://<bucket-name>/frontends --metadata "tags"="'[\"<commit-hash>-SHA1\",\"<branch-name>-branch\"]'"`.

When the function is configured to fetch latest versions, it will list all frontend bundles located in a given S3 bucket (e.g., `artifacts`) under a specific prefix (e.g., `frontends`) that follow the naming convention of `<application-name>/<commit-hash>.zip`.

Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent artifact in S3.

## Versioning of Lambda applications
The function assumes that each Lambda application exist in a given S3 bucket under a specific prefix, is packaged as either a JAR or a ZIP file and has user-defined S3 metadata `tags` containing at least the value `["<commit-hash>-SHA1"]`. The metadata values can be added by using the `--metadata` flag of the `aws-cli` when uploading the artifact, e.g., `aws s3 cp <commit-hash>.zip s3://<bucket-name>/lambdas --metadata "tags"="'[\"<commit-hash>-SHA1\",\"<branch-name>-branch\"]'"`.

When the function is configured to fetch latest versions, it will list all Lambda deployment packages located in a given S3 bucket (e.g., `artifacts`) under a specific prefix (e.g., `lambdas`) that follow the naming convention of `<application-name>/<commit-hash>.{jar,zip}`.

Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent artifact in S3.

## Lambda Inputs
Most inputs are optional, but some of them will only have an effect if they are supplied together with one or more of the other inputs.

#### `account_id` (optional - requires `role_to_assume` to be set)
The id of the account that owns the role `role_to_assume`. If not supplied, the function will simply run using its execution role.

#### `ecr_applications` (optional)
An object that describes the ECR repositories containing Docker applications to set versions for, and optionally which image tags to filter on when looking for the most recent Docker image. Example:
```json
"ecr_applications": {
  "my-repo": {},
  "my-second-repo": {
    "tag_filters": ["master-branch"]
  }
}
```

#### `frontend_applications` (optional - requires all `frontend_*` inputs to be set)
An object that describes which frontend applications to set versions for, and optionally which S3 metadata tags to filter on when looking for the most recent S3 artifact. Example:
```json
"frontend_applications": {
  "my-app": {},
  "my-second-app": {
    "tag_filters": ["master-branch"]
  }
}
```

#### `frontend_s3_bucket` (optional - requires all `frontend_*` inputs to be set)
The name of the S3 bucket containing frontend bundles to set versions for.

#### `frontend_s3_prefix` (optional - requires all `frontend_*` inputs to be set)
The S3 prefix where frontend bundles are stored.

#### `lambda_applications` (optional - requires all `lambda_*` inputs to be set)
The names of the Lambda functions to set versions for.
An object that describes which Lambda applications to set versions for, and optionally which S3 metadata tags to filter on when looking for the most recent S3 artifact. Example:
```json
"lambda_applications": {
  "my-app": {},
  "my-second-app": {
    "tag_filters": ["master-branch"]
  }
}
```

#### `lambda_s3_bucket` (optional - requires all `lambda_*` inputs to be set)
The name of the S3 bucket containing Lambda deployment packages to set versions for.

#### `lambda_s3_prefix` (optional - requires all `lambda_*` inputs to be set)
The S3 prefix where Lambda deployment packages are stored.

#### `role_to_assume` (optional - requires `account_id` to be set)
The name of the role to assume. (Note: A policy should be attached to the the Lambda's execution role, exposed as an output in Terraform, that allows it to assume the role).

#### `ssm_prefix` (optional - required if `set_versions` is `True`)
The prefix to use when creating/updating SSM parameters. To avoid accidental overwrites of wrong SSM parameters, the function is only allowed to operate on SSM parameters with a prefix matching `"/${var.name_prefix}/*"`, where `var.name_prefix` is a Terraform variable. An example value of `ssm_prefix` is `trafficinfo`.

#### `get_versions` (optional)
If this is set to `true`, the Lambda will search through the artifact stores and find the latest versions of all applications defined in the input. If set to `false`, however, the Lambda will instead use application versions that are passed in by the user.

#### `set_versions` (optional)
If this is set to `true`, the Lambda will write to SSM parameters using either versions supplied as input using the `versions` parameter or by fetching during runtime.

#### `versions` (optional)
An object containing application versions to set, e.g., `{ "versions": { "ecr": { "<app-name>": "abcd123" } } }`.
