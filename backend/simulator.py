"""
SIEM Event Simulator
Bombea eventos realistas al backend para demostrar el dashboard en accion.
Uso: python simulator.py [--url http://localhost:8000] [--rate 2]
"""
import asyncio
import random
import argparse
import sys
import os
from datetime import datetime, timezone
import httpx

# Activar colores ANSI en Windows
if sys.platform == "win32":
    os.system("")

# ── Escenarios realistas ───────────────────────────────────────────────
HOSTS = [
    "web-server-01", "web-server-02", "db-primary", "db-replica",
    "auth-service",  "proxy-edge",    "worker-01",  "worker-02",
    "api-gateway-01","monitoring",    "cache-01",   "queue-01",
]

NORMAL_EVENTS = [
    ("INFO",  "GET /api/v1/products 200 {ms}ms",                        "web-server-01"),
    ("INFO",  "POST /api/v1/orders 201 {ms}ms",                         "web-server-01"),
    ("INFO",  "DB query executed in {ms}ms rows={rows}",                 "db-primary"),
    ("INFO",  "Worker job processed: task-id-{id}",                      "worker-01"),
    ("INFO",  "Health check OK /api/health 200",                         "monitoring"),
    ("INFO",  "Cache HIT ratio: {ratio}%",                               "cache-01"),
    ("INFO",  "Queue depth: {depth} messages",                           "queue-01"),
    ("INFO",  "TLS handshake completed for {ip}",                        "proxy-edge"),
    ("INFO",  "User session started: uid={id}",                          "auth-service"),
    ("WARN",  "Rate limit approaching: {n}/500 req/min from {ip}",       "proxy-edge"),
    ("WARN",  "DB connection pool at {pct}% capacity",                   "db-primary"),
    ("WARN",  "Response time elevated: {ms}ms avg (threshold: 500ms)",   "web-server-01"),
    ("WARN",  "Token expiration in < 5 minutes for agent-{id}",          "auth-service"),
    ("WARN",  "Disk usage at {pct}% on /var/log",                        "monitoring"),
]

ATTACK_SCENARIOS = {
    "brute_force": {
        "label": "BRUTE FORCE",
        "events": [
            ("ERROR", "Failed login attempt: user={user} src={ip}",     "auth-service"),
            ("ERROR", "Failed login attempt: user=root src={ip}",       "auth-service"),
            ("ERROR", "Failed login attempt: user=admin src={ip}",      "auth-service"),
            ("ERROR", "SSH auth failure: invalid key for {user}",       "auth-service"),
            ("CRIT",  "BRUTE FORCE: {n} failures in 60s src={ip}",     "auth-service"),
        ],
        "ips": ["185.220.101.47", "91.108.4.38", "198.54.117.200"],
        "users": ["root", "admin", "deploy", "ubuntu", "postgres"],
        "burst": 8,
    },
    "port_scan": {
        "label": "PORT SCAN",
        "events": [
            ("WARN",  "SYN packet to closed port {port} from {ip}",    "proxy-edge"),
            ("WARN",  "Sequential port probe detected: {port} from {ip}", "proxy-edge"),
            ("ERROR", "Port scan detected: {n} ports in 30s from {ip}","proxy-edge"),
        ],
        "ips": ["91.108.4.38", "45.142.212.100"],
        "ports": list(range(20, 3390, 47)),
        "burst": 6,
    },
    "priv_escalation": {
        "label": "PRIV ESCALATION",
        "events": [
            ("WARN",  "sudo command executed by {user}: {cmd}",        "web-server-01"),
            ("ERROR", "Privilege escalation: {user} ran sudo bash at {time} UTC", "web-server-01"),
            ("CRIT",  "NOPASSWD sudo outside business hours: {user}",  "web-server-01"),
        ],
        "users": ["deploy-user", "ci-runner", "backup-agent"],
        "cmds": ["sudo bash", "sudo su -", "sudo chmod 777 /etc/passwd"],
        "burst": 3,
    },
    "sql_injection": {
        "label": "SQL INJECTION",
        "events": [
            ("WARN",  "Suspicious query pattern detected: {ip}",       "db-primary"),
            ("ERROR", "WAF blocked SQLi attempt from {ip}",            "proxy-edge"),
            ("ERROR", "DB error: syntax error near UNION SELECT from {ip}", "db-primary"),
            ("CRIT",  "SQL INJECTION attempt blocked: {ip} target=/api/users", "web-server-01"),
        ],
        "ips": ["103.21.244.0", "198.41.128.0", "172.64.0.0"],
        "burst": 4,
    },
}

COLORS = {
    "INFO":  "\033[32m",   # verde
    "WARN":  "\033[33m",   # amarillo
    "ERROR": "\033[31m",   # rojo
    "CRIT":  "\033[1;31m", # rojo brillante
    "OK":    "\033[36m",   # cyan
    "RESET": "\033[0m",
}


def colorize(sev: str, text: str) -> str:
    return f"{COLORS.get(sev, '')}{text}{COLORS['RESET']}"


def fmt_event(sev: str, host: str, msg: str) -> str:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    return f"  {COLORS['RESET']}{now}{COLORS['RESET']} {colorize(sev, f'[{sev:<5}]')} {COLORS['OK']}{host:<20}{COLORS['RESET']} {msg}"


def build_message(template: str, scenario: dict | None = None) -> str:
    replacements = {
        "{ms}":    str(random.randint(2, 890)),
        "{rows}":  str(random.randint(1, 5000)),
        "{id}":    str(random.randint(1000, 9999)),
        "{ratio}": str(random.randint(60, 98)),
        "{depth}": str(random.randint(0, 500)),
        "{pct}":   str(random.randint(40, 92)),
        "{n}":     str(random.randint(50, 500)),
        "{port}":  str(random.choice(scenario["ports"]) if scenario and "ports" in scenario else random.randint(20, 9000)),
        "{ip}":    random.choice(scenario["ips"]) if scenario and "ips" in scenario else f"10.0.{random.randint(1,4)}.{random.randint(1,254)}",
        "{user}":  random.choice(scenario["users"]) if scenario and "users" in scenario else "svc-user",
        "{cmd}":   random.choice(scenario["cmds"]) if scenario and "cmds" in scenario else "ls",
        "{time}":  datetime.now(timezone.utc).strftime("%H:%M"),
    }
    result = template
    for k, v in replacements.items():
        result = result.replace(k, v)
    return result


async def login(client: httpx.AsyncClient, base_url: str) -> str:
    resp = await client.post(f"{base_url}/api/v1/auth/token",
                             json={"username": "admin", "password": "Admin1234!"})
    resp.raise_for_status()
    print(colorize("OK", f"[SIM] Login OK — JWT RS256 obtenido"))
    return resp.json()["access_token"]


async def send_event(client: httpx.AsyncClient, base_url: str, token: str,
                     sev: str, host: str, msg: str, ip: str | None = None) -> bool:
    try:
        resp = await client.post(
            f"{base_url}/api/v1/events/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"severity": sev, "host": host, "message": msg,
                  "source_ip": ip or f"10.0.1.{random.randint(1,254)}"},
            timeout=5.0,
        )
        return resp.status_code == 201
    except Exception:
        return False


async def run_normal_stream(client: httpx.AsyncClient, base_url: str,
                            token: str, rate: float, stop: asyncio.Event):
    """Genera eventos normales continuamente."""
    interval = 1.0 / rate
    sent = 0
    while not stop.is_set():
        sev, tmpl, host = random.choice(NORMAL_EVENTS)
        msg = build_message(tmpl)
        ok = await send_event(client, base_url, token, sev, host, msg)
        if ok:
            sent += 1
            print(fmt_event(sev, host, msg))
        await asyncio.sleep(interval + random.uniform(-0.1, 0.2))
    print(f"\n{colorize('OK', f'[SIM] Stream normal detenido. {sent} eventos enviados.')}")


async def run_attack(client: httpx.AsyncClient, base_url: str,
                     token: str, name: str):
    """Dispara un escenario de ataque."""
    scenario = ATTACK_SCENARIOS[name]
    label = scenario["label"]
    burst = scenario["burst"]
    print(f"\n{colorize('CRIT', f'[SIM] >> ATAQUE: {label} <<')}")

    for _ in range(burst):
        sev, tmpl, host = random.choice(scenario["events"])
        ip = random.choice(scenario["ips"])
        msg = build_message(tmpl, scenario)
        await send_event(client, base_url, token, sev, host, msg, ip)
        print(fmt_event(sev, host, msg))
        await asyncio.sleep(random.uniform(0.15, 0.4))

    print(colorize("CRIT", f"[SIM] Escenario {label} completado ({burst} eventos)\n"))


async def attack_scheduler(client: httpx.AsyncClient, base_url: str,
                            token: str, stop: asyncio.Event):
    """Lanza ataques aleatorios cada 20-40 segundos."""
    names = list(ATTACK_SCENARIOS.keys())
    while not stop.is_set():
        wait = random.uniform(20, 40)
        print(colorize("WARN", f"[SIM] Proximo ataque en {wait:.0f}s..."))
        try:
            await asyncio.wait_for(stop.wait(), timeout=wait)
        except asyncio.TimeoutError:
            pass
        if not stop.is_set():
            await run_attack(client, base_url, token, random.choice(names))


async def stats_reporter(client: httpx.AsyncClient, base_url: str,
                         token: str, stop: asyncio.Event):
    """Imprime stats cada 15 segundos."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=15)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            resp = await client.get(
                f"{base_url}/api/v1/events/stats",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            s = resp.json()
            print(colorize("OK",
                f"\n[STATS] ev/h={s['events_per_hour']}  "
                f"errores/h={s['failed_logins_hour']}  "
                f"alertas_criticas={s['critical_alerts_open']}\n"
            ))
        except Exception:
            pass


async def main():
    parser = argparse.ArgumentParser(description="SIEM Event Simulator")
    parser.add_argument("--url",  default="http://127.0.0.1:8000", help="Backend URL")
    parser.add_argument("--rate", type=float, default=2.0, help="Eventos/segundo (normal stream)")
    parser.add_argument("--attack-only", action="store_true", help="Solo lanzar ataques, sin stream normal")
    args = parser.parse_args()

    print(colorize("OK", "=========================================="))
    print(colorize("OK", "     SIEM EVENT SIMULATOR v1.0            "))
    print(colorize("OK", f"  Backend: {args.url}"))
    print(colorize("OK", f"  Rate: {args.rate} ev/s  | Ctrl+C para detener"))
    print(colorize("OK", "==========================================\n"))

    stop = asyncio.Event()

    async with httpx.AsyncClient() as client:
        try:
            token = await login(client, args.url)
        except Exception as e:
            print(colorize("CRIT", f"[SIM] ERROR de login: {e}"))
            sys.exit(1)

        tasks = [
            asyncio.create_task(attack_scheduler(client, args.url, token, stop)),
            asyncio.create_task(stats_reporter(client, args.url, token, stop)),
        ]

        if not args.attack_only:
            tasks.append(asyncio.create_task(
                run_normal_stream(client, args.url, token, args.rate, stop)
            ))

        print(colorize("OK", "[SIM] Simulacion iniciada. Ctrl+C para detener.\n"))
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            for t in tasks:
                t.cancel()
            print(colorize("OK", "\n[SIM] Simulacion detenida."))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(colorize("OK", "\n[SIM] Hasta luego."))
