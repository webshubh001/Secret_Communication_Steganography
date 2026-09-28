# 🔐 SecretVault — Multi-Image Steganography & Face Recognition

> **MCA Final Year Workshop Project** | Domain: AI + Cybersecurity + Image Processing

A full-stack secure communication web app that hides AES-encrypted messages inside multiple cover images (steganography) and gates decoding behind live **face authentication**.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-green)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-Academic-lightgrey)](#-license)

---

## 📌 Project Overview

Traditional image steganography hides secret information inside a **single** image. If that image is intercepted, the entire secret is exposed.

**SecretVault** improves on this by:

1. 🔒 **AES-256-CBC encrypting** the secret message/file
2. ✂️ **Splitting** the ciphertext across multiple images
3. 🖼️ **Embedding** each chunk via LSB steganography into cover images
4. 👤 **Gating decoding** behind live face authentication (128-D dlib embeddings)
5. 🔓 Reconstructing, verifying integrity, and **decrypting** only after auth passes

---

## ✨ Key Features

| Feature | Details |
|---------|---------|
| 🔐 AES-256-CBC Encryption | Per-session keys, master-secret-protected |
| 🖼️ Multi-Image LSB Steganography | Data split across 1–N cover images |
| 👤 Face Registration & Auth | Live webcam capture or photo upload; dlib 128-D embeddings |
| 🛡️ Integrity Verification | SHA-256 per-chunk + full-payload hash |
| 📊 Image Quality Metrics | MSE, PSNR, SSIM computed after encoding |
| 📜 Security Audit Logs | Auth attempts, encode/decode events, IP, timestamps |
| ⚡ Rate Limiting | Flask-Limiter on login, register, face-auth endpoints |
| 🌐 Responsive Dark UI | Glassmorphism design, webcam tab on all face pages |

---

## 🏗️ System Architecture

```
                    ┌───────────────────┐
                    │       Sender      │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Secret Message  │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │  AES-256-CBC Enc  │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Data Splitting  │  ← SHA-256 per chunk
                    └─────────┬─────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                 Image 1   Image 2   Image N
                 (LSB)     (LSB)     (LSB)
                    └─────────┼─────────┘
                              ▼
                    ┌───────────────────┐
                    │   Stego Images    │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │     Receiver      │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Face Auth (dlib)  │
                    └────────┬──────────┘
                         ┌───┴───┐
                       FAIL     PASS
                         │         │
                       DENY    Extract → Reconstruct → Verify → Decrypt
                                                                   │
                                                          Original Message
```

---

## 🔄 System Workflow

### Sender Workflow
```
Register / Login  →  Upload Cover Images  →  Enter Secret Message/File
       ↓
   AES-256 Encrypt  →  Split into N chunks  →  LSB embed into N images
       ↓
   Download Stego Images  →  Share with receiver
```

### Receiver Workflow
```
Login  →  Face Authentication (webcam or photo)
       ↓
   Upload Stego Images  →  LSB Extract chunks  →  Reconstruct payload
       ↓
   Verify SHA-256 hashes  →  AES Decrypt  →  View / Download secret
```

---

## 📁 Project Structure

```
Workshop Project/
│
├── app.py                    # Flask application factory
├── config.py                 # Configuration classes (dev/prod)
├── extensions.py             # Shared Flask extensions (limiter, login_manager)
├── init_db.py                # One-time DB initialisation script
├── requirements.txt
├── .env                      # Secret keys (not committed)
├── .env.example              # Template for .env
│
├── models/
│   ├── __init__.py           # db = SQLAlchemy()
│   ├── user.py               # User, FaceProfile models
│   ├── message.py            # SecretMessage, StegoImage models
│   └── logs.py               # AuthenticationLog, ActivityLog models
│
├── routes/
│   ├── auth.py               # /register  /login  /logout
│   ├── face.py               # /face/register  /face/authenticate
│   ├── encode.py             # /encode  — steganography encoding pipeline
│   ├── decode.py             # /decode  — steganography decoding pipeline
│   └── dashboard.py          # /dashboard  /profile  /history
│
├── modules/
│   ├── steganography.py      # LSB embed / extract
│   ├── encryption.py         # AES-256-CBC encrypt / decrypt
│   ├── face_authentication.py# dlib face embedding + verification
│   ├── data_splitter.py      # Split ciphertext into chunks
│   ├── data_reconstruction.py# Reconstruct + hash-verify chunks
│   ├── integrity.py          # SHA-256 helpers
│   └── image_metrics.py      # MSE, PSNR, SSIM computation
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html  /  register.html
│   ├── face_register.html    # Upload + Live Camera tabs
│   ├── face_auth.html        # Upload + Live Camera tabs
│   ├── encode.html
│   ├── decode.html
│   ├── dashboard.html
│   ├── history.html
│   ├── profile.html
│   ├── result.html
│   └── errors/  (404, 403, 413, 500)
│
├── static/
│   ├── css/style.css
│   └── js/script.js
│
└── database/
    └── app.db                # SQLite database (auto-created)
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 3.x |
| Database | SQLite via Flask-SQLAlchemy |
| Auth | Flask-Login, Werkzeug password hashing |
| Face Recognition | `face_recognition` (dlib), `dlib-bin` |
| Encryption | AES-256-CBC via `pycryptodome` |
| Image Processing | OpenCV, Pillow, NumPy |
| Image Metrics | scikit-image (SSIM), OpenCV (PSNR/MSE) |
| Rate Limiting | Flask-Limiter |
| CSRF Protection | Flask-WTF |
| Frontend | Vanilla HTML/CSS/JS, WebRTC (camera) |

---

## ⚙️ Installation

### Prerequisites
- Python 3.10 or higher
- Git
- **Windows**: `dlib` requires a pre-built binary (see Step 5)

### 1. Clone the Repository

```bash
git clone https://github.com/webshubh001/secret-communication.git
cd secret-communication
```

### 2. Create & Activate Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python -m venv venv
source venv/bin/activate
```

### 3. Install dlib (Windows — pre-built binary)

`dlib` requires Visual C++ to build from source on Windows. Use the pre-built wheel instead:

```bash
pip install dlib-bin
```

> On Linux/macOS, `pip install dlib` builds from source (requires cmake).

### 4. Install All Dependencies

```bash
pip install -r requirements.txt --no-deps face_recognition
pip install "git+https://github.com/ageitgey/face_recognition_models"
```

> **Note:** `face_recognition` is installed with `--no-deps` to avoid rebuilding `dlib` since `dlib-bin` already provides it.

### 5. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
MASTER_SECRET=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
FACE_RECOGNITION_THRESHOLD=0.6
FLASK_ENV=development
```

### 6. Initialise the Database

```bash
python init_db.py
```

This creates all 6 database tables: `users`, `face_profiles`, `secret_messages`, `stego_images`, `authentication_logs`, `activity_logs`.

---

## ▶️ Running the Application

```bash
python app.py
```

Open in your browser:

```
http://127.0.0.1:5000/
```

---

## 🔒 Security Pipeline

```
Secret Message / File
        ↓
  AES-256-CBC Encrypt  (random 256-bit key per session)
        ↓
  SHA-256 hash per chunk + full payload hash
        ↓
  Split into N chunks
        ↓
  LSB embed chunk i → Cover Image i  (for i = 1..N)
        ↓
  Stego Images  →  shared with receiver
        ↓
  Face Authentication  (dlib 128-D embedding, Euclidean distance < threshold)
        ↓
  LSB Extract raw bytes from each stego image
        ↓
  Reconstruct payload, verify all SHA-256 hashes
        ↓
  AES Decrypt using recovered key
        ↓
  Original Secret Message / File
```

---

## 📊 Image Quality Metrics

After encoding, the system computes:

| Metric | Meaning | Good Value |
|--------|---------|-----------|
| **MSE** | Mean Squared Error between cover and stego | Lower is better |
| **PSNR** | Peak Signal-to-Noise Ratio (dB) | > 40 dB is imperceptible |
| **SSIM** | Structural Similarity Index | Closer to 1.0 is better |

---

## 👤 Face Authentication Details

- Face images are **never stored** — only the 128-dimensional embedding vector is saved in the database
- Registration and authentication both support **live webcam capture** (via WebRTC) or file upload
- Distance threshold is configurable via `FACE_RECOGNITION_THRESHOLD` in `.env` (default `0.6`)
- Authentication events are rate-limited to **5 attempts per minute**

---

## 🚀 Future Enhancements

- 📱 Mobile app (Flutter/React Native)
- ☁️ Cloud storage for stego images (AWS S3 / Firebase)
- 🔑 RSA + AES hybrid encryption
- 🧬 Deep learning face recognition (FaceNet / ArcFace)
- ⏳ Self-expiring messages with TTL
- 🔗 Blockchain-based audit trail
- 📧 Secure email delivery of stego images
- 🧩 Reed-Solomon error correction for corrupted image parts

---

## 🎓 Academic Significance

This project integrates:

- **Artificial Intelligence** — Face recognition via dlib CNN
- **Machine Learning** — 128-D face embedding model
- **Computer Vision** — Image processing, steganography
- **Cryptography** — AES-256-CBC, SHA-256
- **Cybersecurity** — Rate limiting, CSRF, session management
- **Web Development** — Full-stack Flask application
- **Database** — SQLAlchemy ORM, SQLite

---

## 👨‍💻 Project Info

| | |
|-|-|
| **Type** | Academic Project — MCA Final Year Workshop |
| **Domain** | Artificial Intelligence + Cybersecurity + Image Processing |
| **Author** | Shubham |

---

## 📜 License

Developed for educational and research purposes.

---

## ⭐ Conclusion

**SecretVault** provides a multi-layer security mechanism for confidential communication. By combining **AES-256 encryption**, **multi-image LSB steganography**, **SHA-256 integrity verification**, and **face authentication**, the system provides substantially stronger protection than any single security technique in isolation.
