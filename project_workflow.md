# SecretVault: Multi-Image Steganography & Face Recognition - Project Workflow

## 1. Executive Summary
**SecretVault** is a cutting-edge web application designed for highly secure secret communication. It combines Artificial Intelligence, Cybersecurity, and Image Processing to ensure that sensitive data remains confidential. Unlike traditional steganography, which hides data in a single image (making it vulnerable if that one image is intercepted), SecretVault encrypts the data, splits it across multiple images, and gates access to decode it behind live biometric face authentication.

## 2. Security Pipeline (The 6-Layer Architecture)
The project utilizes a robust 6-layer security pipeline to protect the payload:
1. **AES-256 Encryption:** The secret message or file is encrypted using an Advanced Encryption Standard (AES) with a 256-bit key in CBC mode.
2. **SHA-256 Integrity Hashing:** Each chunk of data and the full payload is hashed to detect any tampering or corruption.
3. **Data Splitting:** The encrypted ciphertext is split across multiple chunks.
4. **Multi-Image LSB Steganography:** Each chunk is embedded into separate cover images using Least Significant Bit (LSB) steganography.
5. **Face Recognition Authentication:** Access to decode the message requires live face authentication using 128-dimensional dlib embeddings.
6. **Data Reconstruction & Decryption:** The chunks are reassembled, verified for integrity, and decrypted back to the original secret.

---

## 3. Detailed Workflow

### Phase 1: User Registration & Onboarding
1. **Account Creation:** A user registers on the platform, providing basic credentials (username, password).
2. **Face Registration:** The user sets up their biometric profile. They can either upload a clear photo or use their live webcam via the browser. The system processes the image using the `face_recognition` (dlib) library, generating a 128-D mathematical embedding vector. 
   > **Note on Privacy:** Raw face images are **never stored**; only the mathematical representation (vector) is saved in the database to ensure maximum privacy and security.

### Phase 2: Encoding (Sender Workflow)
When a user wants to send a secure message:
1. **Upload Cover Images:** The sender uploads one or more innocent-looking images (cover images) that will act as the carrier for the secret.
2. **Input Secret:** The sender inputs the secret text message or uploads a secret file.
3. **Encryption:** The system encrypts the secret using AES-256-CBC, generating a secure ciphertext.
4. **Data Splitting & Hashing:** The ciphertext is divided into $N$ chunks (matching the number of uploaded cover images). A SHA-256 hash is generated for each chunk and the overall payload.
5. **Steganography (LSB Embedding):** Each chunk is invisibly embedded into a corresponding cover image by slightly altering the Least Significant Bits of the pixel data. 
6. **Download & Share:** The sender downloads the generated "Stego Images" (which visually look identical to the originals) and shares them with the intended receiver through any standard channel (email, chat, etc.).
7. **Quality Metrics Check:** The system calculates Image Quality Metrics (MSE, PSNR, SSIM) internally to guarantee that the stego images are visually indistinguishable from the cover images.

### Phase 3: Decoding (Receiver Workflow)
When a receiver receives the stego images and wants to read the secret:
1. **Authentication Gate:** The receiver logs into the system. Before accessing the decoding tool, they must pass a live **Face Authentication** check. The system captures their face via webcam (or upload) and calculates the Euclidean distance between the new 128-D embedding and the registered profile embedding.
2. **Upload Stego Images:** Once biometrically authenticated, the receiver uploads the received stego images to the platform.
3. **Extraction:** The system extracts the hidden LSB data (raw bytes) from each of the uploaded images.
4. **Reconstruction & Integrity Check:** The system reassembles the chunks into the full ciphertext payload. It computes the SHA-256 hash and compares it with the embedded hash. If any image was modified, compressed, or corrupted during transit, the hashes will mismatch, and the system will instantly alert the user of tampering.
5. **Decryption:** If the integrity is fully verified, the system decrypts the ciphertext using the recovered AES key.
6. **Reveal Secret:** The original secret message or file is finally revealed to the authenticated receiver.

---

## 4. Technology Stack
The application is built on a modern, robust technology stack:
- **Backend Core:** Python 3.10+, Flask Web Framework
- **Database:** SQLite (managed via Flask-SQLAlchemy ORM)
- **Face Recognition AI:** OpenCV, `dlib`, `face_recognition`
- **Cryptography:** AES-256 (PyCryptodome), SHA-256
- **Frontend Design:** HTML, CSS (Glassmorphism Dark UI for a premium cybersecurity aesthetic), Vanilla JS, WebRTC for live webcam integration.

## 5. Security & Audit Logging
To maintain compliance and track potential breaches, the system features comprehensive audit logging:
- **Authentication Logs:** Records every login and face authentication attempt (success/failure), including timestamps and IP addresses.
- **Activity Logs:** Tracks when users encode or decode messages.
- **Rate Limiting:** Protects the endpoints from brute-force and DDoS attacks by limiting authentication attempts (e.g., max 5 face auth attempts per minute).

## 6. Business Value & Conclusion
This architecture represents a **Zero-Trust model** for secure communication. If an attacker intercepts the stego images, they cannot read the message because:
1. The data is spread across multiple files (they need the entire set).
2. The data is AES-256 encrypted (they need the encryption key).
3. The decoding portal requires the authorized user's live biometric face data.

SecretVault significantly raises the barrier against data interception, providing a reliable, enterprise-grade solution for protecting highly sensitive information.
