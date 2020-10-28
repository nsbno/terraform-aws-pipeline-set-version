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
import re

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


def get_ecr_versions(applications):
    """Gets the latest image version of all ECR repositories in the current account.

    Only repositories containing at least one image tagged with `image_tag` and a tag
    ending with "-SHA1" are included. The image version is extracted from the SHA1-tag
    of the most recently pushed image.

    Args:
        applications: A dictionary of ECR repository names to find versions for (e.g., { "my-ecr-repo": { "tag_filters": ["master-branch"]}, where tag_filters is an optional list of image tags to filter on.

    Returns:
        A dictionary containing the names of ECR repositories together with the
        latest image version in each repository.
    """

    client = boto3.client("ecr")
    repositories = client.describe_repositories()["repositories"]
    if len(repositories):
        repositories = list(
            filter(
                lambda r: r["repositoryName"] in applications,
                repositories,
            )
        )
    logger.debug("Found %s ECR repositories", len(repositories))
    versions = {}
    for repo in repositories:
        name = repo["repositoryName"]
        image_tag_filters = applications[repo].get("tag_filters", [])
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


def get_s3_artifact_versions(
    applications,
    bucket_name,
    s3_prefix,
    allowed_key_patterns=[r"[a-z0-9]{7}\.(zip|jar)$"],
):
    """Gets the S3 version of application artifacts stored under a given S3 prefix.

    A file located under the prefix is treated as an application artifact iff it is inside a
    dedicated folder and contains a file that follows a pattern.
    (e.g., `nsbno/trafficinfo-aws/lambdas/<application-name>/<sha1>.zip`).

    Args:
        applications: A dictionary of S3 artifacts to find versions for (e.g., { "my-s3-artifact": { "tag_filters": ["master-branch"]}, where tag_filters is an optional list of S3 metadata tags to filter artifacts on.
        bucket_name: The name of the S3 bucket to use when looking for application artifacts.
        s3_prefix: The S3 prefix to use when looking for application artifacts
            (e.g., `nsbno/trafficinfo-aws/lambdas`).
        allowed_key_patterns: Allowed S3 key patterns for application artifacts.

    Returns:
        A dictionary containing the application names together with the
        SHA1 of the latest artifact.
    """
    s3 = boto3.client("s3")
    s3_resource = boto3.resource("s3")
    versions = {}

    for application_name, details in applications.items():
        artifact_tag_filters = details.get("tag_filters", [])
        prefix = f"{s3_prefix + '/' if s3_prefix else ''}{application_name}/"
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        try:
            objects = response["Contents"]
        except KeyError:
            logger.info(
                "Did not find any objects in bucket '%s' matching the prefix '%s'",
                bucket_name,
                prefix,
            )
            continue

        while response["IsTruncated"]:
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                ContinuationToken=response["NextContinuationToken"],
                Prefix=prefix,
            )
            objects = objects + response["Contents"]
        logger.info(
            "Found a total of %s objects under prefix '%s' %s",
            len(objects),
            f"{bucket_name}/{prefix}",
            objects,
        )
        valid_objects = list(
            filter(
                lambda obj: any(
                    re.search(pattern, obj["Key"])
                    for pattern in allowed_key_patterns
                ),
                objects,
            )
        )
        logger.info(
            "Found %s valid objects under prefix '%s' %s",
            len(valid_objects),
            f"{bucket_name}/{prefix}",
            valid_objects,
        )
        sorted_objects = sorted(
            valid_objects,
            key=lambda obj: obj["LastModified"].timestamp(),
            reverse=True,
        )
        if len(sorted_objects):
            for obj in sorted_objects:
                metadata = s3_resource.Object(bucket_name, obj["Key"]).metadata
                logger.info(
                    "Object with key '%s' has metadata '%s'",
                    obj["Key"],
                    metadata,
                )
                tags = (
                    json.loads(metadata["tags"])
                    if metadata.get("tags", None)
                    else None
                )
                if (
                    tags
                    and any(tag.endswith("-SHA1") for tag in tags)
                    and all(tag in tags for tag in artifact_tag_filters)
                ):
                    version = next(
                        (
                            tag.split("-SHA1")[0]
                            for tag in tags
                            if tag.endswith("-SHA1")
                        ),
                        None,
                    )
                    if version:
                        versions[application_name] = version
                        break

    logger.info("Found versions '%s'", versions)
    return versions


def set_ssm_parameters(credentials, versions, ssm_prefix, region):
    """Updates (or creates) one parameter in parameter store for each
    pair of application and version passed in.

    Example: The versions in the following dict would result in a parameter with
        name "/<ssm-prefix>/trafficinfo-docker-app" and value "abcdefgh":
        `{"trafficinfo-docker-app": "acdefgh"}`

    Args:
        credentials: The credentials to use when creating the SSM client.
        versions: A dictionary containing the names of applications
            as well as their version.
        ssm_prefix: The prefix to use for the parameters in parameter store
            (e.g., `trafficinfo`).
        region: The region to use when creating the SSM client.
    """
    if len(ssm_prefix) == 0 or ssm_prefix.lower().startswith("aws"):
        logger.error("SSM prefix '%s' is not valid", ssm_prefix)
        raise ValueError()

    for application, version in versions.items():
        ssm_name = f"/{ssm_prefix}/{application}"
        update_parameterstore(credentials, ssm_name, version, region)


def lambda_handler(event, context):
    logger.info("Lambda triggered with input data '%s'", json.dumps(event))

    region = os.environ["AWS_REGION"]

    ssm_prefix = event.get("ssm_prefix", "")

    get_versions = event.get("get_versions", True)
    set_versions = event.get("set_versions", True)

    ecr_applications = event.get("ecr_applications", {}) or {
        app: {"tag_filters": event.get("ecr_image_tag_filters", [])}
        for app in event.get("ecr_repositories", [])
    }  # Fallback to stay backwards compatible

    lambda_s3_bucket = event.get("lambda_s3_bucket", "")
    lambda_s3_prefix = event.get("lambda_s3_prefix", "")
    lambda_applications = event.get("lambda_applications", {}) or {
        app: {"tag_filters": event.get("lambda_tag_filters", [])}
        for app in event.get("lambda_names", [])
    }  # Fallback to stay backwards compatible

    frontend_s3_bucket = event.get("frontend_s3_bucket", "")
    frontend_s3_prefix = event.get("frontend_s3_prefix", "")
    frontend_applications = event.get("frontend_applications", {}) or {
        app: {"tag_filters": event.get("frontend_tag_filters", [])}
        for app in event.get("frontend_names", [])
    }  # Fallback to stay backwards compatible

    role_to_assume = event.get("role_to_assume", "")
    account_id = event.get("account_id", "")

    versions = event.get("versions", {})
    ecr_versions = versions.get("ecr", {})
    frontend_versions = versions.get("frontend", {})
    lambda_versions = versions.get("lambda", {})

    if get_versions and lambda_s3_bucket and len(lambda_applications):
        lambda_versions = get_s3_artifact_versions(
            lambda_applications,
            lambda_s3_bucket,
            lambda_s3_prefix,
            [r"/[a-z0-9]{7,}\.(zip|jar)$"],
        )

    if get_versions and frontend_s3_bucket and len(frontend_applications):
        frontend_versions = get_s3_artifact_versions(
            frontend_applications,
            frontend_s3_bucket,
            frontend_s3_prefix,
            [r"/[a-z0-9]{7,}\.zip$"],
        )

    if get_versions and len(ecr_applications):
        ecr_versions = get_ecr_versions(ecr_applications)

    if set_versions:
        if len(
            set().union(ecr_versions, frontend_versions, lambda_versions)
        ) != len(ecr_versions) + len(frontend_versions) + len(lambda_versions):
            logger.error(
                "One or more ECR, Lambda and/or frontend applications are sharing the same name"
            )
            raise ValueError()
        credentials = (
            assume_role(account_id, role_to_assume)
            if account_id and role_to_assume
            else None
        )
        set_ssm_parameters(credentials, lambda_versions, ssm_prefix, region)
        set_ssm_parameters(credentials, frontend_versions, ssm_prefix, region)
        set_ssm_parameters(credentials, ecr_versions, ssm_prefix, region)

    return {
        "ecr": ecr_versions,
        "frontend": frontend_versions,
        "lambda": lambda_versions,
    }
