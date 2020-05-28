# terraform-aws-pipeline-set-version
A Terraform module that creates a Lambda function that sets SSM parameters containing the latest _version_ for Docker and Lambda applications. The main use-case is to run the function as a task in a CD pipeline implemented using AWS Step Functions, and reference the parameters in Terraform code that is deployed at a later point in the pipeline.

## Versioning of Docker applications
The function assumes that each Docker application has a dedicated ECR repository where images are tagged with at least one tag `<commit-has>-SHA1`.

The function lists all ECR repositories in the current region of the current account, finds the most recently pushed image in each repository that is tagged with at least `<commit-hash>-SHA1` and sets an SSM parameter, either in the current account or by assuming a role in another account, with name `<name-of-ecr-repository>` and value `<commit-hash>`. Additional tags can also be enforced, such that only images tagged with `<commit-hash>-SHA1` **and** `master-branch` are included when locating the most recent image in an ECR repository.

## Versioning of Lambda applications
The function assumes that each Lambda application exist in a given S3 bucket under a specific prefix, and is packaged as either a JAR or a ZIP file.

The function lists all Lambda deployment packages located in a given S3 bucket under a specific prefix (e.g., `<github_org>/<github_repo>/lambdas`) that follows the naming convention of `<application-name>/package.{jar,zip}`. An SSM parameter will be set per application with name `<application-name>` and value equal to the S3 version of the deployment package.

## Lambda Inputs
Most values are provided through Terraform variables that are added to the Lambda function as environment variables. To allow the Lambda to be used reused for updating parameters in multiple accounts, the Lambda function has two dynamic inputs. If these values are provided, a policy should be attached to the the Lambda's execution role (exposed as an output) that allows it to assume the role.

If none of these values are provided, the function will simply run using its execution role.

#### account_id (optional)
The id of the account that owns the role `role_to_assume`.

#### role_to_assume (optional)
The name of the role to assume.
