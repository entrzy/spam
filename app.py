from flask import Flask, request, jsonify
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
import uuid
import base64

app = Flask(__name__)

# Hardcoded AES key (ensure to handle keys securely in production)
aes_key = bytes.fromhex('9b74c9798ee64d12849f25618a9b3dca')
iv = b'1234567890123456'  # IV should be random in production

@app.route('/normal', methods=['POST'])
def normal():
    try:
        data = request.get_json()
        # Add a UUID for tracing
        data['header']['subHeader']['requestUUID'] = str(uuid.uuid4())
        return jsonify({"responseBody": data}), 200
    except Exception as e:
        return jsonify({"response": {"error": {"errorCode": "500", "message": str(e)}}}), 500

@app.route('/encrypted', methods=['POST'])
def encrypted():
    try:
        data = request.get_json()
        encrypted_data = data['encryptedBody']
        # Decrypt the data
        decrypted_data = decrypt(encrypted_data)
        
        # Assume the decrypted data is JSON
        processed_data = jsonify(decrypted_data)
        
        # Encrypt the response body
        encrypted_response = encrypt(processed_data.get_data().decode())

        return jsonify({"encryptedResponseBody": encrypted_response}), 200
    except Exception as e:
        return jsonify({"response": {"error": {"errorCode": "500", "message": str(e)}}}), 500

def encrypt(plain_text):
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(plain_text.encode()) + padder.finalize()
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted_data).decode()

def decrypt(encrypted_text):
    encrypted_data = base64.b64decode(encrypted_text)
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    return decrypted_data.decode()

if __name__ == '__main__':
    app.run(port=18090)
