"""
modules/face_authentication.py — Face recognition authentication module.

Uses the `face_recognition` library (built on dlib) which generates
128-dimensional face embeddings.  Embeddings are compared using Euclidean
distance — a distance below the configured threshold means the faces match.

Security notes:
  • Raw face images are NOT stored permanently.  Only the 128-d embedding is
    stored in the database as a JSON array.
  • The threshold is configurable via the FACE_RECOGNITION_THRESHOLD env var.
  • Multiple faces in a single image cause rejection (ambiguous identity).
  • No face detected causes rejection with a clear error message.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import face_recognition
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Default threshold (can be overridden via app config)
DEFAULT_THRESHOLD = 0.6


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _load_image_array(source) -> np.ndarray:
    """
    Load an image from a file path (str) or raw bytes and return
    it as an RGB numpy array suitable for face_recognition.
    """
    if isinstance(source, str):
        # File path
        img = Image.open(source).convert('RGB')
    else:
        # Raw bytes — must wrap in BytesIO so Pillow reads as file content,
        # NOT as a filename (which would crash trying to decode JPEG bytes as UTF-8)
        buf = io.BytesIO(source) if isinstance(source, bytes) else source
        img = Image.open(buf).convert('RGB')
    return np.array(img)



# ─── Core API ──────────────────────────────────────────────────────────────────

def get_face_embedding(image_source) -> list[float]:
    """
    Detect a face in the image and return its 128-d embedding.

    Args:
        image_source: File path (str) or raw image bytes.

    Returns:
        List of 128 floats representing the face embedding.

    Raises:
        ValueError: If no face is detected or multiple faces are detected.
    """
    arr = _load_image_array(image_source)
    # face_recognition expects RGB
    locations = face_recognition.face_locations(arr, model='hog')

    if len(locations) == 0:
        raise ValueError(
            "No face detected in the image. "
            "Please ensure your face is clearly visible and well-lit."
        )
    if len(locations) > 1:
        raise ValueError(
            f"{len(locations)} faces detected in the image. "
            "Please upload an image containing only your face."
        )

    encodings = face_recognition.face_encodings(arr, known_face_locations=locations)
    if not encodings:
        raise ValueError(
            "Face detected but could not generate an embedding. "
            "Please try a clearer, higher-resolution image."
        )

    return encodings[0].tolist()   # 128-d list of floats


def compare_embeddings(
    stored_embedding: list[float],
    probe_embedding: list[float],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """
    Compare a stored face embedding against a probe embedding.

    Args:
        stored_embedding: The 128-d list stored in the database.
        probe_embedding:  The 128-d list from the authentication attempt.
        threshold:        Maximum allowed Euclidean distance (default 0.6).

    Returns:
        dict with keys:
            'authenticated' (bool)
            'distance' (float) — smaller = more similar
            'threshold' (float)
    """
    stored = np.array(stored_embedding, dtype=np.float64)
    probe = np.array(probe_embedding, dtype=np.float64)

    distance = float(np.linalg.norm(stored - probe))
    authenticated = distance <= threshold

    return {
        'authenticated': authenticated,
        'distance': round(distance, 4),
        'threshold': threshold,
    }


def verify_face(image_source, stored_embedding: list[float], threshold: float = DEFAULT_THRESHOLD) -> dict:
    """
    End-to-end face verification: detect → embed → compare.

    Args:
        image_source:     File path or raw bytes of the face image to authenticate.
        stored_embedding: The 128-d embedding registered in the database.
        threshold:        Distance threshold for acceptance.

    Returns:
        dict with 'authenticated' (bool), 'distance' (float), 'threshold' (float),
        and optionally 'error' (str) if a non-fatal error occurred.
    """
    try:
        probe_embedding = get_face_embedding(image_source)
        result = compare_embeddings(stored_embedding, probe_embedding, threshold)
        logger.info(
            "Face verification: distance=%.4f threshold=%.2f authenticated=%s",
            result['distance'], threshold, result['authenticated']
        )
        return result
    except ValueError as exc:
        logger.warning("Face verification error: %s", exc)
        return {
            'authenticated': False,
            'distance': None,
            'threshold': threshold,
            'error': str(exc),
        }
