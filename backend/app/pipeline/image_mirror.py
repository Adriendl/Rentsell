"""Mirror listing images to S3-compatible storage."""

from __future__ import annotations

import hashlib
import os

import httpx


async def mirror_image(
    url: str,
    s3_client,
    bucket: str,
    public_base_url: str,
) -> str:
    """Download *url* and upload it to S3 if not already present.

    The object key is ``SHA-256(url) + original_extension``.
    Returns the public URL of the mirrored object.
    """
    ext = os.path.splitext(url.split("?")[0])[-1] or ".jpg"
    key = hashlib.sha256(url.encode()).hexdigest() + ext

    # Check whether the object already exists
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return f"{public_base_url.rstrip('/')}/{key}"
    except s3_client.exceptions.ClientError:
        pass

    # Download the image
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.content
        content_type = resp.headers.get("content-type", "image/jpeg")

    # Upload to S3
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )

    return f"{public_base_url.rstrip('/')}/{key}"


async def mirror_listing_images(
    images: list[str],
    settings,
) -> list[str]:
    """Mirror every image in *images* to S3.

    If ``settings.storage_bucket`` is falsy the original URLs are returned
    unchanged (passthrough mode for local development).
    """
    bucket = getattr(settings, "storage_bucket", None)
    if not bucket:
        return list(images)

    import boto3

    s3_client = boto3.client(
        "s3",
        region_name=getattr(settings, "aws_region", "eu-west-3"),
        aws_access_key_id=getattr(settings, "aws_access_key_id", None),
        aws_secret_access_key=getattr(settings, "aws_secret_access_key", None),
    )

    public_base_url: str = getattr(
        settings,
        "storage_public_url",
        f"https://{bucket}.s3.amazonaws.com",
    )

    mirrored: list[str] = []
    for url in images:
        try:
            public_url = await mirror_image(url, s3_client, bucket, public_base_url)
            mirrored.append(public_url)
        except Exception:
            # Keep the original URL on failure so we don't lose the reference
            mirrored.append(url)

    return mirrored
