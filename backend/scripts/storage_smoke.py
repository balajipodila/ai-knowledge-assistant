import sys
from uuid import uuid4
import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings


def main() -> int:
    try:
        settings = get_settings()
    except Exception:
        print("Error: Could not load application settings.")
        return 2

    if (
        settings.file_storage_backend != "s3"
        or not settings.s3_endpoint_url
        or not settings.s3_bucket
        or not settings.s3_bucket.strip()
        or not settings.s3_region.strip()
        or settings.s3_access_key_id is None
        or not settings.s3_access_key_id.get_secret_value().strip()
        or settings.s3_secret_access_key is None
        or not settings.s3_secret_access_key.get_secret_value().strip()
    ):
        print("Refusing to run: S3 storage settings are incomplete or backend is not set to 's3'.")
        return 2

    prefix = f"smoke-test-{uuid4().hex}"
    test_key = f"{prefix}/smoke-test.txt"
    test_body = b"storage smoke test content"

    print("Initializing S3/R2 client for smoke test...")
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            config=Config(
                s3={"addressing_style": "path"},
                signature_version="s3v4",
            ),
        )
    except Exception:
        print("Failed to initialize S3 client.")
        return 1

    # Step 1: Put object
    print("Step 1: Put test object... ", end="", flush=True)
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=test_key,
            Body=test_body,
            ContentType="text/plain",
        )
        print("PASS")
    except (BotoCoreError, ClientError) as error:
        print(f"FAIL ({type(error).__name__})")
        return 1

    # Step 2: Head/Read object
    print("Step 2: Head/Verify test object... ", end="", flush=True)
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=test_key)
        print("PASS")
    except (BotoCoreError, ClientError) as error:
        print(f"FAIL ({type(error).__name__})")
        # Attempt cleanup
        try:
            client.delete_object(Bucket=settings.s3_bucket, Key=test_key)
        except Exception:
            pass
        return 1

    # Step 3: Delete object
    print("Step 3: Delete test object... ", end="", flush=True)
    try:
        client.delete_object(Bucket=settings.s3_bucket, Key=test_key)
        print("PASS")
    except (BotoCoreError, ClientError) as error:
        print(f"FAIL ({type(error).__name__})")
        return 1

    print("All storage smoke test steps completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
