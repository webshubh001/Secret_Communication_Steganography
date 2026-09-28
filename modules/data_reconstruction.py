"""
modules/data_reconstruction.py — Reconstruct encrypted data from extracted chunks.

This module handles the receiver-side pipeline:
  1. Validate that all expected chunks are present (no missing/duplicate).
  2. Deserialise each chunk to get metadata + raw bytes.
  3. Verify per-chunk SHA-256 hashes.
  4. Sort chunks by chunk_index.
  5. Concatenate in order to reconstruct the full encrypted payload.
  6. Verify the full-payload SHA-256 hash.
  7. Return the verified ciphertext ready for AES decryption.
"""

from __future__ import annotations

from modules.data_splitter import deserialise_chunk
from modules.integrity import sha256_bytes, verify_chunks


class ReconstructionError(Exception):
    """Raised when data reconstruction fails for any reason."""


def reconstruct_from_raw(raw_chunks: list[bytes]) -> tuple[bytes, str]:
    """
    Reconstruct the full encrypted payload from a list of raw byte blobs
    extracted from stego images (via LSB extraction).

    Args:
        raw_chunks: List of raw bytes, one per stego image (order may vary).

    Returns:
        Tuple of (ciphertext: bytes, session_id: str)

    Raises:
        ReconstructionError: On any validation failure.
    """
    if not raw_chunks:
        raise ReconstructionError("No stego images were provided.")

    # ── Step 1: Deserialise each raw blob ──────────────────────────────────────
    parsed = []
    for idx, raw in enumerate(raw_chunks):
        try:
            chunk_dict = deserialise_chunk(raw)
        except ValueError as exc:
            raise ReconstructionError(
                f"Image {idx + 1} appears to be corrupted or is not a stego image: {exc}"
            ) from exc
        parsed.append(chunk_dict)

    # ── Step 2: Validate session consistency ────────────────────────────────────
    session_ids = {c['metadata']['session_id'] for c in parsed}
    if len(session_ids) > 1:
        raise ReconstructionError(
            "The uploaded images belong to different encoding sessions. "
            "Please ensure all images are from the same session."
        )
    session_id = session_ids.pop()

    total_chunks = parsed[0]['metadata']['total_chunks']
    data_hash = parsed[0]['metadata']['data_hash']

    # ── Step 3: Check all chunks report the same total ─────────────────────────
    for chunk in parsed:
        if chunk['metadata']['total_chunks'] != total_chunks:
            raise ReconstructionError(
                "Inconsistent total_chunks metadata across images. "
                "One or more images may have been tampered with."
            )
        if chunk['metadata']['data_hash'] != data_hash:
            raise ReconstructionError(
                "Data hash mismatch across images. The images may belong to "
                "different sessions or have been tampered with."
            )

    # ── Step 4: Check correct count ────────────────────────────────────────────
    if len(parsed) < total_chunks:
        missing = total_chunks - len(parsed)
        raise ReconstructionError(
            f"Only {len(parsed)} of {total_chunks} required images were provided. "
            f"{missing} image(s) are missing. "
            "The secret message cannot be reconstructed."
        )
    if len(parsed) > total_chunks:
        raise ReconstructionError(
            f"Too many images uploaded ({len(parsed)} provided, {total_chunks} expected). "
            "Remove any duplicate images and try again."
        )

    # ── Step 5: Check for duplicate chunk indexes ───────────────────────────────
    indexes = [c['metadata']['chunk_index'] for c in parsed]
    if len(set(indexes)) != len(indexes):
        dupes = [i for i in indexes if indexes.count(i) > 1]
        raise ReconstructionError(
            f"Duplicate chunk indexes detected: {sorted(set(dupes))}. "
            "You may have uploaded the same image twice."
        )

    # ── Step 6: Check no gaps in chunk indexes ─────────────────────────────────
    expected_indexes = set(range(total_chunks))
    actual_indexes = set(indexes)
    if actual_indexes != expected_indexes:
        missing_idx = sorted(expected_indexes - actual_indexes)
        raise ReconstructionError(
            f"Missing chunk indexes: {missing_idx}. "
            "One or more required stego images are missing or incorrect."
        )

    # ── Step 7: Sort by chunk_index ────────────────────────────────────────────
    parsed.sort(key=lambda c: c['metadata']['chunk_index'])

    # ── Step 8: Verify per-chunk hashes ────────────────────────────────────────
    chunk_bytes_list = [c['data'] for c in parsed]
    chunk_hashes = [c['metadata']['chunk_hash'] for c in parsed]
    failed_chunks = verify_chunks(chunk_bytes_list, chunk_hashes)
    if failed_chunks:
        raise ReconstructionError(
            f"Integrity verification failed for chunk(s): "
            f"{[i + 1 for i in failed_chunks]}. "
            "The corresponding stego image(s) have been tampered with or corrupted."
        )

    # ── Step 9: Concatenate and verify full payload ─────────────────────────────
    ciphertext = b''.join(chunk_bytes_list)
    if sha256_bytes(ciphertext) != data_hash:
        raise ReconstructionError(
            "Full payload integrity check failed. "
            "The reconstructed data does not match the expected hash — "
            "one or more chunks may be corrupted."
        )

    return ciphertext, session_id
