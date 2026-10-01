# Secret Communication System v2

A secure steganographic communication system built with Flask that hides encrypted secret messages inside images using LSB steganography, protected by dual-sided face biometric authentication, AES-256-CBC encryption, SHA-256 integrity verification, and academic AI modules (LSTM — Unit IV, Convolutional Autoencoder — Unit V).

---

## System Architecture (v2)

```
                        ┌─────────────────────────────┐
                        │           SENDER             │
                        └────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │     1. Select Receiver            │
                    │     2. Validate receiver face     │
                    │        profile exists             │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   3. Enter Secret Message/File    │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   4. AES-256-CBC Encryption       │
                    │      (random 256-bit session key) │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   5. LSTM Sequence Processing     │
                    │      [Unit IV]                    │
                    │   Encrypted bytes → LSTM encoder  │
                    │   → 8-D feature vector            │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   6. SHA-256 Integrity Hash       │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   7. Convolutional Autoencoder    │
                    │      [Unit V]                     │
                    │   Cover image → Encoder →         │
                    │   Latent representation →         │
                    │   Decoder → Reconstruction loss   │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   8. Data Split (N chunks)        │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   9. LSB Steganography            │
                    │   (1 chunk per cover image)       │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  10. Store DB record              │
                    │      sender_id, receiver_id,      │
                    │      sender_face_profile_id,      │
                    │      receiver_face_profile_id     │
                    └────────────────┬────────────────┘
                                     │
                              Stego Images ZIP
                                     │
                        ┌────────────▼────────────────┐
                        │          RECEIVER            │
                        └────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Step 1: Upload stego images      │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Step 2: Receiver Face Auth       │
                    │  (existing session mechanism)     │
                    └──────┬─────────────────┬────────┘
                         FAIL               PASS
                           │                 │
                        DENY                 │
                                ┌────────────▼────────────┐
                                │  Step 3: Sender Face     │
                                │  Verification            │
                                │  Upload sender photo →   │
                                │  Compare vs. DB profile  │
                                └──────┬──────────┬───────┘
                                     FAIL        PASS
                                       │           │
                              "Sender face       Step 4:
                              verification    SHA-256 Verify
                              failed. Access       │
                               denied."           Step 5:
                                               LSTM Validate
                                                   │
                                               Step 6:
                                               AES Decrypt
                                                   │
                                           Secret Message
```

---

## Features

| Feature | Status |
|---------|--------|
| User registration / login | ✅ Existing |
| Face registration (128-d dlib embedding) | ✅ Existing |
| Face authentication gate | ✅ Existing |
| AES-256-CBC encryption | ✅ Existing |
| SHA-256 integrity verification | ✅ Existing |
| Multi-image LSB steganography | ✅ Existing |
| MSE / PSNR / SSIM metrics | ✅ Existing |
| Receiver selection at sender | ✅ **v2 New** |
| Sender face verification at receiver | ✅ **v2 New** |
| Dual-sided identity verification | ✅ **v2 New** |
| LSTM sequence processing (Unit IV) | ✅ **v2 New** |
| Convolutional Autoencoder (Unit V) | ✅ **v2 New** |
| Backward-compatible legacy messages | ✅ **v2 New** |

---

## Sender Workflow

1. Log in → navigate to **Encode**
2. **Register your face** (if not done) at `/face/register`
3. **Select receiver** from the dropdown (only users with registered faces appear)
4. Upload 2–5 cover images
5. Enter secret message or upload a file
6. Click **Encode & Download ZIP**
7. Send all stego images from the ZIP to the receiver

## Receiver Workflow

1. Log in → navigate to `/face/authenticate` to complete **receiver face auth**
2. Navigate to **Decode**
3. Upload all stego images from the session
4. Upload a photo of the expected **sender's face** (for sender verification)
5. Click **Verify & Decrypt Secret**
6. If both authentications pass → view the secret message

---

## Face Authentication Workflow

### Receiver Authentication (Step 2)
- Receiver uploads their own photo at `/face/authenticate`
- System compares it against the stored 128-d dlib embedding in the DB
- Sets `session['face_authenticated'] = True` on success
- The decode route checks this flag before processing

### Sender Verification (Step 3)
- During **encoding**, sender's `FaceProfile.id` is stored in `secret_messages.sender_face_profile_id`
- During **decoding**, receiver uploads a photo of the sender
- System loads sender's stored embedding from DB and calls `verify_face()`
- If distance ≤ threshold (default 0.6): **PASS**; else: **DENY** — message is never decrypted
- Raw face images are not stored; only the 128-d float embedding

### Security Properties
- No raw face photographs are stored permanently
- Face embeddings are not exposed in API responses or Flask logs
- Sender/receiver IDs are validated server-side — never trusted from browser input
- Failed authentication attempts are logged (without biometric distance values)

---

## Unit IV — LSTM (Long Short-Term Memory)

**File:** `modules/lstm_processor.py`

### Concept
An LSTM is a Recurrent Neural Network that maintains two state vectors:
- **h_t** (hidden state) — short-term memory / output at each timestep
- **c_t** (cell state) — long-term memory that persists across timesteps

Four gates control information flow at each timestep t:
```
Forget gate:  f_t = σ(W_f · [h_{t-1}, x_t] + b_f)
Input gate:   i_t = σ(W_i · [h_{t-1}, x_t] + b_i)
Cell update:  g_t = tanh(W_g · [h_{t-1}, x_t] + b_g)
Output gate:  o_t = σ(W_o · [h_{t-1}, x_t] + b_o)

c_t = f_t ⊙ c_{t-1}  +  i_t ⊙ g_t
h_t = o_t ⊙ tanh(c_t)
```

### Integration
```
AES-encrypted bytes
        ↓
Reshape into 64-byte windows → normalise to [0,1]
        ↓
Bidirectional LSTM(32 units) — processes forward + backward
        ↓
Mean-pool across windows → 8-D feature vector
        ↓
[stored as metadata — used for validation at decode side]

At decode:
extracted bytes → same pipeline → compare via cosine similarity
if similarity ≥ 0.90 → PASS (additional integrity check)
```

### Model Architecture
```
Input (64, 1) → Bidirectional LSTM(32) → Dense(8, relu) → features (8,)
```

---

## Unit V — Convolutional Autoencoder

**File:** `modules/autoencoder.py`

### Concept
A Convolutional Autoencoder learns to compress images into a compact latent space and reconstruct them. It consists of:
- **Encoder:** Conv2D layers + MaxPooling to reduce spatial dimensions
- **Latent representation:** Compressed bottleneck (16×16×8 for 128×128 input)
- **Decoder:** Conv2D layers + UpSampling to reconstruct original resolution

### Architecture
```
Input 128×128×3
      ↓
Conv2D(32, 3×3, relu) → MaxPool(2×2) → 64×64×32
      ↓
Conv2D(16, 3×3, relu) → MaxPool(2×2) → 32×32×16
      ↓
Conv2D(8,  3×3, relu) → MaxPool(2×2) → 16×16×8  ← Latent space
      ↓
Conv2D(8,  3×3, relu) → UpSample(2×2) → 32×32×8
      ↓
Conv2D(16, 3×3, relu) → UpSample(2×2) → 64×64×16
      ↓
Conv2D(32, 3×3, relu) → UpSample(2×2) → 128×128×32
      ↓
Conv2D(3,  3×3, sigmoid)               → 128×128×3  ← Reconstructed image
```

### Integration
- Applied **around** the existing LSB pipeline (does not replace it)
- Each cover image passes through the autoencoder during encoding
- **Reconstruction loss** (pixel-level MSE) is stored in `stego_images.ae_reconstruction_loss`
- Displayed alongside MSE/PSNR/SSIM in the result page

---

## Installation

```bash
# 1. Clone and navigate
cd "Workshop Project"

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
copy .env.example .env
# Edit .env — set SECRET_KEY and MASTER_SECRET

# 5. Initialise / migrate database
python init_db.py
```

## Model Training (Unit IV + V)

```bash
# Train LSTM encoder (Unit IV) — ~2 minutes on CPU
python training/train_lstm.py

# Train Convolutional Autoencoder (Unit V) — ~5 minutes on CPU
# Optionally put cover images in uploads/covers/ for better quality
python training/train_autoencoder.py

# Models are saved to:
#   models/lstm_model.keras
#   models/autoencoder.keras
```

> **Note:** The application runs without trained models — LSTM and autoencoder steps are gracefully skipped with a logged warning. Train the models for full functionality.

## Running the Application

```bash
python app.py
# Open: http://localhost:5000
```

## Testing

```bash
pytest tests/test_system.py -v
# Expected: 25 passed
```

---

## Database Schema (v2)

```
secret_messages
├── id, message_id, sender_id (existing)
├── receiver_id ───────────────── FK → users.id          [NEW v2]
├── sender_face_profile_id ────── FK → face_profiles.id  [NEW v2]
├── receiver_face_profile_id ──── FK → face_profiles.id  [NEW v2]
├── encrypted_aes_key, data_hash, total_chunks (existing)
└── status, created_at, decoded_at (existing)

stego_images
├── id, message_id, chunk_index (existing)
├── file_path, file_hash, chunk_hash (existing)
├── mse, psnr, ssim (existing)
└── ae_reconstruction_loss ──────────────────────────── [NEW v2]
```

Legacy messages (created before v2) have `receiver_id = NULL`. They are detected via `message.is_legacy` and handled gracefully — sender verification step is skipped with a clear warning.

---

## Limitations

1. **LSTM features** are currently not persisted in the DB — validation compares extracted bytes against themselves (self-validation). To enable cross-session comparison, add a `lstm_features` TEXT column to `secret_messages`.
2. **Autoencoder** is trained on synthetic random images by default. Using real cover images produces better reconstruction quality metrics.
3. **Face recognition** requires dlib's shape predictor models; performance varies with lighting and image quality.
4. **SQLite** is used for development. For production, use PostgreSQL.
5. The LSTM and autoencoder models must be trained before first use for full pipeline activation.

---

## Modified Files (v2)

| File | Change |
|------|--------|
| `models/message.py` | Added `receiver_id`, `sender/receiver_face_profile_id`, `ae_reconstruction_loss` |
| `models/user.py` | Added `received_messages` relationship |
| `routes/encode.py` | Receiver validation, LSTM processing, AE analysis, receiver API endpoints |
| `routes/decode.py` | Dual face verification (receiver + sender), LSTM validation |
| `templates/encode.html` | Receiver dropdown, status indicators, live validation |
| `templates/decode.html` | 6-step pipeline UI, sender face upload |
| `templates/result.html` | Sender verification badge, LSTM metrics, AE loss display |
| `requirements.txt` | Added `tensorflow>=2.13.0` |
| `init_db.py` | v2 column migration (safe for existing DBs) |

## New Files (v2)

| File | Purpose |
|------|---------|
| `modules/lstm_processor.py` | LSTM sequence encoder/validator (Unit IV) |
| `modules/autoencoder.py` | Convolutional autoencoder (Unit V) |
| `training/train_lstm.py` | LSTM training script |
| `training/train_autoencoder.py` | Autoencoder training script |
| `tests/test_system.py` | 25-test integration suite |
