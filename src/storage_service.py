import os
import io
import time
from typing import Optional

# Cloudflare R2 Configuration (S3 Compatible)
CF_R2_ACCOUNT_ID = os.getenv("CF_R2_ACCOUNT_ID", "").strip()
CF_R2_ACCESS_KEY_ID = os.getenv("CF_R2_ACCESS_KEY_ID", "").strip()
CF_R2_SECRET_ACCESS_KEY = os.getenv("CF_R2_SECRET_ACCESS_KEY", "").strip()
CF_R2_BUCKET_NAME = os.getenv("CF_R2_BUCKET_NAME", "smartwork-docs").strip()
CF_R2_PUBLIC_DOMAIN = os.getenv("CF_R2_PUBLIC_DOMAIN", "").strip().rstrip("/")

r2_client = None

def get_r2_client():
    global r2_client
    if r2_client is not None:
        return r2_client
    
    if CF_R2_ACCOUNT_ID and CF_R2_ACCESS_KEY_ID and CF_R2_SECRET_ACCESS_KEY:
        try:
            import boto3
            from botocore.config import Config
            
            endpoint = f"https://{CF_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
            r2_client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=CF_R2_ACCESS_KEY_ID,
                aws_secret_access_key=CF_R2_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4'),
                region_name='auto'
            )
            print(f"[Cloudflare R2] Connected to bucket: {CF_R2_BUCKET_NAME}")
            return r2_client
        except Exception as e:
            print(f"[Cloudflare R2] Initialization notice: {e}")
            return None
    return None

def upload_docx_to_r2(doc_id: str, file_bytes: bytes, filename: str = "") -> Optional[str]:
    """Uploads a generated DOCX file to Cloudflare R2 bucket."""
    client = get_r2_client()
    if not client:
        return None
    
    key = f"documents/{doc_id}.docx"
    try:
        client.put_object(
            Bucket=CF_R2_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        if CF_R2_PUBLIC_DOMAIN:
            return f"{CF_R2_PUBLIC_DOMAIN}/{key}"
        return key
    except Exception as e:
        print(f"[Cloudflare R2] Failed to upload {doc_id}: {e}")
        return None

def get_docx_from_r2(doc_id: str) -> Optional[bytes]:
    """Retrieves a DOCX file from Cloudflare R2 bucket."""
    client = get_r2_client()
    if not client:
        return None
    
    key = f"documents/{doc_id}.docx"
    try:
        response = client.get_object(Bucket=CF_R2_BUCKET_NAME, Key=key)
        return response['Body'].read()
    except Exception as e:
        print(f"[Cloudflare R2] Failed to fetch {doc_id}: {e}")
        return None
