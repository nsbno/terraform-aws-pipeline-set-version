terraform {
  required_version = ">= 0.12.23"
}

provider "aws" {
  version = ">= 2.46"
  region  = "eu-west-1"
}

data "aws_caller_identity" "current-account" {}
data "aws_region" "current" {}

locals {
  current_account_id = data.aws_caller_identity.current-account.account_id
  current_region     = data.aws_region.current.name
  name_prefix        = "example"
}


##################################
#                                #
# Step Function                  #
#                                #
##################################
resource "aws_sfn_state_machine" "state_machine" {
  definition = local.state_definition
  name       = "${local.name_prefix}-state-machine"
  role_arn   = aws_iam_role.state_machine_role.arn
}

resource "aws_iam_role" "state_machine_role" {
  assume_role_policy = data.aws_iam_policy_document.state_machine_assume.json
}

resource "aws_iam_role_policy" "lambda_to_state_machine" {
  policy = data.aws_iam_policy_document.lambda_for_state_machine.json
  role   = aws_iam_role.state_machine_role.id
}


##################################
#                                #
# set-version                    #
#                                #
##################################
module "set_version_lambda" {
  source                = "github.com/nsbno/terraform-aws-pipeline-set-version" # Should be pinned to a specific ref
  name_prefix           = local.name_prefix
  ecr_image_tag_filters = ["master-branch"]
  ecr_repositories      = ["${local.name_prefix}-docker-app"]
  ssm_prefix            = "${local.name_prefix}/versions"
  lambda_s3_bucket      = "example-bucket"
  lambda_s3_prefix      = "lambdas"
}
