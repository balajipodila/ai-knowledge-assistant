import sys
from uuid import uuid4
import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.services.storage import create_file_storage, S3FileStorage


def main() -> int:
    try:
        settings = get_settings()
    except Exception:
        print("Error: Could not load application settings.")
        return 2

    if settings.file_storage_backend != "s3":
        print("Refusing to run: File storage backend is not set to 's3'.")
        return 2

    prefix = f"smoke-test-{uuid4().hex}"
    test_key = f"{prefix}/smoke-test.txt"
    test_body = b"storage smoke test content"

    print("Initializing S3/R2 storage via app factory for smoke test...")
    try:
        storage = create_file_storage(settings)
        if not isinstance(storage, S3FileStorage):
            print("Refusing to run: Storage backend is not S3FileStorage.")
            return 2
        client = storage.client
        bucket = storage.bucket
    except Exception:
        print("Failed to initialize S3 storage.")
        return 1

    # Step 1: Put object
    print("Step 1: Put test object... ", end="", flush=True)
    try:
        client.put_object(
            Bucket=bucket,
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
        client.head_object(Bucket=bucket, Key=test_key)
        print("PASS")
    except (BotoCoreError, ClientError) as error:
        print(f"FAIL ({type(error).__name__})")
        # Attempt cleanup
        try:
            client.delete_object(Bucket=bucket, Key=test_key)
        except Exception:
            pass
        return 1

    # Step 3: Delete object
    print("Step 3: Delete test object... ", end="", flush=True)
    try:
        client.delete_object(Bucket=bucket, Key=test_key)
        print("PASS")
    except (BotoCoreError, ClientError) as error:
        print(f"FAIL ({type(error).__name__})")
        return 1

    print("All storage smoke test steps completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
