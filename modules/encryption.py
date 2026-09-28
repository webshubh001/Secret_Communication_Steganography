"""
modules/encryption.py — AES-256-CBC encryption/decryption module.

Pipeline:
    plaintext  →  AES-256-CBC encrypt  →  base64 ciphertext
    ciphertext →  AES-256-CBC decrypt  →  plaintext

Key handling:
    - Each encoding session generates a random 32-byte AES key.
    - That key is itself encrypted using a master secret (from env) and stored
      in the database. This avoids hard-coding any keys.
    - The master secret MUST be set via the MASTER_SECRET environment variable.
"""

import base64
import hashlib
import os

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


# ─── Session-level AES key generation ──────────────────────────────────────────

def generate_aes_key() -> bytes:
    """Generate a cryptographically random 256-bit (32-byte) AES key."""
    return get_random_bytes(32)


# ─── Data encryption / decryption ──────────────────────────────────────────────

def encrypt_data(data: bytes, key: bytes) -> bytes:
    """
    Encrypt arbitrary bytes using AES-256-CBC with PKCS7 padding.

    Returns:
        iv (16 bytes) + ciphertext bytes concatenated.
        The IV is prepended so it can be extracted during decryption.
    """
    if len(key) != 32:
        raise ValueError("AES key must be exactly 32 bytes (256-bit).")

    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(data, AES.block_size))
    # Prepend IV to ciphertext for self-contained decryption
    return cipher.iv + ciphertext


def decrypt_data(encrypted: bytes, key: bytes) -> bytes:
    """
    Decrypt bytes produced by encrypt_data().

    Args:
        encrypted: iv (16 bytes) + ciphertext
        key: 32-byte AES key

    Returns:
        Original plaintext bytes.

    Raises:
        ValueError: If decryption fails (wrong key, corrupted data, etc.)
    """
    if len(key) != 32:
        raise ValueError("AES key must be exactly 32 bytes (256-bit).")
    if len(encrypted) < 32:
        raise ValueError("Encrypted data is too short to be valid.")

    iv = encrypted[:16]
    ciphertext = encrypted[16:]

    cipher = AES.new(key, AES.MODE_CBC, iv)
    try:
        return unpad(cipher.decrypt(ciphertext), AES.block_size)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Decryption failed — wrong key or corrupted data: {exc}") from exc


# ─── AES key protection (for database storage) ─────────────────────────────────

def _derive_master_key(master_secret: str) -> bytes:
    """Derive a 256-bit key from the master secret using SHA-256."""
    return hashlib.sha256(master_secret.encode('utf-8')).digest()


def encrypt_aes_key(aes_key: bytes, master_secret: str) -> str:
    """
    Encrypt a 32-byte AES key using the master secret so it can be safely
    stored in the database.

    Returns:
        Base64-encoded string: iv (16 bytes) + encrypted key.
    """
    master_key = _derive_master_key(master_secret)
    cipher = AES.new(master_key, AES.MODE_CBC)
    ct = cipher.encrypt(pad(aes_key, AES.block_size))
    payload = cipher.iv + ct
    return base64.b64encode(payload).decode('utf-8')


def decrypt_aes_key(encrypted_key_b64: str, master_secret: str) -> bytes:
    """
    Decrypt an AES key previously encrypted with encrypt_aes_key().

    Returns:
        The original 32-byte AES key.

    Raises:
        ValueError: If decryption fails.
    """
    master_key = _derive_master_key(master_secret)
    payload = base64.b64decode(encrypted_key_b64)
    iv = payload[:16]
    ct = payload[16:]
    cipher = AES.new(master_key, AES.MODE_CBC, iv)
    try:
        return unpad(cipher.decrypt(ct), AES.block_size)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"AES key decryption failed: {exc}") from exc
