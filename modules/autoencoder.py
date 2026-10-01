"""
modules/autoencoder.py — Convolutional Autoencoder (Unit V)
============================================================

Academic context — Unit V: Convolutional Neural Networks / Autoencoders
------------------------------------------------------------------------
A Convolutional Autoencoder (CAE) is an unsupervised neural network that learns
to compress images into a compact latent representation and reconstruct them.

Architecture used here:

    ENCODER
    -------
    Input  (H × W × 3)   — normalised RGB image [0, 1]
    Conv2D(32, 3×3, relu) → MaxPooling(2×2)
    Conv2D(16, 3×3, relu) → MaxPooling(2×2)
    Conv2D(8,  3×3, relu) → MaxPooling(2×2)
    ↓
    Latent representation  (H/8 × W/8 × 8)

    DECODER
    -------
    Conv2D(8,  3×3, relu) → UpSampling(2×2)
    Conv2D(16, 3×3, relu) → UpSampling(2×2)
    Conv2D(32, 3×3, relu) → UpSampling(2×2)
    Conv2D(3,  3×3, sigmoid) → Reconstructed image

Integration in this project
----------------------------
The autoencoder is applied AROUND the existing LSB steganography pipeline:

  ENCODE side:
    1. Load cover image.
    2. Normalise pixel values to [0, 1].
    3. Pass through encoder → get latent representation.
    4. Decode back → reconstructed image.
    5. Compute reconstruction loss (MSE between original and reconstructed).
    6. Store loss as metadata (ae_reconstruction_loss in StegoImage).
    7. The ORIGINAL cover image is still used for LSB steganography
       (the autoencoder does NOT replace LSB — it adds AI image analysis).

  DECODE side (metrics):
    1. Load extracted stego image.
    2. Pass through autoencoder.
    3. Compute reconstruction loss.
    4. Display alongside MSE/PSNR/SSIM in the result page.

Model is saved as:  models/autoencoder.keras
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
TARGET_SIZE = (128, 128)   # images are resized to this before AE processing
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'models', 'autoencoder.keras'
)


class ConvAutoencoder:
    """
    Lightweight convolutional autoencoder for image representation and
    reconstruction quality analysis.

    Usage
    -----
    ae = ConvAutoencoder()
    result = ae.process_image(image_path)
    # result['reconstruction_loss'] — float MSE between original and reconstruction
    # result['latent_shape']        — shape of the compressed representation
    """

    def __init__(self):
        self._model = None
        self._encoder = None
        self._model_available = False

    # ── Model management ───────────────────────────────────────────────────────

    def _load_model(self) -> bool:
        if self._model is not None:
            return self._model_available

        if not os.path.exists(_MODEL_PATH):
            logger.warning(
                "Autoencoder model not found at %s. "
                "Run training/train_autoencoder.py to train it. "
                "Autoencoder metrics will be skipped.",
                _MODEL_PATH
            )
            self._model_available = False
            return False

        try:
            import tensorflow as tf
            self._model = tf.keras.models.load_model(_MODEL_PATH)
            # Extract encoder sub-model (all layers up to the latent layer)
            # The latent layer is named 'latent_space' in the training script.
            try:
                latent_output = self._model.get_layer('latent_space').output
                self._encoder = tf.keras.Model(
                    inputs=self._model.input, outputs=latent_output
                )
            except ValueError:
                self._encoder = None  # encoder sub-model optional
            self._model_available = True
            logger.info("Autoencoder loaded from %s", _MODEL_PATH)
            return True
        except Exception as exc:
            logger.warning("Failed to load autoencoder: %s", exc)
            self._model_available = False
            return False

    @property
    def is_available(self) -> bool:
        return self._load_model()

    # ── Image helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_normalised(image_path: str) -> np.ndarray:
        """
        Load an image, resize to TARGET_SIZE, convert to RGB float32 in [0, 1].
        Returns shape: (1, H, W, 3) — batch dimension included for Keras.
        """
        img = Image.open(image_path).convert('RGB').resize(TARGET_SIZE)
        arr = np.array(img, dtype=np.float32) / 255.0
        return arr[np.newaxis, ...]   # add batch dimension

    @staticmethod
    def _mse(a: np.ndarray, b: np.ndarray) -> float:
        """Mean Squared Error between two arrays."""
        return float(np.mean((a - b) ** 2))

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_image(self, image_path: str) -> dict:
        """
        Run the full autoencoder pipeline on a single image.

        Args:
            image_path: Path to a cover or stego image.

        Returns:
            dict with:
                'available'           — bool
                'reconstruction_loss' — float MSE (None if unavailable)
                'latent_shape'        — tuple or None
                'original_shape'      — (H, W, 3)
                'target_size'         — TARGET_SIZE tuple
        """
        result = {
            'available': False,
            'reconstruction_loss': None,
            'latent_shape': None,
            'original_shape': None,
            'target_size': TARGET_SIZE,
        }

        try:
            # Record original shape (before resize)
            with Image.open(image_path) as img:
                result['original_shape'] = (img.height, img.width, 3)
        except Exception as exc:
            logger.warning("Cannot open image %s: %s", image_path, exc)
            return result

        if not self._load_model():
            return result

        try:
            # ENCODER: normalise → compress
            x = self._load_normalised(image_path)

            # LATENT representation
            if self._encoder is not None:
                latent = self._encoder.predict(x, verbose=0)
                result['latent_shape'] = latent.shape[1:]  # strip batch dim

            # DECODER: reconstruct from latent (full forward pass)
            x_reconstructed = self._model.predict(x, verbose=0)

            # RECONSTRUCTION LOSS (pixel-level MSE)
            loss = self._mse(x, x_reconstructed)
            result['reconstruction_loss'] = round(float(loss), 6)
            result['available'] = True

            logger.debug(
                "Autoencoder: image=%s loss=%.6f latent=%s",
                os.path.basename(image_path),
                loss,
                result['latent_shape']
            )

        except Exception as exc:
            logger.warning("Autoencoder process_image error: %s", exc)

        return result

    def encode_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Return only the latent representation of the image (encoder half).

        Args:
            image_path: Path to image.

        Returns:
            numpy array of latent representation, or None if unavailable.
        """
        if not self._load_model() or self._encoder is None:
            return None
        try:
            x = self._load_normalised(image_path)
            return self._encoder.predict(x, verbose=0)[0]  # remove batch dim
        except Exception as exc:
            logger.warning("Autoencoder encode_image error: %s", exc)
            return None

    def decode_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Return the reconstructed image as a uint8 numpy array (H, W, 3).

        Args:
            image_path: Path to image.

        Returns:
            Reconstructed image array, or None if unavailable.
        """
        if not self._load_model():
            return None
        try:
            x = self._load_normalised(image_path)
            reconstructed = self._model.predict(x, verbose=0)[0]  # remove batch
            # Denormalise: [0, 1] → [0, 255] uint8
            return (reconstructed * 255).clip(0, 255).astype(np.uint8)
        except Exception as exc:
            logger.warning("Autoencoder decode_image error: %s", exc)
            return None

    def compute_cover_stego_metrics(
        self, cover_path: str, stego_path: str
    ) -> dict:
        """
        Process both cover and stego images and return comparative AE metrics.

        Returns:
            dict with 'cover_loss', 'stego_loss', 'available'.
        """
        cover_result = self.process_image(cover_path)
        stego_result = self.process_image(stego_path)
        return {
            'available': cover_result['available'] and stego_result['available'],
            'cover_loss': cover_result.get('reconstruction_loss'),
            'stego_loss': stego_result.get('reconstruction_loss'),
        }


# ── Module-level singleton ─────────────────────────────────────────────────────
conv_autoencoder = ConvAutoencoder()
