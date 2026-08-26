#!/usr/bin/env python3
"""La oreja.

Espera mensajes de Telegram con long polling — un socket abierto, no cuesta
nada— y cuando llega uno dispara un latido al instante. Escuchar es gratis;
pensar es lo que cuesta, y por eso son dos procesos y no uno.

Es el ÚNICO que lee de Telegram: dos consumidores de la misma cola se roban los
mensajes. latido.py lee el buzón que este deja.

Lo mantiene vivo launchd con KeepAlive. A mano: ./escucha.py
"""

import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent
CONFIG = REPO / "config.json"
BUZON = REPO / "buzon.txt"
OFFSET = REPO / ".offset"
ESPERA = 25          # segundos de long poll; Telegram admite hasta 50
CASTIGO = 15         # cuánto esperar tras un error de red


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def config():
    try:
        return json.loads(CONFIG.read_text())
    except Exception:
        return {}


def escuchar():
    cfg = config()
    tg = cfg.get("telegram") or {}
    token, propio = tg.get("token"), str(tg.get("chat_id") or "")
    if not token:
        log("sin token todavía; espero")
        return time.sleep(30)

    off = int(OFFSET.read_text().strip()) if OFFSET.exists() else 0
    url = (f"https://api.telegram.org/bot{token}/getUpdates?"
           + urllib.parse.urlencode({"timeout": ESPERA, "offset": off}))
    try:
        with urllib.request.urlopen(url, timeout=ESPERA + 15) as r:
            d = json.load(r)
    except Exception as e:
        log("sin respuesta de Telegram:", e)
        return time.sleep(CASTIGO)

    if not d.get("ok"):
        return time.sleep(CASTIGO)

    # Cualquiera que sepa el @usuario del bot puede escribirle, y lo que llegue
    # entra al prompt de un agente que lee tus archivos. Solo pasa lo del chat
    # configurado, y se falla cerrado: sin chat_id, nadie entra.
    nuevos, ultimo, ajenos = [], None, 0
    for u in d.get("result", []):
        ultimo = u["update_id"]
        m = u.get("message") or u.get("edited_message") or {}
        t = (m.get("text") or "").strip()
        if not t:
            continue
        if propio and str((m.get("chat") or {}).get("id") or "") == propio:
            nuevos.append(t)
        else:
            ajenos += 1

    # Mientras no haya chat configurado no se confirma nada ante Telegram: si se
    # confirmara, los mensajes que el dueño manda para que "Detectar" los vea ya
    # estarían consumidos y el botón no encontraría ninguno, para siempre.
    if ultimo is not None and propio:
        OFFSET.write_text(str(ultimo + 1))   # un ajeno no se reintenta después
    elif not propio:
        time.sleep(10)              # sin offset que avanzar, no gires en vacío
    if ajenos:
        log(f"{ajenos} mensaje(s) de un chat ajeno, descartados")
    if not nuevos:
        return

    with BUZON.open("a") as f:
        for t in nuevos:
            f.write(t + "\n\n---\n\n")
    log(f"{len(nuevos)} mensaje(s) → latido")
    # Sincrónico a propósito: mientras piensa no queremos disparar otro.
    try:
        # Con techo: si el latido se cuelga —un CLI que deja nietos con el pipe
        # abierto, por ejemplo— la oreja quedaría sorda y KeepAlive no la
        # revive, porque el proceso no murió.
        subprocess.run([sys.executable, str(REPO / "latido.py")],
                       cwd=REPO, timeout=900)
    except subprocess.TimeoutExpired:
        log("el latido se pasó de 15 minutos; sigo escuchando")


if __name__ == "__main__":
    log("oreja despierta")
    while True:
        try:
            escuchar()
        except KeyboardInterrupt:
            break
        except Exception as e:                 # nada tumba la oreja
            log("error inesperado:", e)
            time.sleep(CASTIGO)
