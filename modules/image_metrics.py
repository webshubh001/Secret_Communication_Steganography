"""
modules/image_metrics.py — Image quality metrics for stego image evaluation.

Calculates:
  • MSE  — Mean Squared Error (lower is better; 0 = identical)
  • PSNR — Peak Signal-to-Noise Ratio in dB (higher is better; >40 dB is excellent)
  • SSIM — Structural Similarity Index (higher is better; 1.0 = identical)

These metrics are computed by comparing the original cover image against the
stego image to quantify the visual distortion introduced by LSB embedding.

LSB steganography typically achieves PSNR > 50 dB and SSIM > 0.99,
making the stego images visually indistinguishable from the originals.
"""

from __future__ import annotations

import math
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim_metric


def _load_rgb_array(path: str) -> np.ndarray:
    """Load an image as a float64 RGB numpy array (0–255 range)."""
    return np.array(Image.open(path).convert('RGB'), dtype=np.float64)


def compute_mse(original_path: str, stego_path: str) -> float:
    """
    Compute the Mean Squared Error between the cover and stego images.

    MSE = mean((original_pixel - stego_pixel)^2) across all channels.

    Returns:
        MSE value (float). 0.0 means the images are identical.
    """
    orig = _load_rgb_array(original_path)
    stego = _load_rgb_array(stego_path)

    if orig.shape != stego.shape:
        raise ValueError(
            f"Image shapes differ: original {orig.shape} vs stego {stego.shape}."
        )

    mse = float(np.mean((orig - stego) ** 2))
    return round(mse, 6)


def compute_psnr(original_path: str, stego_path: str, mse: float = None) -> float:
    """
    Compute the Peak Signal-to-Noise Ratio in decibels.

    PSNR = 10 × log10(MAX_I^2 / MSE)
    where MAX_I = 255 for 8-bit images.

    Returns:
        PSNR in dB. Returns float('inf') if MSE == 0 (identical images).
    """
    if mse is None:
        mse = compute_mse(original_path, stego_path)

    if mse == 0:
        return float('inf')

    psnr = 10.0 * math.log10((255.0 ** 2) / mse)
    return round(psnr, 4)


def compute_ssim(original_path: str, stego_path: str) -> float:
    """
    Compute the Structural Similarity Index Measure (SSIM).

    SSIM is computed per channel and averaged.

    Returns:
        SSIM value in [−1, 1]. 1.0 means structurally identical.
    """
    orig = _load_rgb_array(original_path)
    stego = _load_rgb_array(stego_path)

    if orig.shape != stego.shape:
        raise ValueError(
            f"Image shapes differ: original {orig.shape} vs stego {stego.shape}."
        )

    # Compute SSIM directly using channel_axis for significantly better performance
    val = ssim_metric(
        orig,
        stego,
        data_range=255.0,
        channel_axis=-1,
    )

    return round(float(val), 6)


def compute_all_metrics(original_path: str, stego_path: str) -> dict:
    """
    Compute MSE, PSNR, and SSIM in a single call.

    Returns:
        dict with keys 'mse', 'psnr', 'ssim'.
    """
    try:
        mse = compute_mse(original_path, stego_path)
        psnr = compute_psnr(original_path, stego_path, mse=mse)
        ssim = compute_ssim(original_path, stego_path)
        return {'mse': mse, 'psnr': psnr, 'ssim': ssim}
    except Exception as exc:
        return {'mse': None, 'psnr': None, 'ssim': None, 'error': str(exc)}
