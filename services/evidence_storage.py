"""
EcoQuest — Evidence Storage Service.

Provides secure, private filesystem persistence for camera-captured mission proof.
Features:
- Stores evidence outside the public static directory.
- Accepts raw binary, Flask FileStorage, or Base64 Data URLs.
- MIME type and extension validation (JPEG, PNG, WebP, WebM, MP4).
- Safe unique filename generation with collision prevention.
- Path traversal protection (secure_filename + commonpath validation).
- Cleanup helpers for failed or rejected transactions.
- Ready for seamless future Supabase Storage abstraction.
"""

import os
import re
import uuid
import time
import base64
from typing import Optional, Union
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"webm", "mp4"}
ALLOWED_EVIDENCE_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/webm": "webm",
    "video/mp4": "mp4",
}


def _get_evidence_folder() -> str:
    """Resolve absolute path to private evidence storage directory."""
    if current_app and "EVIDENCE_FOLDER" in current_app.config:
        folder = current_app.config["EVIDENCE_FOLDER"]
    else:
        folder = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", "instance", "evidence")
    os.makedirs(folder, exist_ok=True)
    return os.path.abspath(folder)


def save_evidence_media(
    data: Union[str, bytes],
    prefix: str = "proof",
    is_video: bool = False,
) -> str:
    """
    Save camera evidence (image or video) from either base64 DataURL or raw bytes.

    Args:
        data: Base64 DataURL (e.g. 'data:image/jpeg;base64,...') or raw bytes.
        prefix: Filename prefix ('before', 'after', 'video').
        is_video: Whether the payload is expected to be video.

    Returns:
        The generated unique filename.

    Raises:
        ValueError on invalid data, unsupported format, or excessive size.
    """
    folder = _get_evidence_folder()
    max_size = current_app.config.get("MAX_EVIDENCE_SIZE", 25 * 1024 * 1024) if current_app else 25 * 1024 * 1024

    ext = "webm" if is_video else "jpg"
    raw_bytes = b""

    if isinstance(data, str):
        # Handle Data URL: "data:image/jpeg;base64,...."
        match = re.match(r"^data:([^;]+);base64,(.+)$", data, re.DOTALL)
        if match:
            mime = match.group(1).lower()
            b64_str = match.group(2)
            ext = MIME_TO_EXT.get(mime, ext)
            try:
                raw_bytes = base64.b64decode(b64_str)
            except Exception as e:
                raise ValueError(f"Invalid base64 payload: {e}")
        else:
            # Raw string or plain base64
            try:
                raw_bytes = base64.b64decode(data)
            except Exception:
                raw_bytes = data.encode("utf-8")
    elif isinstance(data, bytes):
        raw_bytes = data
    elif hasattr(data, "read"):
        raw_bytes = data.read()
    else:
        raise ValueError("Unsupported media data type.")

    if not raw_bytes:
        raise ValueError("Empty evidence payload received.")

    if len(raw_bytes) > max_size:
        raise ValueError(f"Evidence file exceeds maximum permitted size of {max_size // (1024 * 1024)}MB.")

    # Validate extension against whitelist
    clean_ext = ext.lstrip(".").lower()
    if clean_ext not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise ValueError(f"Unsupported media extension: .{clean_ext}")

    # Generate unique collision-free filename
    unique_id = uuid.uuid4().hex[:12]
    timestamp = int(time.time())
    safe_prefix = secure_filename(prefix) or "evidence"
    filename = f"{safe_prefix}_{unique_id}_{timestamp}.{clean_ext}"

    # Path traversal safety check
    target_path = os.path.abspath(os.path.join(folder, filename))
    if os.path.commonpath([folder, target_path]) != folder:
        raise ValueError("Invalid storage path detected.")

    with open(target_path, "wb") as f:
        f.write(raw_bytes)

    return filename


def get_evidence_path(filename: str) -> Optional[str]:
    """
    Safely retrieve absolute path of an evidence file with traversal protection.
    Returns None if file does not exist or path is invalid.
    """
    if not filename:
        return None

    clean_name = secure_filename(filename)
    if not clean_name or clean_name != filename:
        return None

    folder = _get_evidence_folder()
    target_path = os.path.abspath(os.path.join(folder, clean_name))

    # Guard against traversal outside evidence folder
    if os.path.commonpath([folder, target_path]) != folder:
        return None

    if os.path.isfile(target_path):
        return target_path

    return None


def delete_evidence_file(filename: str) -> bool:
    """Delete evidence file from disk (e.g. rollback on failed transaction)."""
    path = get_evidence_path(filename)
    if path and os.path.exists(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False
