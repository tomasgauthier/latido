#!/usr/bin/env python3
"""La página de configuración del latido.

Biblioteca estándar, sin dependencias. Escucha solo en 127.0.0.1: esto edita
archivos y carga agentes de launchd, no tiene nada que hacer en la red.

    ./servidor.py        →  http://127.0.0.1:8737
"""

import json
import os
import pathlib
import plistlib
import re
import subprocess
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parent
CONFIG = REPO / "config.json"
PROMPT = REPO / "prompt.md"
ULTIMO = REPO / ".ultimo"
LATIDO = "local.latido"           # el reloj: despierta cada N segundos
OREJA = "local.latido.escucha"    # la oreja: permanente, dispara al recibir
WEB = "local.latido.web"          # esta misma página
AGENTES = pathlib.Path.home() / "Library/LaunchAgents"
PUERTO = 8737
GUI = f"gui/{os.getuid()}"


# ── configuración ────────────────────────────────────────────────────────────

def leer():
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return json.loads((REPO / "config.example.json").read_text())


def escribir(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    CONFIG.chmod(0o600)          # lleva el token del bot


# ── launchd ──────────────────────────────────────────────────────────────────

def lc(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def vivo(label):
    return lc("print", f"{GUI}/{label}").returncode == 0


def corriendo():
    return vivo(LATIDO)


def agente(label, guion, **extra):
    """Escribe el plist con las rutas de ESTE repo y lo recarga."""
    AGENTES.mkdir(parents=True, exist_ok=True)
    p = AGENTES / f"{label}.plist"
    p.write_bytes(plistlib.dumps({
        "Label": label,
        "ProgramArguments": ["/usr/bin/python3", str(REPO / guion)],
        "WorkingDirectory": str(REPO),
        "EnvironmentVariables": {
            "PATH": f"{pathlib.Path.home()}/.local/bin:/opt/homebrew/bin:/usr/bin:/bin",
            "HOME": str(pathlib.Path.home()),
        },
        "StandardOutPath": f"/tmp/{label}.log",
        "StandardErrorPath": f"/tmp/{label}.log",
        **extra,
    }))
    lc("bootout", f"{GUI}/{label}")
    return lc("bootstrap", GUI, str(p)).returncode == 0


def instalar(cadencia):
    """El reloj y la oreja son una sola cosa: se prenden y apagan juntos."""
    a = agente(LATIDO, "latido.py", StartInterval=int(cadencia), RunAtLoad=False)
    b = agente(OREJA, "escucha.py", KeepAlive=True, RunAtLoad=True)
    return a and b


def apagar():
    for label in (LATIDO, OREJA):
        lc("bootout", f"{GUI}/{label}")
    return not corriendo()


def registro():
    """Dónde vive lo que el latido escribe sobre tu vida."""
    r = leer().get("registro")
    return pathlib.Path(os.path.expanduser(r)) if r else REPO


def latidos(n=25):
    """La bitácora en pedazos: cada latido con su hora y de qué tipo fue."""
    salida = []
    carpeta = registro() / "bitacora"
    if not carpeta.is_dir():
        return salida
    for d in sorted(carpeta.glob("*.md"), reverse=True)[:5]:
        for bloque in re.split(r"\n##\s+", "\n" + d.read_text()):
            hora, _, cuerpo = bloque.partition("\n")
            hora, cuerpo = hora.strip(), cuerpo.strip()
            if not re.fullmatch(r"\d{1,2}:\d{2}", hora) or not cuerpo:
                continue
            bajo = cuerpo.lower()
            tipo = ("roto" if bajo.startswith(("roto", "contrato")) else
                    "callo" if bajo.startswith("silencio") else "hablo")
            salida.append({"dia": d.stem, "hora": hora, "tipo": tipo, "texto": cuerpo})
    salida.sort(key=lambda x: (x["dia"], x["hora"]), reverse=True)
    return salida[:n]


# ── la API ───────────────────────────────────────────────────────────────────

def estado():
    cfg = leer()
    tg = cfg.get("telegram") or {}
    return {
        "cadencia": cfg.get("cadencia", 86400),
        "modelo": cfg.get("modelo", "sonnet"),
        "fuentes": cfg.get("fuentes") or [],
        "prompt": PROMPT.read_text() if PROMPT.exists() else "",
        "hay_token": bool(tg.get("token")),      # nunca el token mismo
        "chat_id": tg.get("chat_id") or "",
        "registro": cfg.get("registro") or "",
        "cli": json.dumps(cfg.get("cli") or CLI_POR_OMISION, indent=2, ensure_ascii=False),
        "corriendo": corriendo(),
        "escuchando": vivo(OREJA),
        "ultimo": ULTIMO.read_text().strip() if ULTIMO.exists() else "",
        "latidos": latidos(),
    }


CLI_POR_OMISION = {
    "bin": "claude",
    "args": ["-p", "{prompt}", "--model", "{modelo}",
             "--permission-mode", "acceptEdits",
             "--allowedTools", "{herramientas}"],
    "flag_carpeta": "--add-dir",
}


def guardar(d):
    cfg = leer()
    if d.get("cli") is not None:
        # Un JSON malo acá deja al latido mudo y sin avisar, así que no se
        # guarda nada hasta que esté bien formado.
        try:
            cli = json.loads(d["cli"])
            assert isinstance(cli, dict) and cli.get("bin"), "falta \"bin\""
            assert isinstance(cli.get("args"), list), "\"args\" tiene que ser una lista"
        except Exception as e:
            return {"ok": False, "error": f"el motor no se guardó: {e}"}
        cfg["cli"] = cli
    cfg["cadencia"] = int(d.get("cadencia") or 86400)
    cfg["modelo"] = d.get("modelo") or "sonnet"
    cfg["fuentes"] = [f for f in (d.get("fuentes") or []) if f.get("ruta")]
    cfg["registro"] = (d.get("registro") or "").strip()
    tg = cfg.setdefault("telegram", {})
    if d.get("token"):                  # vacío = no lo toques
        tg["token"] = d["token"].strip()
    if d.get("chat_id"):
        tg["chat_id"] = str(d["chat_id"]).strip()
    escribir(cfg)
    if d.get("prompt"):
        PROMPT.write_text(d["prompt"])
    if corriendo():
        instalar(cfg["cadencia"])       # la cadencia vive en el plist
    return {"ok": True}


def detectar():
    """Captura el chat: el dueño le escribe al bot y apretamos este botón."""
    cfg = leer()
    tok = (cfg.get("telegram") or {}).get("token")
    if not tok:
        return {"ok": False, "error": "primero guarda el token del bot"}
    # Dos lectores de la misma cola se pelean (409), así que la oreja se calla
    # un segundo. No se pierde nada: acá se mira sin consumir.
    estaba = vivo(OREJA)
    if estaba:
        lc("bootout", f"{GUI}/{OREJA}")
    try:
        url = f"https://api.telegram.org/bot{tok}/getUpdates?timeout=0"
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.load(r)
    except Exception as e:
        return {"ok": False, "error": f"no se pudo hablar con Telegram: {e}"}
    finally:
        if estaba:
            lc("bootstrap", GUI, str(AGENTES / f"{OREJA}.plist"))
    for u in reversed(d.get("result", [])):
        m = u.get("message") or u.get("edited_message") or {}
        chat = (m.get("chat") or {}).get("id")
        if chat:
            cfg.setdefault("telegram", {})["chat_id"] = str(chat)
            escribir(cfg)
            return {"ok": True, "chat_id": str(chat)}
    return {"ok": False, "error": "no hay mensajes. Escríbele algo al bot y reintenta."}


def accion(cual):
    if cual == "prender":
        return {"ok": instalar(leer().get("cadencia", 86400))}
    if cual == "apagar":
        return {"ok": apagar()}
    if cual == "disparar":
        if corriendo():
            lc("kickstart", "-k", f"{GUI}/{LATIDO}")
        else:
            subprocess.Popen(["/usr/bin/python3", str(REPO / "latido.py")], cwd=REPO)
        return {"ok": True}
    return {"ok": False, "error": "acción desconocida"}


class Handler(BaseHTTPRequestHandler):
    def responder(self, cuerpo, tipo="application/json"):
        b = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
        self.send_response(200)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Cache-Control", "no-store")   # editas el HTML y recargas
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path
        if ruta == "/":
            return self.responder((REPO / "index.html").read_bytes(), "text/html")
        if ruta == "/logo.svg":
            # el mismo archivo que va en el README: un solo logotipo, no dos
            return self.responder((REPO / "logo.svg").read_bytes(), "image/svg+xml")
        if ruta == "/api/estado":
            return self.responder(estado())
        self.send_error(404)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        d = json.loads(self.rfile.read(largo) or "{}")
        ruta = urllib.parse.urlparse(self.path).path
        if ruta == "/api/guardar":
            return self.responder(guardar(d))
        if ruta == "/api/detectar":
            return self.responder(detectar())
        if ruta == "/api/accion":
            return self.responder(accion(d.get("accion")))
        self.send_error(404)

    def log_message(self, *a):
        pass          # sin ruido en la terminal


if __name__ == "__main__":
    import sys
    if "--instalar" in sys.argv:
        # Deja esta página siempre disponible: launchd la levanta al iniciar
        # sesión y la revive si se cae.
        ok = agente(WEB, "servidor.py", KeepAlive=True, RunAtLoad=True)
        print("página instalada" if ok else "no se pudo instalar la página")
        raise SystemExit(0 if ok else 1)
    print(f"latido → http://127.0.0.1:{PUERTO}   (ctrl-c para salir)")
    ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler).serve_forever()
