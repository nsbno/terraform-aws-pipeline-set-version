#!/usr/bin/env python3.7
#
# Copyright (C) 2020 Erlend Ekern <dev@ekern.me>
#
# Distributed under terms of the MIT license.

"""
SSM parameters are used in each environment (test, stage, prod) to
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
    retry_wait_in_seconds = 15
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


def get_ecr_versions(image_tag):
    client = boto3.client("ecr")
    repositories = client.describe_repositories()["repositories"]
    logger.debug("Found %s ECR repositories", len(repositories))
    versions = {}
    for repo in repositories:
        name = repo["repositoryName"]
        # Only tagged images
        try:
            images = client.describe_images(
                repositoryName=name,
                imageIds=[{"imageTag": image_tag}],
                filter={"tagStatus": "TAGGED"},
            )["imageDetails"]
        except client.exceptions.ImageNotFoundException:
            logger.warn(
                "No (matching) images found in ECR repo '%s' -- the repository is either empty, or does not contain any images tagged with '%s'",
                name,
                image_tag,
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
                "Could not find an image in repository '%s' tagged with both '%s' and a SHA1",
                name,
                image_tag,
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


def get_lambda_versions(bucket_name, s3_prefix):
    s3 = boto3.client("s3")
    contents_of_lambda_folder = s3.list_objects(
        Bucket=bucket_name, Prefix=s3_prefix
    )

    s3_files = list(
        map(
            lambda s3_file: s3_file["Key"],
            contents_of_lambda_folder["Contents"],
        )
    )
    logger.info("Found S3 files '%s'", s3_files)
    s3_zips = list(
        filter(
            lambda key: key.endswith(".zip")
            and key.rsplit("/", 2)[1] == key.rsplit("/", 2)[2].rstrip(".zip"),
            s3_files,
        )
    )
    logger.info("Found Lambda zips '%s'", s3_zips)

    s3_resource = boto3.resource("s3")
    versions = {
        s3_key: s3_resource.Object(bucket_name, s3_key).version_id
        for s3_key in s3_zips
    }

    logger.info("Found Lambda versions '%s'", versions)
    return versions


def set_ssm_parameters_for_lambdas(
    credentials, lambda_versions, ssm_prefix, region
):
    for s3_key, s3_version in lambda_versions.items():
        lambda_name = s3_key.rsplit("/", 2)[1]
        ssm_name = f"/{ssm_prefix}/{lambda_name}"
        update_parameterstore(credentials, ssm_name, s3_version, region)


def set_ssm_parameters_for_ecr_repos(
    credentials, ecr_versions, ssm_prefix, region
):
    for repo, version in ecr_versions.items():
        ssm_name = f"/{ssm_prefix}/{repo}"
        update_parameterstore(credentials, ssm_name, version, region)


def lambda_handler(event, context):
    logger.info("Lambda triggered with input data '%s'", json.dumps(event))

    region = os.environ["AWS_REGION"]
    account_id = event["account_id"]
    cross_account_role = event["cross_account_role"]
    ecr_filter_tag = event["ecr_filter_tag"]
    lambda_s3_bucket = event["lambda_s3_bucket"]
    lambda_s3_prefix = event["lambda_s3_prefix"]
    ssm_prefix = event["ssm_prefix"]

    lambda_versions = get_lambda_versions(lambda_s3_bucket, lambda_s3_prefix)
    ecr_versions = get_ecr_versions(ecr_filter_tag)

    credentials = assume_role(account_id, cross_account_role)

    set_ssm_parameters_for_lambdas(
        credentials, lambda_versions, ssm_prefix, region
    )
    set_ssm_parameters_for_ecr_repos(
        credentials, ecr_versions, ssm_prefix, region
    )

    # TODO: Upload a metafile that contains the mapping between SHA1 and S3 version
    # lambda_meta = json.dumps({[{"lambda": l, "sha1": sha1, "s3_version": versions[l]} for l in versions]
    return