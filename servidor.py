#!/usr/bin/env python3
"""La página de configuración del latido.

Biblioteca estándar, sin dependencias. Escucha solo en 127.0.0.1: esto edita
archivos y carga agentes de launchd, no tiene nada que hacer en la red.

    ./servidor.py        →  http://127.0.0.1:8737
"""

import datetime
import json
import os
import pathlib
import plistlib
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = pathlib.Path(__file__).resolve().parent
CONFIG = REPO / "config.json"
# El prompt puede vivir fuera de este repo (config.json: "prompt"). La página
# tiene que editar el que el latido de verdad lee: si editara el del repo
# mientras el latido lee otro, guardarías cambios que no ocurren nunca.
def prompt():
    r = leer().get("prompt")
    return pathlib.Path(os.path.expanduser(r)) if r else REPO / "prompt.md"
ULTIMO = REPO / ".ultimo"
CONSUMO = REPO / "consumo.jsonl"
PULSO = REPO / ".oreja"
# Las transcripciones se guardan por carpeta de trabajo, y el latido siempre
# corre en la suya: acá están sus sesiones y ninguna otra.
SESIONES = (pathlib.Path.home() / ".claude/projects"
            / re.sub(r"[^A-Za-z0-9]", "-", str(REPO)))
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
    # bootout no es instantáneo: si arrancamos el nuevo antes de que muera el
    # viejo, quedan dos orejas consultando el mismo bot y Telegram responde 409
    # a las dos. Se espera a que el nombre desaparezca de verdad.
    lc("bootout", f"{GUI}/{label}")
    for _ in range(50):
        if not vivo(label):
            break
        time.sleep(0.2)
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


def consumo(dias=7):
    """Lo que llevan gastando los latidos, sumado por día.

    Lo escribe latido.py, un renglón por latido. Se lee entero cada vez: son
    unos pocos miles de líneas al año y no vale la pena un índice.
    """
    if not CONSUMO.exists():
        return None
    hoy = datetime.date.today()
    desde = (hoy - datetime.timedelta(days=dias - 1)).isoformat()
    r = {k: {"latidos": 0, "tokens": 0, "usd": 0.0}
         for k in ("hoy", "semana", "total")}
    r["desde"] = ""
    with CONSUMO.open() as f:
        for renglon in f:
            try:
                g = json.loads(renglon)
            except Exception:
                continue
            dia = (g.get("cuando") or "")[:10]
            cubos = ["total"]
            if dia >= desde:
                cubos.append("semana")
            if dia == hoy.isoformat():
                cubos.append("hoy")
            for k in cubos:
                r[k]["latidos"] += 1
                r[k]["tokens"] += sum(g.get(x) or 0 for x in (
                    "entrada", "salida", "cache", "cache_lee", "cache_crea"))
                r[k]["usd"] += g.get("usd") or 0
            r["desde"] = min(r["desde"] or dia, dia)
    return r if r["total"]["latidos"] else None


def sesiones(n=12, techo=60):
    """Los latidos como sesiones: cuándo despertó y quién lo despertó.

    Los dos orígenes que existen —el reloj, y un mensaje tuyo por Telegram—
    salen los dos. Lo que NO sale es lo que abres tú en una terminal dentro de
    esta carpeta: eso es trabajo sobre el latido, no el latido.
    """
    if not SESIONES.is_dir():
        return []
    salida = []
    archivos = sorted(SESIONES.glob("*.jsonl"),
                      key=lambda f: f.stat().st_mtime, reverse=True)
    for f in archivos[:techo]:
        if len(salida) >= n:
            break
        try:
            fila = ojear(f)
        except OSError:
            continue
        if fila:
            salida.append(fila)
    return salida


# El mismo texto que arma armar_prompt() en latido.py. Son dos copias a
# propósito —el latido tiene que correr aunque borres la página— pero si tocas
# una, toca la otra.
AVISO = "Tu dueño te escribió esto"


def ojear(f):
    """Mira una transcripción por arriba. La primera línea de usuario lo dice
    todo: si fue un programa el que la abrió, cuándo, y con qué prompt."""
    with f.open(errors="ignore") as fh:
        for renglon in fh:
            try:
                d = json.loads(renglon)
            except Exception:
                continue
            if d.get("type") != "user":
                continue
            if d.get("entrypoint") != "sdk-cli":
                return None      # una sesión tuya en esta carpeta, no un latido
            crudo = bruto(d)
            i = crudo.find(AVISO)
            if i < 0:
                tipo, tema = "reloj", ""
            else:
                # El bloque va: aviso, advertencia de que es una persona, y el
                # mensaje. Termina en la raya que lo separa del resto.
                bloque = crudo[i:].split("\n\n---", 1)[0]
                tipo = "telegram"
                tema = " ".join(bloque.split("\n\n", 2)[-1].split())
            return {"cuando": local(d.get("timestamp") or ""),
                    "tipo": tipo, "tema": tema[:150],
                    "ultimo": time.strftime("%Y-%m-%dT%H:%M:%S",
                                            time.localtime(f.stat().st_mtime))}
    return None


def local(iso):
    """Las transcripciones marcan la hora en UTC. Acá se lee en la hora de esta
    máquina, que es la que el dueño tiene en la cabeza."""
    try:
        return (datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
                .astimezone().isoformat(timespec="seconds"))
    except Exception:
        return iso


def bruto(d):
    """El prompt tal cual, con sus saltos de línea: acá lo que importa es la
    forma del bloque, no solo las palabras."""
    c = (d.get("message") or {}).get("content")
    if isinstance(c, list):
        c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict))
    return str(c or "")


# ── la API ───────────────────────────────────────────────────────────────────

def estado():
    cfg = leer()
    tg = cfg.get("telegram") or {}
    cli = cfg.get("cli") or CLI_POR_OMISION
    elegido, lista = catalogo(cli)
    return {
        "cadencia": cfg.get("cadencia", 86400),
        "modelo": cfg.get("modelo", "sonnet"),
        "fuentes": cfg.get("fuentes") or [],
        "prompt": prompt().read_text() if prompt().exists() else "",
        "hay_token": bool(tg.get("token")),      # nunca el token mismo
        "chat_id": tg.get("chat_id") or "",
        "registro": cfg.get("registro") or "",
        "cli": json.dumps(cli, indent=2, ensure_ascii=False),
        "motor": elegido,
        "motores": lista,
        "casa": str(pathlib.Path.home()),
        "basicas": BASICAS,
        "herramientas": cfg.get("herramientas") or BASICAS,
        "corriendo": corriendo(),
        "escuchando": vivo(OREJA),
        "ultimo": ULTIMO.read_text().strip() if ULTIMO.exists() else "",
        "consumo": consumo(),
        "sondeo": PULSO.read_text().strip() if PULSO.exists() else "",
        "sesiones": sesiones(),
        "latidos": latidos(),
    }


# Los motores conocidos. Las banderas están leídas del --help de cada CLI, no
# inventadas; donde no se probó a fondo, se dice.
MOTORES = [
    {"id": "claude", "nombre": "Claude Code", "de": "Anthropic", "bin": "claude",
     "args": ["-p", "{prompt}", "--model", "{modelo}",
              "--permission-mode", "acceptEdits",
              "--allowedTools", "{herramientas}",
              "--output-format", "json"],
     "flag_carpeta": "--add-dir",
     "modelos": [["sonnet", "Sonnet — recomendado"],
                 ["haiku", "Haiku — más barato"],
                 ["opus", "Opus — el caro"]],
     "nota": "Probado. Es el motor con el que se escribió esto."},
    {"id": "codex", "nombre": "Codex CLI", "de": "OpenAI", "bin": "codex",
     "args": ["exec", "{prompt}", "-m", "{modelo}",
              "-s", "workspace-write", "--approve-for-me"],
     "flag_carpeta": "--add-dir", "modelos": None,
     "nota": "Banderas leídas de su ayuda, sin probar a fondo. Deja el modelo "
             "vacío para usar el suyo por omisión."},
    {"id": "opencode", "nombre": "opencode", "de": "código abierto", "bin": "opencode",
     "args": ["run", "{prompt}", "-m", "{modelo}"],
     "flag_carpeta": "", "modelos": None,
     "nota": "El modelo va como proveedor/modelo. No tiene concepto de carpetas "
             "permitidas: las lee del prompt con sus propias herramientas."},
]
CLI_POR_OMISION = {k: MOTORES[0][k] for k in ("bin", "args", "flag_carpeta")}


def catalogo(cli):
    """Los motores, con cuál está instalado y cuál es el elegido."""
    elegido = "otro"
    for m in MOTORES:
        if m["bin"] == (cli or {}).get("bin"):
            elegido = m["id"]
    return elegido, [{**m, "instalado": bool(shutil.which(m["bin"]))} for m in MOTORES]


BASICAS = ["Read", "Glob", "Grep", "Write", "Edit"]


def guardar(d):
    cfg = leer()

    motor = d.get("motor")
    if motor and motor != "otro":
        elegido = next((m for m in MOTORES if m["id"] == motor), None)
        if not elegido:
            return {"ok": False, "error": "ese motor no existe"}
        cfg["cli"] = {k: elegido[k] for k in ("bin", "args", "flag_carpeta")}
    elif d.get("cli") is not None:
        # Un JSON malo acá deja al latido mudo y sin avisar, así que no se
        # guarda nada hasta que esté bien formado.
        try:
            cli = json.loads(d["cli"])
            assert isinstance(cli, dict) and cli.get("bin"), "falta \"bin\""
            assert isinstance(cli.get("args"), list), "\"args\" tiene que ser una lista"
        except Exception as e:
            return {"ok": False, "error": f"el motor no se guardó: {e}"}
        cfg["cli"] = cli

    if d.get("herramientas") is not None:
        h = [x.strip() for x in d["herramientas"] if x.strip()]
        if "Write" not in h:
            h.append("Write")      # salida.txt es su única voz: no es opcional
        cfg["herramientas"] = list(dict.fromkeys(h))      # sin repetidos
    cfg["cadencia"] = int(d.get("cadencia") or 86400)
    # Vacío es una respuesta válida: significa "usa el modelo por omisión del
    # motor". Forzar "sonnet" acá le mandaba un modelo de Anthropic a Codex.
    cfg["modelo"] = (d.get("modelo") or "").strip()
    cfg["fuentes"] = [f for f in (d.get("fuentes") or []) if f.get("ruta")]
    cfg["registro"] = (d.get("registro") or "").strip()
    tg = cfg.setdefault("telegram", {})
    if d.get("token"):                  # vacío = no lo toques
        tg["token"] = d["token"].strip()
    if d.get("chat_id"):
        tg["chat_id"] = str(d["chat_id"]).strip()
    escribir(cfg)
    if d.get("prompt"):
        prompt().write_text(d["prompt"])
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


def carpetas(ruta):
    """Lista subcarpetas para el explorador de la página.

    El navegador no puede entregar rutas absolutas —un selector de archivos da
    el nombre y nada más—, así que navegar el disco lo hace el servidor, que
    sí vive en esta máquina. Solo lee nombres de directorios.
    """
    d = pathlib.Path(os.path.expanduser(ruta or "~")).resolve()
    if not d.is_dir():
        d = pathlib.Path.home()
    try:
        hijas = sorted((x.name for x in d.iterdir()
                        if x.is_dir() and not x.name.startswith(".")),
                       key=str.lower)
    except PermissionError:
        hijas = []
    casa = str(pathlib.Path.home())
    bonita = str(d).replace(casa, "~", 1) if str(d).startswith(casa) else str(d)
    return {"ruta": str(d), "bonita": bonita,
            "padre": str(d.parent) if d.parent != d else None,
            "carpetas": hijas}


def accion(cual):
    if cual == "prender":
        return {"ok": instalar(leer().get("cadencia", 86400))}
    if cual == "apagar":
        return {"ok": apagar()}
    if cual == "disparar":
        if corriendo():
            # sin -k: si hay un latido en vuelo no se le mata, se deja terminar
            lc("kickstart", f"{GUI}/{LATIDO}")
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
        if ruta == "/api/carpetas":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self.responder(carpetas((q.get("ruta") or [""])[0]))
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
