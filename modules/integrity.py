"""
modules/integrity.py — SHA-256 integrity verification utilities.

Used to:
  • Hash the complete encrypted payload before splitting (data_hash).
  • Hash each individual chunk (chunk_hash).
  • Hash stego image files after writing (file_hash).
  • Verify all hashes during reconstruction.
"""

import hashlib
import os
from typing import Union


def sha256_bytes(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(filepath: str) -> str:
    """
    Return the hex-encoded SHA-256 digest of a file on disk.
    Reads in chunks to handle large files without loading into RAM.
    """
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_bytes(data: bytes, expected_hash: str) -> bool:
    """Return True iff sha256_bytes(data) matches expected_hash."""
    return sha256_bytes(data) == expected_hash


def verify_file(filepath: str, expected_hash: str) -> bool:
    """Return True iff sha256_file(filepath) matches expected_hash."""
    if not os.path.isfile(filepath):
        return False
    return sha256_file(filepath) == expected_hash


def verify_chunks(chunks: list[bytes], chunk_hashes: list[str]) -> list[int]:
    """
    Verify each chunk against its expected hash.

    Returns:
        List of chunk indexes that FAILED verification (empty list = all OK).
    """
    failed = []
    for idx, (chunk, expected) in enumerate(zip(chunks, chunk_hashes)):
        if sha256_bytes(chunk) != expected:
            failed.append(idx)
    return failed
