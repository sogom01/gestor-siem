"""
Imprime las claves RSA en formato de variable de entorno para Railway.
Uso: python export_keys_env.py
Luego pega el output en Railway > Variables.
"""
import sys

try:
    with open("keys/private.pem") as f:
        priv = f.read().replace("\n", "\\n")
    with open("keys/public.pem") as f:
        pub = f.read().replace("\n", "\\n")

    print("Copia estas variables en Railway > tu servicio > Variables:\n")
    print(f"JWT_PRIVATE_KEY={priv}\n")
    print(f"JWT_PUBLIC_KEY={pub}\n")
except FileNotFoundError:
    print("ERROR: Ejecuta primero: python generate_keys.py")
    sys.exit(1)
