"""
EcoQuest — Supabase Cloud Storage Integration Service.

Provides secure persistent cloud storage for user profile pictures and mission proof media.
Architecture:
- Public bucket ('profiles') for avatar pictures.
- Private bucket ('evidence') for sensitive mission photos and videos.
- Uses server-side service-role key exclusively.
- Service-role credentials are never exposed to browser, templates, or client API responses.
- Graceful local filesystem fallback if Supabase credentials are not configured.
"""

import os
import mimetypes
from typing import Optional, Tuple
from flask import current_app
import requests


def _get_config():
    """Retrieve Supabase storage configuration parameters safely."""
    if current_app:
        url = (current_app.config.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        service_key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        profiles_bucket = (
            current_app.config.get("SUPABASE_STORAGE_PROFILES_BUCKET")
            or os.environ.get("SUPABASE_STORAGE_PROFILES_BUCKET")
            or "profile-pictures"
        )
        evidence_bucket = (
            current_app.config.get("SUPABASE_STORAGE_EVIDENCE_BUCKET")
            or os.environ.get("SUPABASE_STORAGE_EVIDENCE_BUCKET")
            or "mission-evidence"
        )
    else:
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        profiles_bucket = os.environ.get("SUPABASE_STORAGE_PROFILES_BUCKET", "profile-pictures")
        evidence_bucket = os.environ.get("SUPABASE_STORAGE_EVIDENCE_BUCKET", "mission-evidence")
    return url, service_key, profiles_bucket, evidence_bucket


def is_supabase_storage_enabled() -> bool:
    """Return True if Supabase URL and service role key are configured."""
    url, service_key, _, _ = _get_config()
    return bool(url and service_key and service_key.strip())


def upload_profile_picture_to_supabase(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Upload a profile picture to the private 'profile-pictures' Supabase Storage bucket.
    The object remains private and accessible only via server-side authenticated proxy.

    Returns:
        (True, filename) if successful, or (False, error_message) on failure.
    """
    url, service_key, profiles_bucket, _ = _get_config()
    if not url or not service_key:
        return False, "Supabase storage is not configured."

    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "image/jpeg"

    endpoint = f"{url}/storage/v1/object/{profiles_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    try:
        response = requests.post(endpoint, data=file_bytes, headers=headers, timeout=10)
        if response.status_code in (200, 201):
            return True, filename
        return False, f"Supabase storage upload failed with status {response.status_code}."
    except Exception as exc:
        return False, f"Network error during Supabase upload: {str(exc)}"


def download_profile_picture_from_supabase(filename: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Fetch private profile picture from Supabase Storage using server-side service credentials.
    Keeps credentials completely hidden from client side.

    Returns:
        (bytes, content_type) if found, or (None, None) if not found or on error.
    """
    url, service_key, profiles_bucket, _ = _get_config()
    if not url or not service_key:
        return None, None

    endpoint = f"{url}/storage/v1/object/authenticated/{profiles_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        if response.status_code == 200:
            c_type = response.headers.get("Content-Type", "image/jpeg")
            return response.content, c_type
        # Fallback to direct object endpoint
        fallback_endpoint = f"{url}/storage/v1/object/{profiles_bucket}/{filename}"
        fallback_res = requests.get(fallback_endpoint, headers=headers, timeout=15)
        if fallback_res.status_code == 200:
            c_type = fallback_res.headers.get("Content-Type", "image/jpeg")
            return fallback_res.content, c_type
        return None, None
    except Exception:
        return None, None


def delete_profile_picture_from_supabase(filename: str) -> bool:
    """Delete a profile picture object from the private Supabase storage bucket."""
    url, service_key, profiles_bucket, _ = _get_config()
    if not url or not service_key:
        return False

    endpoint = f"{url}/storage/v1/object/{profiles_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
    }

    try:
        response = requests.delete(endpoint, headers=headers, timeout=10)
        return response.status_code in (200, 204)
    except Exception:
        return False


def upload_evidence_to_supabase(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Upload sensitive mission evidence (photo/video) to private 'evidence' bucket.
    The object remains private and accessible only via server-side authenticated proxy.

    Returns:
        (True, filename) if successful, or (False, error_message) on failure.
    """
    url, service_key, _, evidence_bucket = _get_config()
    if not url or not service_key:
        return False, "Supabase storage is not configured."

    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        content_type = content_type or "application/octet-stream"

    endpoint = f"{url}/storage/v1/object/{evidence_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    try:
        response = requests.post(endpoint, data=file_bytes, headers=headers, timeout=15)
        if response.status_code in (200, 201):
            return True, filename
        return False, f"Supabase storage upload failed with status {response.status_code}."
    except Exception as exc:
        return False, f"Network error during Supabase upload: {str(exc)}"


def download_evidence_from_supabase(filename: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Fetch private evidence media from Supabase Storage using server-side service credentials.
    Keeps credentials completely hidden from client side.

    Returns:
        (bytes, content_type) if found, or (None, None) if not found or on error.
    """
    url, service_key, _, evidence_bucket = _get_config()
    if not url or not service_key:
        return None, None

    endpoint = f"{url}/storage/v1/object/authenticated/{evidence_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        if response.status_code == 200:
            c_type = response.headers.get("Content-Type", "application/octet-stream")
            return response.content, c_type
        # Fallback to direct object endpoint if authenticated prefix differs
        fallback_endpoint = f"{url}/storage/v1/object/{evidence_bucket}/{filename}"
        fallback_res = requests.get(fallback_endpoint, headers=headers, timeout=15)
        if fallback_res.status_code == 200:
            c_type = fallback_res.headers.get("Content-Type", "application/octet-stream")
            return fallback_res.content, c_type
        return None, None
    except Exception:
        return None, None


def delete_evidence_from_supabase(filename: str) -> bool:
    """Delete an evidence object from the private Supabase storage bucket."""
    url, service_key, _, evidence_bucket = _get_config()
    if not url or not service_key:
        return False

    endpoint = f"{url}/storage/v1/object/{evidence_bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {service_key}",
    }

    try:
        response = requests.delete(endpoint, headers=headers, timeout=10)
        return response.status_code in (200, 204)
    except Exception:
        return False
