from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import base64

key = bytes.fromhex('9b74c9798ee64d12849f25618a9b3dca')
iv = b'1234567890123456'  # Static IV for example, should be random in practice

def encrypt(plain_text):
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(plain_text.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted_data).decode()

# Example message
message = "This is a secret message"
encrypted_message = encrypt(message)
print(encrypted_message)
