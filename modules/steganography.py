"""
modules/steganography.py — LSB (Least Significant Bit) image steganography.

Encoding:
    Cover Image + Data → LSB Embedding → Stego Image

Decoding:
    Stego Image → LSB Extraction → Data

Header format (first 32 LSBs of the image = first 32 pixel-channel LSBs):
    • 32 bits (big-endian uint32) = total payload length in bytes

Payload:
    • payload_length bytes of embedded data

The data capacity of an image is:
    capacity_bytes = (width × height × channels) // 8  −  4 (header)

Only PNG output is used (lossless) — JPEG would destroy the hidden bits.
"""

import struct
import numpy as np
from PIL import Image


def _image_to_array(image_path: str) -> np.ndarray:
    """Load an image and return it as a uint8 numpy array (RGB)."""
    img = Image.open(image_path).convert('RGB')
    return np.array(img, dtype=np.uint8)


def _array_to_image(arr: np.ndarray) -> Image.Image:
    """Convert a uint8 numpy array back to a PIL Image."""
    return Image.fromarray(arr.astype(np.uint8), 'RGB')


def capacity_bytes(image_path: str) -> int:
    """
    Return the maximum number of bytes that can be hidden in this image
    using 1-LSB steganography, minus the 4-byte length header.
    """
    arr = _image_to_array(image_path)
    total_bits = arr.size  # width × height × 3 channels, each contributes 1 bit
    return (total_bits // 8) - 4


def embed(image_path: str, data: bytes, output_path: str) -> None:
    """
    Embed ``data`` into the cover image at ``image_path`` using 1-LSB
    steganography and save the result (PNG) to ``output_path``.

    Args:
        image_path:  Path to the cover image.
        data:        Raw bytes to embed (already serialised chunk).
        output_path: Where to save the stego image (must end in .png).

    Raises:
        ValueError: If the image lacks sufficient capacity for the data.
    """
    arr = _image_to_array(image_path)
    flat = arr.flatten()

    payload_len = len(data)
    # Check capacity: we need 32 bits for the header + payload_len * 8 bits
    required_bits = 32 + payload_len * 8
    if required_bits > flat.size:
        cap = (flat.size // 8) - 4
        raise ValueError(
            f"Image capacity is {cap} bytes but {payload_len} bytes of data "
            f"need to be embedded. Please use a larger image or reduce the "
            f"payload size."
        )

    # Encode the 4-byte length header + payload as bits using numpy
    header_bytes = struct.pack('>I', payload_len)
    full_data = header_bytes + data
    bits_array = np.unpackbits(np.frombuffer(full_data, dtype=np.uint8))

    # Embed each bit into the LSB of the corresponding pixel channel value using vectorization
    flat[:len(bits_array)] = (flat[:len(bits_array)] & 254) | bits_array

    stego_arr = flat.reshape(arr.shape)
    stego_img = _array_to_image(stego_arr)
    stego_img.save(output_path, format='PNG')


def extract(stego_path: str) -> bytes:
    """
    Extract hidden bytes from a stego image previously processed by embed().

    Args:
        stego_path: Path to the stego image.

    Returns:
        The original embedded bytes.

    Raises:
        ValueError: If the image does not appear to contain valid embedded data.
    """
    arr = _image_to_array(stego_path)
    flat = arr.flatten()

    if flat.size < 32:
        raise ValueError("Image too small to contain any embedded data.")

    # Read the first 32 LSBs (4 bytes) to get the payload length
    lsbs = flat & 1
    header_bytes = np.packbits(lsbs[:32]).tobytes()
    payload_len = struct.unpack('>I', header_bytes)[0]

    if payload_len == 0:
        raise ValueError(
            "No data found in this image (payload length header is zero). "
            "This may not be a stego image."
        )

    required_bits = 32 + payload_len * 8
    if required_bits > flat.size:
        raise ValueError(
            f"Corrupt stego image: claims {payload_len} bytes but image only "
            f"has capacity for {(flat.size // 8) - 4} bytes."
        )

    # Read the payload bits and pack them back into bytes
    payload_bits = lsbs[32:required_bits]
    data = np.packbits(payload_bits).tobytes()
    return data
