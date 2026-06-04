"""Genera par de claves RSA 2048 para JWT RS256."""
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

os.makedirs("keys", exist_ok=True)

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

with open("keys/private.pem", "wb") as f:
    f.write(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))

with open("keys/public.pem", "wb") as f:
    f.write(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

print("OK: keys/private.pem y keys/public.pem generados")
