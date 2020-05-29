#!/usr/bin/env python3.7
#
# Copyright (C) 2020 Erlend Ekern <dev@ekern.me>
#
# Distributed under terms of the MIT license.

"""
SSM parameters are used in each environment (service, test, stage, prod) to
reflect the current versions of Lambda functions and Docker images.

For a given environment, this script updates these parameters to
the newest Lambda and ECR versions found in the artifact bucket and
ECR repositories, respectively, of the service account.
"""

import boto3
import botocore
import json
import time
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def assume_role(account_id, account_role):
    sts_client = boto3.client("sts")
    role_arn = f"arn:aws:iam::{account_id}:role/{account_role}"
    assuming_role = True
    retry_wait_in_seconds = 5
    while assuming_role:
        try:
            logger.info("Trying to assume role with arn '%s'", role_arn)
            assumedRoleObject = sts_client.assume_role(
                RoleArn=role_arn, RoleSessionName="pipeline-set-version"
            )
            assuming_role = False
        except botocore.exceptions.ClientError:
            assuming_role = True
            logger.exception("Failed to assume role with arn '%s'", role_arn)
            logger.info(
                "Retrying role assumption for role with arn '%s' in %ss",
                role_arn,
                retry_wait_in_seconds,
            )
            time.sleep(retry_wait_in_seconds)
    logger.info("Successfully assumed role with arn '%s'", role_arn)
    return assumedRoleObject["Credentials"]


def get_ecr_versions(repo_name_filters=[], image_tag_filters=[]):
    """Gets the latest image version of all ECR repositories in the current account.

    Only repositories containing at least one image tagged with `image_tag` and a tag
    ending with "-SHA1" are included. The image version is extracted from the SHA1-tag
    of the most recently pushed image.

    Args:
        repo_name_filters: An optional list of names of ECR to filter on (e.g., ["trafficinfo-baseline-micronaut"])
        image_tag_filters: An optional list of image tags to filter on (e.g., ["master-branch"]).

    Returns:
        A dictionary containing the names of ECR repositories together with the
        latest image version in each repository.
    """

    client = boto3.client("ecr")
    repositories = client.describe_repositories()["repositories"]
    if len(repo_name_filters):
        repositories = list(
            filter(
                lambda r: r["repositoryName"] in repo_name_filters,
                repositories,
            )
        )
    logger.debug("Found %s ECR repositories", len(repositories))
    versions = {}
    for repo in repositories:
        name = repo["repositoryName"]
        # Only tagged images
        try:
            filter_kwargs = {}
            if len(image_tag_filters):
                filter_kwargs = {
                    "imageIds": [
                        {"imageTag": image_tag}
                        for image_tag in image_tag_filters
                    ]
                }
            images = client.describe_images(
                repositoryName=name,
                filter={"tagStatus": "TAGGED"},
                **filter_kwargs,
            )["imageDetails"]
        except client.exceptions.ImageNotFoundException:
            logger.warn(
                "No (matching) images found in ECR repo '%s' -- the repository is either empty, or does not contain any images tagged with '%s'",
                name,
                ", ".join(image_tag_filters),
            )
            continue
        # Only keep images ttagged with a SHA1-tag
        filtered_images = list(
            filter(
                lambda image: any(
                    t.endswith("-SHA1") for t in image["imageTags"]
                ),
                images,
            )
        )
        if len(filtered_images) == 0:
            logger.warn(
                "Could not find an image in repository '%s' tagged with both a SHA1 and the tags '%s'",
                name,
                ", ".join(image_tag_filters),
            )
            continue
        # Sort the images by date
        sorted_images = sorted(
            filtered_images, key=lambda image: image["imagePushedAt"]
        )
        most_recent_image = sorted_images[-1]
        most_recent_image_sha1_tags = [
            t.split("-SHA1")[0]
            for t in most_recent_image["imageTags"]
            if t.endswith("-SHA1")
        ]
        if len(most_recent_image_sha1_tags) > 1:
            logger.warn(
                "Expected to find an image in repository '%s' with one SHA1-tag, but found multiple such tags",
                name,
            )
            continue
        most_recent_sha1 = most_recent_image_sha1_tags[0]
        logger.info(
            "Most recent image in repository '%s' has SHA1 '%s'",
            name,
            most_recent_sha1,
        )
        versions[name] = most_recent_sha1

    logger.info("Found ECR versions '%s'", versions)
    return versions


def update_parameterstore(credentials, name, value, region):
    """Updates (or creates) one parameter in parameter store.

    Args:
        credentials: The credentials to use when creating the SSM client.
        name: The name of the parameter.
        value: The value of the parameter.
        region: The region to use when creating the SSM client.
    """
    if credentials is None:
        ssm = boto3.client("ssm", region_name=region)
    else:
        ssm = boto3.client(
            "ssm",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region,
        )
    logger.info(
        "Setting SSM parameter '%s' to '%s' in region '%s'",
        name,
        value,
        region,
    )
    ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


def get_lambda_versions(lambda_names, bucket_name, s3_prefix):
    """Gets the S3 version of all Lambda deployment packages located under a given S3 prefix.

    A deployment package located under the prefix is treated as a Lambda iff it is inside a
    folder and contains a file named `package.jar` or `package.zip`
    (e.g., `nsbno/trafficinfo-aws/lambdas/<function-name>/package.zip`).

    Args:
        lambda_names: The name of the Lambda functions to set versions for.
        bucket_name: The name of the S3 bucket to use when looking for Lambda deployment packages.
        s3_prefix: The S3 prefix to use when looking for Lambda deployment packages
            (e.g., `nsbno/trafficinfo-aws/lambdas`).

    Returns:
        A dictionary containing the S3 keys of the Lambda functions together with the
        S3 version of their respective deployment packages.
    """
    s3 = boto3.client("s3")
    contents_of_lambda_folder = s3.list_objects(
        Bucket=bucket_name, Prefix=s3_prefix
    )

    try:
        content = contents_of_lambda_folder["Contents"]
    except KeyError:
        # 'Contents' key will be missing from response if no matching
        # objects were found
        logger.info(
            "Did not find any objects in bucket '%s' matching the prefix '%s'",
            bucket_name,
            s3_prefix,
        )
        return {}

    s3_files = list(map(lambda s3_file: s3_file["Key"], content))
    logger.info("Found S3 files '%s'", s3_files)
    s3_deployment_packages = list(
        filter(
            lambda key: key.rsplit("/", 2)[1] in lambda_names
            and key.rsplit("/", 1) != s3_prefix
            and (key.endswith("/package.zip") or key.endswith("/package.jar")),
            s3_files,
        )
    )
    logger.info(
        "Found Lambda deployment packages '%s'", s3_deployment_packages
    )

    s3_resource = boto3.resource("s3")
    versions = {
        s3_key: s3_resource.Object(bucket_name, s3_key).version_id
        for s3_key in s3_deployment_packages
    }

    logger.info("Found Lambda versions '%s'", versions)
    return versions


def set_ssm_parameters_for_lambdas(
    credentials, lambda_versions, ssm_prefix, region
):
    """Updates (or creates) one parameter in parameter store for each
    pair of Lambda function and version passed in.

    Example: The versions in the following dict would result in a parameter with
        name "hello-world" and value "AAL5Srm2XNB10IziOoI7nfZ4_nsHNr_B":
        `{"nsbno/trafficinfo-aws/lambdas/hello-world/package.zip": "AAL5Srm2XNB10IziOoI7nfZ4_nsHNr_B"}`

    Args:
        credentials: The credentials to use when creating the SSM client.
        lambda_versions: A dictionary containing the S3 key of Lambda zip files
            as well as their S3 version.
        ssm_prefix: The prefix to use for the parameters in parameter store
            (e.g., `trafficinfo`).
        region: The region to use when creating the SSM client.
    """

    for s3_key, s3_version in lambda_versions.items():
        lambda_name = s3_key.rsplit("/", 2)[1]
        ssm_name = f"/{ssm_prefix}/{lambda_name}"
        update_parameterstore(credentials, ssm_name, s3_version, region)


def set_ssm_parameters_for_ecr_repos(
    credentials, ecr_versions, ssm_prefix, region
):
    """Updates (or creates) one parameter in parameter store for each
    pair of ECR repository and version passed in.

    Example: The versions in the following dict would result in a parameter with
        name "trafficinfo-docker-app" and value "abcdefgh-SHA1":
        `{"trafficinfo-docker-app": "acdefgh-SHA1"}`

    Args:
        credentials: The credentials to use when creating the SSM client.
        lambda_versions: A dictionary containing the names of ECR
            repositories as well as their version.
        ssm_prefix: The prefix to use for the parameters in parameter store
            (e.g., `trafficinfo`).
        region: The region to use when creating the SSM client.
    """
    for repo, version in ecr_versions.items():
        ssm_name = f"/{ssm_prefix}/{repo}"
        update_parameterstore(credentials, ssm_name, version, region)


def lambda_handler(event, context):
    logger.info("Lambda triggered with input data '%s'", json.dumps(event))

    region = os.environ["AWS_REGION"]

    main_ssm_prefix = os.environ["SSM_PREFIX"]
    additional_ssm_prefix = event.get("ssm_prefix", "")
    ssm_prefix = (
        f"{main_ssm_prefix}/{additional_ssm_prefix}"
        if additional_ssm_prefix
        else main_ssm_prefix
    )

    ecr_image_tag_filters = event.get("ecr_image_tag_filters", [])
    ecr_repositories = event.get("ecr_repositories", [])
    lambda_names = event.get("lambda_names", [])
    lambda_s3_bucket = event.get("lambda_s3_bucket", "")
    lambda_s3_prefix = event.get("lambda_s3_prefix", "")

    role_to_assume = event.get("role_to_assume", "")
    account_id = event.get("account_id", "")

    lambda_versions = {}
    if lambda_s3_bucket and lambda_s3_prefix and len(lambda_names):
        lambda_versions = get_lambda_versions(
            lambda_names, lambda_s3_bucket, lambda_s3_prefix
        )

    ecr_versions = {}
    if len(ecr_repositories):
        ecr_versions = get_ecr_versions(
            ecr_repositories, ecr_image_tag_filters
        )

    credentials = (
        assume_role(account_id, role_to_assume)
        if account_id and role_to_assume
        else None
    )

    set_ssm_parameters_for_lambdas(
        credentials, lambda_versions, ssm_prefix, region
    )
    set_ssm_parameters_for_ecr_repos(
        credentials, ecr_versions, ssm_prefix, region
    )

    # TODO: Upload a metafile that contains the mapping between SHA1 and S3 version
    # lambda_meta = json.dumps({[{"lambda": l, "sha1": sha1, "s3_version": versions[l]} for l in versions]
    return
