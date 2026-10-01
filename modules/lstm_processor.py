"""
modules/lstm_processor.py — LSTM Sequence Processor (Unit IV)
==============================================================

Academic context — Unit IV: Recurrent Neural Networks / LSTM
-------------------------------------------------------------
Long Short-Term Memory (LSTM) networks are a special kind of RNN capable of
learning long-range dependencies in sequential data.  An LSTM cell maintains
two state vectors:

    h_t  — hidden state  (short-term memory / output)
    c_t  — cell state    (long-term memory)

Four gates control information flow:

    Forget gate  f_t = σ(W_f · [h_{t-1}, x_t] + b_f)
    Input  gate  i_t = σ(W_i · [h_{t-1}, x_t] + b_i)
    Cell update  g_t = tanh(W_g · [h_{t-1}, x_t] + b_g)
    Output gate  o_t = σ(W_o · [h_{t-1}, x_t] + b_o)

    c_t = f_t ⊙ c_{t-1}  +  i_t ⊙ g_t
    h_t = o_t ⊙ tanh(c_t)

Integration in this project
----------------------------
The LSTMProcessor wraps a small Keras model that:

  ENCODE side:
    1. Takes the AES-encrypted byte sequence.
    2. Reshapes it into fixed-length windows (input sequences).
    3. Passes it through a Bidirectional LSTM encoder.
    4. Produces a compact learned representation (features).
    5. The original encrypted bytes are still passed to LSB steganography
       unchanged — the LSTM features are stored as metadata to allow
       sequence-level validation on the decode side.

  DECODE side:
    1. Extracts the encrypted byte sequence from stego images.
    2. Re-runs the LSTM encoder on the extracted bytes.
    3. Compares the produced representation against the stored one.
    4. If the representations are sufficiently close (cosine similarity),
       the sequence is validated — confirming data integrity at the
       neural-network level IN ADDITION TO SHA-256.
    5. AES decryption then proceeds.

Model architecture (lightweight — academic demo):
    Input  → Reshape(sequence_len, 1) → Bidirectional LSTM(32) → Dense(16, relu)
    Output → Dense(8)  [compact feature vector]

Model is saved as:  models/lstm_model.keras
"""

from __future__ import annotations

import logging
import os
import struct
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
# Each LSTM input window processes this many bytes at once.
SEQUENCE_LENGTH = 64        # 64-byte windows
FEATURE_DIM = 8             # output feature vector dimension
SIMILARITY_THRESHOLD = 0.90 # cosine similarity threshold for validation

# Path to the saved Keras model (relative to project root)
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'models', 'lstm_model.keras'
)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1-D vectors."""
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 1.0  # both zero vectors → identical
    return float(np.dot(a, b) / denom)


class LSTMProcessor:
    """
    Lightweight LSTM-based sequence processor for encrypted byte streams.

    Usage
    -----
    processor = LSTMProcessor()
    features  = processor.process_sequence(encrypted_bytes)  # encode side
    is_valid  = processor.validate_sequence(extracted_bytes, stored_features)  # decode side
    """

    def __init__(self):
        self._model = None          # loaded lazily
        self._model_available = False

    # ── Model management ───────────────────────────────────────────────────────

    def _load_model(self) -> bool:
        """
        Attempt to load the pre-trained Keras LSTM model.
        Returns True if successfully loaded, False otherwise.
        """
        if self._model is not None:
            return self._model_available

        if not os.path.exists(_MODEL_PATH):
            logger.warning(
                "LSTM model not found at %s. "
                "Run training/train_lstm.py to train it. "
                "LSTM validation will be skipped.",
                _MODEL_PATH
            )
            self._model_available = False
            return False

        try:
            import tensorflow as tf  # imported lazily to avoid startup cost
            self._model = tf.keras.models.load_model(_MODEL_PATH)
            self._model_available = True
            logger.info("LSTM model loaded from %s", _MODEL_PATH)
            return True
        except Exception as exc:
            logger.warning("Failed to load LSTM model: %s", exc)
            self._model_available = False
            return False

    @property
    def is_available(self) -> bool:
        """True if the LSTM model is loaded and ready."""
        return self._load_model()

    # ── Sequence helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _bytes_to_windows(data: bytes, seq_len: int = SEQUENCE_LENGTH) -> np.ndarray:
        """
        Convert raw bytes into overlapping windows for LSTM input.

        Input sequence:  N bytes
        Output shape:    (num_windows, seq_len, 1)   — floats in [0, 1]

        Each byte value is normalised to [0, 1] by dividing by 255.
        """
        # Pad to a multiple of seq_len with zeros
        remainder = len(data) % seq_len
        if remainder:
            data = data + b'\x00' * (seq_len - remainder)

        arr = np.frombuffer(data, dtype=np.uint8).astype(np.float32) / 255.0
        num_windows = len(arr) // seq_len
        # Reshape: (num_windows, seq_len, 1)
        windows = arr[:num_windows * seq_len].reshape(num_windows, seq_len, 1)
        return windows

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_sequence(self, encrypted_bytes: bytes) -> Optional[list]:
        """
        ENCODE side — run the LSTM encoder on the encrypted byte stream.

        Args:
            encrypted_bytes: Raw AES-encrypted bytes.

        Returns:
            A list of floats (feature vector) if the model is available,
            or None if the model is unavailable (processing is skipped gracefully).

        Pipeline:
            bytes → normalised windows → Bidirectional LSTM → feature vector
        """
        if not self._load_model():
            logger.info("LSTM model unavailable — skipping sequence processing.")
            return None

        try:
            windows = self._bytes_to_windows(encrypted_bytes)
            if len(windows) == 0:
                return None

            # The model processes each window independently; we take the mean
            # of all window feature vectors as the aggregate representation.
            # Shape: (num_windows, FEATURE_DIM)
            window_features = self._model.predict(windows, verbose=0)

            # Aggregate: mean pooling across windows → (FEATURE_DIM,)
            aggregated = np.mean(window_features, axis=0)

            logger.debug(
                "LSTM sequence processing complete. Feature norm=%.4f",
                np.linalg.norm(aggregated)
            )
            return aggregated.tolist()

        except Exception as exc:
            logger.warning("LSTM process_sequence error: %s", exc)
            return None

    def encode_sequence(self, encrypted_bytes: bytes) -> dict:
        """
        Alias / wrapper used during the encoding pipeline.

        Returns a dict with:
            'features'  — list of floats or None
            'available' — bool, whether the LSTM was applied
            'seq_len'   — number of windows processed
        """
        windows = self._bytes_to_windows(encrypted_bytes)
        features = self.process_sequence(encrypted_bytes)
        return {
            'features': features,
            'available': features is not None,
            'seq_len': len(windows),
        }

    def decode_sequence(
        self,
        extracted_bytes: bytes,
        stored_features: Optional[list],
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> dict:
        """
        DECODE side — validate the extracted byte sequence against stored features.

        Args:
            extracted_bytes: Bytes extracted from stego images via LSB.
            stored_features: Feature vector produced during encoding (list of floats).
            threshold:       Minimum cosine similarity to pass validation.

        Returns:
            dict with:
                'valid'       — bool
                'similarity'  — float or None
                'threshold'   — float
                'skipped'     — bool (True when LSTM model is unavailable)

        Sequential processing:
            extracted_bytes → normalised windows → LSTM → current features
            cosine_similarity(current_features, stored_features) ≥ threshold → PASS
        """
        # If stored features are unavailable (legacy message or model was absent
        # during encoding), skip validation gracefully.
        if stored_features is None:
            return {'valid': True, 'similarity': None, 'threshold': threshold, 'skipped': True}

        if not self._load_model():
            return {'valid': True, 'similarity': None, 'threshold': threshold, 'skipped': True}

        try:
            current_features = self.process_sequence(extracted_bytes)
            if current_features is None:
                return {'valid': True, 'similarity': None, 'threshold': threshold, 'skipped': True}

            stored = np.array(stored_features, dtype=np.float64)
            current = np.array(current_features, dtype=np.float64)
            similarity = _cosine_similarity(stored, current)

            valid = similarity >= threshold
            logger.info(
                "LSTM sequence validation: similarity=%.4f threshold=%.2f valid=%s",
                similarity, threshold, valid
            )
            return {
                'valid': valid,
                'similarity': round(similarity, 4),
                'threshold': threshold,
                'skipped': False,
            }

        except Exception as exc:
            logger.warning("LSTM decode_sequence error: %s", exc)
            # On error, skip rather than block decryption (fail-open for LSTM only)
            return {'valid': True, 'similarity': None, 'threshold': threshold, 'skipped': True}


# ── Module-level singleton ─────────────────────────────────────────────────────
# One instance per process — the Keras model is only loaded once.
lstm_processor = LSTMProcessor()
