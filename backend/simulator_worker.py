"""
Simulador de eventos para Railway (worker continuo).
Se ejecuta como servicio separado apuntando al backend en prod.

Variables de entorno requeridas:
  SIEM_API_URL  — URL del backend (ej: https://gestor-siem-production.up.railway.app)
  SIEM_USERNAME — usuario con rol analyst o admin (default: admin)
  SIEM_PASSWORD — contraseña del usuario
  SIM_RATE      — eventos por segundo (default: 0.5)
"""
import asyncio
import os
import random
import sys
from datetime import datetime, timezone
import httpx

# ── Config desde variables de entorno ─────────────────────────────────
BASE_URL  = os.environ.get("SIEM_API_URL", "http://127.0.0.1:8000")
USERNAME  = os.environ.get("SIEM_USERNAME", "admin")
PASSWORD  = os.environ.get("SIEM_PASSWORD", "Admin1234!")
RATE      = float(os.environ.get("SIM_RATE", "0.5"))  # ev/s (0.5 = 1 cada 2s)

# ── Pool de eventos ────────────────────────────────────────────────────
NORMAL_EVENTS = [
    ("INFO",  "web-server-01",  "GET /api/v1/products 200 {ms}ms"),
    ("INFO",  "web-server-01",  "POST /api/v1/orders 201 {ms}ms"),
    ("INFO",  "db-primary",     "DB query executed in {ms}ms rows={rows}"),
    ("INFO",  "worker-01",      "Worker job processed: task-id-{id}"),
    ("INFO",  "monitoring",     "Health check OK /api/health 200"),
    ("INFO",  "cache-01",       "Cache HIT ratio: {ratio}%"),
    ("WARN",  "proxy-edge",     "Rate limit approaching: {n}/500 req/min from {ip}"),
    ("WARN",  "db-primary",     "DB connection pool at {pct}% capacity"),
    ("WARN",  "auth-service",   "Token expiration in < 5 minutes for agent-{id}"),
    ("ERROR", "auth-service",   "Failed login attempt: user=root src={ip}"),
    ("ERROR", "auth-service",   "Failed login attempt: user=admin src={ip}"),
    ("ERROR", "web-server-01",  "JWT validation failed: expired token from {ip}"),
]

ATTACK_EVENTS = [
    ("ERROR", "auth-service",  "Failed login attempt: user=root src=185.220.101.47"),
    ("ERROR", "auth-service",  "Failed login attempt: user=admin src=185.220.101.47"),
    ("CRIT",  "auth-service",  "BRUTE FORCE DETECTED: 347 failures in 240s src=185.220.101.47"),
    ("WARN",  "proxy-edge",    "SYN packet to closed port 22 from 91.108.4.38"),
    ("ERROR", "proxy-edge",    "Port scan detected: 1240 ports in 60s from 91.108.4.38"),
    ("ERROR", "db-primary",    "WAF blocked SQLi attempt from 103.21.244.0"),
    ("CRIT",  "web-server-01", "SQL INJECTION attempt blocked: 103.21.244.0 target=/api/users"),
]

IPS = ["185.220.101.47", "91.108.4.38", "10.0.1.22", "10.0.2.15", "198.54.117.200"]


def build(template: str) -> str:
    return (template
        .replace("{ms}",    str(random.randint(2, 890)))
        .replace("{rows}",  str(random.randint(1, 5000)))
        .replace("{id}",    str(random.randint(1000, 9999)))
        .replace("{ratio}", str(random.randint(60, 98)))
        .replace("{n}",     str(random.randint(200, 490)))
        .replace("{pct}",   str(random.randint(40, 92)))
        .replace("{ip}",    random.choice(IPS))
    )


async def login(client: httpx.AsyncClient) -> str:
    for attempt in range(5):
        try:
            r = await client.post(
                f"{BASE_URL}/api/v1/auth/token",
                json={"username": USERNAME, "password": PASSWORD},
                timeout=10.0,
            )
            r.raise_for_status()
            token = r.json()["access_token"]
            print(f"[SIM] Login OK — token obtenido", flush=True)
            return token
        except Exception as e:
            wait = 10 * (attempt + 1)
            print(f"[SIM] Login fallido ({e}) — reintento en {wait}s", flush=True)
            await asyncio.sleep(wait)
    print("[SIM] No se pudo autenticar. Saliendo.", flush=True)
    sys.exit(1)


async def send(client: httpx.AsyncClient, token: str, sev: str, host: str, msg: str) -> bool:
    try:
        r = await client.post(
            f"{BASE_URL}/api/v1/events/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"severity": sev, "host": host, "message": msg,
                  "source_ip": random.choice(IPS)},
            timeout=8.0,
        )
        return r.status_code == 201
    except Exception:
        return False


async def main():
    print(f"[SIM] Iniciando worker — {BASE_URL} @ {RATE} ev/s", flush=True)
    interval = 1.0 / RATE
    attack_counter = 0

    async with httpx.AsyncClient() as client:
        token = await login(client)
        token_refresh = 0

        while True:
            # Refrescar token cada 50 minutos
            token_refresh += 1
            if token_refresh > int(3000 * RATE):
                token = await login(client)
                token_refresh = 0

            # Cada ~60 eventos lanzar un ataque
            attack_counter += 1
            if attack_counter >= random.randint(55, 75):
                attack_counter = 0
                sev, host, tmpl = random.choice(ATTACK_EVENTS)
            else:
                sev, host, tmpl = random.choice(NORMAL_EVENTS)

            msg = build(tmpl)
            ok = await send(client, token, sev, host, msg)

            now = datetime.now(timezone.utc).strftime("%H:%M:%S")
            status = "OK" if ok else "FAIL"
            print(f"[{now}] {status} [{sev}] {host}: {msg[:60]}", flush=True)

            await asyncio.sleep(interval + random.uniform(-0.1, 0.3))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[SIM] Detenido.", flush=True)
