"""Shared AWS helpers for SpendOptimo backend."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

import boto3

READ_ROLE_ARN = os.getenv("READ_ROLE_ARN")
EXECUTOR_ROLE_ARN = os.getenv("EXECUTOR_ROLE_ARN")
REGION = os.getenv("AWS_REGION", "us-east-1")


def _assume_role(role_arn: str, session_name: str) -> dict:
    sts = boto3.client("sts", region_name=REGION)
    creds = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)["Credentials"]
    return {
        "aws_access_key_id": creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token": creds["SessionToken"],
    }


@lru_cache(maxsize=8)
def read_credentials() -> Optional[dict]:
    if not READ_ROLE_ARN:
        return None
    return _assume_role(READ_ROLE_ARN, "SpendOptimoRead")


@lru_cache(maxsize=4)
def executor_credentials() -> Optional[dict]:
    if not EXECUTOR_ROLE_ARN:
        return None
    return _assume_role(EXECUTOR_ROLE_ARN, "SpendOptimoExec")


def client(service: str, *, use_executor: bool = False):
    creds = executor_credentials() if use_executor else read_credentials()
    session_params = creds or {}
    return boto3.client(service, region_name=REGION, **session_params)
