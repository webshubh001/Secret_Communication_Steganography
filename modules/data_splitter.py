"""
modules/data_splitter.py — Splits encrypted bytes into N equal chunks.

Each chunk is accompanied by a metadata dict containing:
  • session_id  — links all chunks to a single SecretMessage
  • chunk_index — 0-based position of this chunk
  • total_chunks — total number of chunks in this session
  • chunk_hash   — SHA-256 of this chunk's bytes
  • data_hash    — SHA-256 of the complete encrypted payload (for full verification)

The metadata is serialised to JSON and stored as the header inside the stego image,
before the chunk data. This allows the decoder to verify integrity without any
external database query (the session_id links back to the DB for the AES key).
"""

import json
import math
from modules.integrity import sha256_bytes


def split_data(data: bytes, n: int, session_id: str, data_hash: str) -> list[dict]:
    """
    Split ``data`` into ``n`` chunks and wrap each with integrity metadata.

    Args:
        data:       The encrypted ciphertext to split.
        n:          Number of chunks (= number of cover images).
        session_id: UUID string identifying this encoding session.
        data_hash:  SHA-256 hex of the complete ``data`` (pre-computed by caller).

    Returns:
        List of ``n`` dicts, each with keys:
            - 'metadata': dict (session_id, chunk_index, total_chunks,
                                chunk_hash, data_hash)
            - 'data':     bytes (the raw chunk bytes)

    Raises:
        ValueError: If n < 1 or data is empty.
    """
    if n < 1:
        raise ValueError("Number of chunks must be at least 1.")
    if not data:
        raise ValueError("Cannot split empty data.")

    total_bytes = len(data)
    # Compute ceiling-divided chunk size so all data fits in n chunks
    chunk_size = math.ceil(total_bytes / n)

    chunks = []
    for i in range(n):
        start = i * chunk_size
        end = min(start + chunk_size, total_bytes)
        chunk_bytes = data[start:end]

        metadata = {
            'session_id': session_id,
            'chunk_index': i,
            'total_chunks': n,
            'chunk_hash': sha256_bytes(chunk_bytes),
            'data_hash': data_hash,
        }

        chunks.append({
            'metadata': metadata,
            'data': chunk_bytes,
        })

    return chunks


def serialise_chunk(chunk_dict: dict) -> bytes:
    """
    Serialise a chunk dict (from split_data) into bytes for LSB embedding.

    Format:
        [4 bytes big-endian: metadata JSON length]
        [metadata JSON bytes]
        [chunk raw data bytes]

    This format allows the decoder to extract the metadata length first,
    then read exactly that many bytes for metadata, and the rest for data.
    """
    meta_json = json.dumps(chunk_dict['metadata']).encode('utf-8')
    meta_len = len(meta_json).to_bytes(4, byteorder='big')
    return meta_len + meta_json + chunk_dict['data']


def deserialise_chunk(raw: bytes) -> dict:
    """
    Reverse of serialise_chunk().

    Args:
        raw: bytes extracted from a stego image by LSB decoding.

    Returns:
        dict with keys 'metadata' (dict) and 'data' (bytes).

    Raises:
        ValueError: If the byte stream is malformed.
    """
    if len(raw) < 4:
        raise ValueError("Chunk data too short — possibly a corrupted stego image.")

    meta_len = int.from_bytes(raw[:4], byteorder='big')
    if len(raw) < 4 + meta_len:
        raise ValueError(
            f"Expected {meta_len} bytes of metadata but only {len(raw) - 4} available."
        )

    meta_json = raw[4: 4 + meta_len]
    chunk_data = raw[4 + meta_len:]

    try:
        metadata = json.loads(meta_json.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Metadata JSON is corrupt: {exc}") from exc

    # Validate required metadata keys
    required = {'session_id', 'chunk_index', 'total_chunks', 'chunk_hash', 'data_hash'}
    missing = required - set(metadata.keys())
    if missing:
        raise ValueError(f"Metadata missing required fields: {missing}")

    return {'metadata': metadata, 'data': chunk_data}
