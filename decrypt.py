from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import base64

# The AES key and IV must match those used for encryption
key = bytes.fromhex('9b74c9798ee64d12849f25618a9b3dca')
iv = b'1234567890123456'  # Remember to use the same IV for encryption and decryption for a given message

def decrypt(encrypted_text):
    try:
        encrypted_data = base64.b64decode(encrypted_text)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
        return decrypted_data.decode()
    except Exception as e:
        return f"Decryption failed: {str(e)}"

# Example usage
encrypted_message = "Eb/QABHkxM/P7V+/3mu9kq24iYIl4kjsimh8Nr8QW20="
decrypted_message = decrypt(encrypted_message)
print("Decrypted message:", decrypted_message)
