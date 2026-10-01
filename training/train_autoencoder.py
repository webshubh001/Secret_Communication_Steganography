"""
training/train_autoencoder.py — Train the Convolutional Autoencoder
====================================================================

Trains a lightweight CNN autoencoder for image compression and reconstruction.

Architecture (Unit V — Convolutional Autoencoder):

    ENCODER:  Input(128×128×3)
              → Conv2D(32, 3×3, relu, padding=same)
              → MaxPooling(2×2)          → 64×64×32
              → Conv2D(16, 3×3, relu, padding=same)
              → MaxPooling(2×2)          → 32×32×16
              → Conv2D(8,  3×3, relu, padding=same, name='latent_space')
              → MaxPooling(2×2)          → 16×16×8   ← latent representation

    DECODER:  → Conv2D(8,  3×3, relu, padding=same)
              → UpSampling(2×2)          → 32×32×8
              → Conv2D(16, 3×3, relu, padding=same)
              → UpSampling(2×2)          → 64×64×16
              → Conv2D(32, 3×3, relu, padding=same)
              → UpSampling(2×2)          → 128×128×32
              → Conv2D(3,  3×3, sigmoid) → 128×128×3  ← reconstructed image

Training data: synthetic random images (no external dataset needed for demo).
For better results, replace with real cover images from uploads/covers/.

Usage
-----
    python training/train_autoencoder.py

Output
------
    models/autoencoder.keras

Requirements
------------
    tensorflow>=2.13   Pillow   numpy
"""

import os
import sys
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

TARGET_H = 128
TARGET_W = 128
CHANNELS = 3
MODEL_SAVE_PATH = os.path.join(PROJECT_ROOT, 'models', 'autoencoder.keras')

EPOCHS     = 20
BATCH_SIZE = 32
NUM_SAMPLES = 5_000   # synthetic images; replace with real images for better results


def build_autoencoder(h: int, w: int, c: int):
    """
    Build and return the full convolutional autoencoder.

    The 'latent_space' layer name is used by ConvAutoencoder._load_model()
    to extract the encoder sub-model.
    """
    import tensorflow as tf
    from tensorflow import keras

    inputs = keras.Input(shape=(h, w, c), name='image_input')

    # ── ENCODER ────────────────────────────────────────────────────────────────
    # Each Conv2D learns spatial filters:
    #   - Early layers: low-level features (edges, colours)
    #   - Later layers: high-level structure (textures, shapes)
    # MaxPooling reduces spatial dimensions (downsampling).

    x = keras.layers.Conv2D(32, (3, 3), activation='relu',
                            padding='same', name='enc_conv1')(inputs)
    x = keras.layers.MaxPooling2D((2, 2), name='enc_pool1')(x)          # 64×64

    x = keras.layers.Conv2D(16, (3, 3), activation='relu',
                            padding='same', name='enc_conv2')(x)
    x = keras.layers.MaxPooling2D((2, 2), name='enc_pool2')(x)          # 32×32

    # Latent layer — named so the encoder sub-model can be extracted
    x = keras.layers.Conv2D(8, (3, 3), activation='relu',
                            padding='same', name='latent_space')(x)
    latent = keras.layers.MaxPooling2D((2, 2), name='enc_pool3')(x)     # 16×16×8

    # ── DECODER ────────────────────────────────────────────────────────────────
    # UpSampling2D performs nearest-neighbour upsampling (no trainable params).
    # Conv2DTranspose (not used here) is an alternative with learned upsampling.

    x = keras.layers.Conv2D(8, (3, 3), activation='relu',
                            padding='same', name='dec_conv1')(latent)
    x = keras.layers.UpSampling2D((2, 2), name='dec_up1')(x)           # 32×32

    x = keras.layers.Conv2D(16, (3, 3), activation='relu',
                            padding='same', name='dec_conv2')(x)
    x = keras.layers.UpSampling2D((2, 2), name='dec_up2')(x)           # 64×64

    x = keras.layers.Conv2D(32, (3, 3), activation='relu',
                            padding='same', name='dec_conv3')(x)
    x = keras.layers.UpSampling2D((2, 2), name='dec_up3')(x)           # 128×128

    # Sigmoid output: pixel values in [0, 1]
    outputs = keras.layers.Conv2D(c, (3, 3), activation='sigmoid',
                                  padding='same', name='reconstruction')(x)

    autoencoder = keras.Model(inputs=inputs, outputs=outputs, name='conv_autoencoder')
    autoencoder.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return autoencoder


def load_real_covers(covers_dir: str, target_h: int, target_w: int):
    """Optionally load real cover images for better training quality."""
    from PIL import Image

    images = []
    if os.path.isdir(covers_dir):
        for fname in os.listdir(covers_dir):
            if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                try:
                    img = Image.open(os.path.join(covers_dir, fname)).convert('RGB')
                    img = img.resize((target_w, target_h))
                    images.append(np.array(img, dtype=np.float32) / 255.0)
                except Exception:
                    pass

    if images:
        print(f"Loaded {len(images)} real cover images from {covers_dir}")
    return images


def generate_synthetic_data(n: int, h: int, w: int, c: int):
    print(f"Generating {n} synthetic images ({h}×{w}×{c})...")
    return np.random.rand(n, h, w, c).astype(np.float32)


def main():
    try:
        import tensorflow as tf
        print(f"TensorFlow version: {tf.__version__}")
    except ImportError:
        print("ERROR: TensorFlow is not installed.")
        print("Install with:  pip install tensorflow")
        sys.exit(1)

    print("\n=== Convolutional Autoencoder Training (Unit V) ===")
    print(f"  Input size  : {TARGET_H}×{TARGET_W}×{CHANNELS}")
    print(f"  Epochs      : {EPOCHS}")
    print(f"  Batch size  : {BATCH_SIZE}")

    ae = build_autoencoder(TARGET_H, TARGET_W, CHANNELS)
    ae.summary()

    # Try to use real cover images first, fall back to synthetic
    covers_dir = os.path.join(PROJECT_ROOT, 'uploads', 'covers')
    real_images = load_real_covers(covers_dir, TARGET_H, TARGET_W)

    if real_images:
        X = np.stack(real_images)
        # Augment with synthetic if too few real images
        if len(X) < NUM_SAMPLES:
            synth = generate_synthetic_data(NUM_SAMPLES - len(X), TARGET_H, TARGET_W, CHANNELS)
            X = np.concatenate([X, synth], axis=0)
    else:
        X = generate_synthetic_data(NUM_SAMPLES, TARGET_H, TARGET_W, CHANNELS)

    print(f"\nTraining on {len(X)} images...")
    history = ae.fit(
        X, X,   # target = input (reconstruction)
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=0.1,
        verbose=1,
    )

    os.makedirs(os.path.dirname(MODEL_SAVE_PATH), exist_ok=True)
    ae.save(MODEL_SAVE_PATH)
    print(f"\nAutoencoder saved to: {MODEL_SAVE_PATH}")

    final_loss = history.history['val_loss'][-1]
    print(f"Final validation loss (MSE): {final_loss:.6f}")
    print("\nDone. Autoencoder will be loaded automatically by the Flask app.")


if __name__ == '__main__':
    main()
