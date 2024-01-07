import boto3
import logging
import pytest
import re
import time

from botocore.exceptions import ClientError
from unittest.mock import Mock, ANY, call

from aws_util import create_client

##
## Helpers and mocks
##

TEST_ACCOUNT = "123456789012"
TEST_ROLE_NAME = "example"
TEST_ROLE_ARN = f"arn:aws:iam::{TEST_ACCOUNT}:role/{TEST_ROLE_NAME}"
TEST_USER = "thatsme"
TEST_ROLE_MAX_DURATION = 900

TEST_ACCESS_KEY = "blah blah"
TEST_SECRET_KEY = "blah blah blah"
TEST_SESSION_TOKEN = "blah blah blah blah"


@pytest.fixture
def boto_mock(monkeypatch, iam_mock, sts_mock):
    boto_mock = Mock(spec=["client"])
    def client_invocation_handler(*args, **kwargs):
        if args[0] == "iam":
            return iam_mock
        elif args[0] == "sts":
            return sts_mock
        else:
            return Mock()  # which won't be used
    boto_mock.client.side_effect = client_invocation_handler
    monkeypatch.setattr(boto3, "client", boto_mock.client)
    return boto_mock


@pytest.fixture
def iam_mock(monkeypatch):
    iam_mock = Mock(spec=["get_role"])
    def get_role_invocation_handler(RoleName=None):
        if RoleName == TEST_ROLE_NAME:
            # just return the bits we care about
            return {
                'Role': {
                    'Arn': TEST_ROLE_ARN,
                    'MaxSessionDuration': TEST_ROLE_MAX_DURATION
                }
            }
    iam_mock.get_role.side_effect = get_role_invocation_handler
    return iam_mock


@pytest.fixture
def sts_mock(monkeypatch):
    sts_mock = Mock(spec=["assume_role", "get_caller_identity"])
    def get_caller_identity_invocation_handler():
        return {
            'UserId': "AIDA12345678901234567",
            'Account': TEST_ACCOUNT,
            'Arn': f"arn:aws:iam::{TEST_ACCOUNT}:user/{TEST_USER}",
        }
    sts_mock.get_caller_identity.side_effect = get_caller_identity_invocation_handler
    def assume_role_invocation_handler(RoleArn=None, RoleSessionName=None, DurationSeconds=None, Policy=None):
        # we return only what we use
        return {
            "Credentials": {
                "AccessKeyId": TEST_ACCESS_KEY,
                "SecretAccessKey": TEST_SECRET_KEY,
                "SessionToken": TEST_SESSION_TOKEN,
            }
        }
    sts_mock.assume_role.side_effect = assume_role_invocation_handler
    return sts_mock


##
## Test Cases
##


def test_invalid_arguments():
    with pytest.raises(ValueError, match=r"create_client: account requires role_name"):
        create_client('s3', account="123456789012")
    with pytest.raises(ValueError, match=r"create_client: policy requires role"):
        create_client('s3', policy="whatever")
    with pytest.raises(ValueError, match=r"create_client: can not specify both account/role_name and role_arn"):
        create_client('s3', account="123456789012", role_name="foo", role_arn="bar")


def test_create_with_default_credentials(boto_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3")
    print(boto_mock.client.call_args)
    boto_mock.client.assert_called_once_with("s3")
    assert len(caplog.records) == 0


def test_create_in_region_with_default_credentials(boto_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", region_name="us-west-1")
    print(boto_mock.client.call_args)
    boto_mock.client.assert_called_once_with("s3", region_name="us-west-1")
    assert len(caplog.records) == 0


def test_create_with_arn_and_session_name(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_arn=TEST_ROLE_ARN, session_name="example", duration=3600)
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    sts_mock.get_caller_identity.assert_not_called()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName="example",
        DurationSeconds=3600
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_create_with_arn_session_name_and_policy(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_arn=TEST_ROLE_ARN, session_name="example", duration=3600, policy="something")
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    sts_mock.get_caller_identity.assert_not_called()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName="example",
        DurationSeconds=3600,
        Policy="something"
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_create_with_arn_and_generated_session_name(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_arn=TEST_ROLE_ARN, duration=3600)
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    iam_mock.assert_not_called()
    sts_mock.get_caller_identity.assert_called_once_with()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
        DurationSeconds=3600
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_create_with_generated_session_name_from_assumed_role(boto_mock, iam_mock, sts_mock, caplog):
    existing_session_name = "argle-bargle"
    def alt_invocation_handler():
        return {
            'UserId': "AROAXXXXXXXXXXXXXXXXX:something",
            'Account': TEST_ACCOUNT,
            'Arn': f"arn:aws:sts::{TEST_ACCOUNT}:assumed-role/SomeIrrelevantRole/{existing_session_name}"
        }
    sts_mock.get_caller_identity.side_effect = alt_invocation_handler
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_arn=TEST_ROLE_ARN, duration=3600)
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    iam_mock.assert_not_called()
    sts_mock.get_caller_identity.assert_called_once_with()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName=existing_session_name,
        DurationSeconds=3600
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_create_with_account_and_role_name(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", account=TEST_ACCOUNT, role_name=TEST_ROLE_NAME)
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    iam_mock.assert_not_called()
    sts_mock.get_caller_identity.assert_called_once_with()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
        DurationSeconds=28800
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_create_with_local_role_name(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_name=TEST_ROLE_NAME)
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    iam_mock.get_role.assert_called_once_with(RoleName=TEST_ROLE_NAME)
    sts_mock.get_caller_identity.assert_called_once_with()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
        DurationSeconds=TEST_ROLE_MAX_DURATION
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )
    assert len(caplog.records) == 0


def test_duration_reduction(boto_mock, sts_mock, caplog):
    def alt_invocation_handler(RoleArn=None, RoleSessionName=None, DurationSeconds=None, Policy=None):
        if DurationSeconds > 3600:
            # this is copied from observed exception
            raise ClientError(
                {   'Error': {
                    'Type': 'Sender',
                    'Code': 'ValidationError',
                    'Message': 'The requested DurationSeconds exceeds the MaxSessionDuration set for this role.'
                }},
                "AssumeRole")
        return {
            "Credentials": {
                "AccessKeyId": TEST_ACCESS_KEY,
                "SecretAccessKey": TEST_SECRET_KEY,
                "SessionToken": TEST_SESSION_TOKEN,
            }
        }
    sts_mock.assume_role.side_effect = alt_invocation_handler
    create_client("s3", role_arn=TEST_ROLE_ARN, duration=9000)
    sts_mock.assume_role.assert_has_calls([
        call(
            RoleArn=TEST_ROLE_ARN,
            RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
            DurationSeconds=9000),
        call(
            RoleArn=TEST_ROLE_ARN,
            RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
            DurationSeconds=4500),
        call(
            RoleArn=TEST_ROLE_ARN,
            RoleSessionName=f"{TEST_ACCOUNT}-{TEST_USER}",
            DurationSeconds=2250),
        ])
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN
        )


def test_create_with_default_credentials_in_region(boto_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", region_name="us-west-1")
    print(boto_mock.client.call_args)
    boto_mock.client.assert_called_once_with("s3", region_name="us-west-1")
    assert len(caplog.records) == 0


def test_with_assumed_role_create_in_region(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_arn=TEST_ROLE_ARN, session_name="example", duration=3600, region_name="us-west-1")
    boto_mock.client.assert_any_call("sts")
    boto_mock.client.assert_any_call("iam")
    sts_mock.get_caller_identity.assert_not_called()
    sts_mock.assume_role.assert_called_once_with(
        RoleArn=TEST_ROLE_ARN,
        RoleSessionName="example",
        DurationSeconds=3600
        )
    boto_mock.client.assert_any_call(
        "s3",
        aws_access_key_id=TEST_ACCESS_KEY,
        aws_secret_access_key=TEST_SECRET_KEY,
        aws_session_token=TEST_SESSION_TOKEN,
        region_name="us-west-1"
        )
    assert len(caplog.records) == 0


def test_logging_create_with_default_credentials(boto_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", log_actions=True)
    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "creating s3 client with default credentials"


def test_log_create_with_lookups(boto_mock, iam_mock, sts_mock, caplog):
    caplog.set_level(logging.DEBUG)
    create_client("s3", role_name=TEST_ROLE_NAME, duration=3600, policy="something", log_actions=True)
    assert len(caplog.records) == 3
    assert caplog.records[0].msg == f"retrieving role {TEST_ROLE_NAME} for invoking account"
    assert caplog.records[1].msg == f"generating session name from caller identity"
    assert caplog.records[2].msg == f"creating s3 client with assumed role {TEST_ROLE_ARN}; session name: {TEST_ACCOUNT}-{TEST_USER}, duration: 3600, policy: something"
