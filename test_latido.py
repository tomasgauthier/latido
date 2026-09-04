#!/usr/bin/env python3
"""Red de seguridad mínima. `python3 -m unittest` y listo.

Sin dependencias ni framework, igual que el resto del repo. No prueba todo:
prueba lo que ya se rompió una vez, que es lo único que se sabe que se rompe.

Ojo: latido.py y servidor.py guardan sus rutas en constantes de módulo. Cada
prueba que escriba algo las redirige a una carpeta temporal — si no, esto le
pisa el config.json y el buzón de verdad al dueño.
"""
import ast
import http.client
import os
import inspect
import json
import pathlib
import sys
import tempfile
import threading
import time
import types
import unittest
from http.server import ThreadingHTTPServer

import escucha
import latido
import servidor


class Instalacion(unittest.TestCase):
    """`python3 servidor.py --instalar` reventaba antes de hacer nada."""

    def test_la_pagina_se_instala_con_la_firma_que_existe(self):
        # Reventaba con TypeError: se le pasaban KeepAlive y RunAtLoad, que
        # `agente` nunca aceptó. Una instalación nueva no llegaba a arrancar.
        inspect.signature(servidor.agente).bind(servidor.WEB, "servidor.py")

    def test_sin_cadencia_la_unidad_revive_sola(self):
        # Es lo que la página necesita: no es un reloj, tiene que estar viva.
        with tempfile.TemporaryDirectory() as d:
            servidor.UNIDADES = pathlib.Path(d)
            # Sin systemctl de verdad: acá se mira lo que se escribe en la
            # unidad, no lo que systemd haga con ella. En un Mac ni existe.
            fingido = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            original, servidor.sc = servidor.sc, lambda *a: fingido
            try:
                servidor._systemd(servidor.WEB, "servidor.py", None)
            finally:
                servidor.sc = original
            cuerpo = (pathlib.Path(d) / "web.service").read_text()
        self.assertIn("Restart=always", cuerpo)
        self.assertNotIn("Type=oneshot", cuerpo)


class LlaveDeLaPagina(unittest.TestCase):
    """Una página cualquiera podía POSTear acá desde tu navegador."""

    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.puerto = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, llave=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        cabeceras = {"Content-Type": "application/json"}
        if llave is not None:
            cabeceras["X-Latido-Llave"] = llave
        # Una acción que no existe: llega hasta el final sin tocar nada.
        c.request("POST", "/api/accion", json.dumps({"accion": "ninguna"}), cabeceras)
        return c.getresponse().status

    def test_sin_llave_no_entra(self):
        self.assertEqual(self.post(), 403)

    def test_con_la_llave_equivocada_no_entra(self):
        self.assertEqual(self.post("no-es"), 403)

    def test_con_la_llave_buena_entra(self):
        self.assertEqual(self.post(servidor.LLAVE), 200)

    def test_la_pagina_trae_la_llave_puesta(self):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=5)
        c.request("GET", "/")
        html = c.getresponse().read().decode()
        self.assertIn(servidor.LLAVE, html)
        self.assertNotIn("{{LLAVE}}", html)   # que quede el hueco es peor que nada


class MotorConocido(unittest.TestCase):
    """El `bin` venía del cuerpo del POST: cualquier binario, cualquier argumento."""

    def test_un_binario_de_fuera_de_la_lista_no_se_guarda(self):
        with tempfile.TemporaryDirectory() as d:
            servidor.CONFIG = pathlib.Path(d) / "config.json"
            r = servidor.guardar(
                {"cli": json.dumps({"bin": "/bin/sh", "args": ["-c", "lo que sea"]})})
        self.assertFalse(r["ok"])
        self.assertIn("desconocido", r["error"])

    def test_los_motores_de_la_lista_sí(self):
        self.assertIn("claude", {m["bin"] for m in servidor.MOTORES})


class Buzon(unittest.TestCase):
    """Entre leer y borrar cabía un mensaje entero, y se perdía."""

    def test_nada_se_pierde_aunque_escriban_mientras_se_vacia(self):
        with tempfile.TemporaryDirectory() as d:
            latido.BUZON = escucha.BUZON = pathlib.Path(d) / "buzon.txt"
            latido.BUZON.touch()
            cuantos, recogidos = 300, []

            def escribir():
                for i in range(cuantos):
                    escucha.BUZON.parent.mkdir(exist_ok=True)
                    with escucha.BUZON.open("a") as f:
                        import fcntl
                        fcntl.flock(f, fcntl.LOCK_EX)
                        f.write(f"m{i}" + latido.SEPARADOR)

            h = threading.Thread(target=escribir)
            h.start()
            while h.is_alive():
                recogidos += latido.correo()
            h.join()
            recogidos += latido.correo()

        self.assertEqual(len(recogidos), cuantos)
        self.assertEqual(len(set(recogidos)), cuantos)   # ni repetidos


class Puente(unittest.TestCase):
    """El puente de WhatsApp. Sus dos formas de dejar al latido mudo."""

    def test_el_puente_no_revive_cuando_termina_bien(self):
        # Si le cierras la sesión desde el teléfono, el puente termina a
        # propósito. Reviviéndolo, pide un QR nuevo cada diez segundos para
        # siempre. `Restart=always` es exactamente ese error.
        with tempfile.TemporaryDirectory() as d:
            servidor.UNIDADES = pathlib.Path(d)
            fingido = types.SimpleNamespace(returncode=0, stdout="", stderr="")
            original, servidor.sc = servidor.sc, lambda *a: fingido
            try:
                servidor._systemd(servidor.PUENTE, "whatsapp/puente.js", None,
                                  "/usr/bin/node", solo_si_falla=True)
            finally:
                servidor.sc = original
            cuerpo = (pathlib.Path(d) / "whatsapp.service").read_text()
        self.assertIn("Restart=on-failure", cuerpo)
        self.assertNotIn("Restart=always", cuerpo)
        self.assertIn("/usr/bin/node", cuerpo)   # no python3

    def test_en_launchd_es_lo_mismo_dicho_de_otra_forma(self):
        with tempfile.TemporaryDirectory() as d:
            servidor.AGENTES = pathlib.Path(d)
            original, servidor.lc = servidor.lc, \
                lambda *a: types.SimpleNamespace(returncode=0, stdout="", stderr="")
            antes, servidor.vivo = servidor.vivo, lambda label: False
            try:
                servidor._launchd(servidor.PUENTE, "whatsapp/puente.js", None,
                                  "/usr/bin/node", solo_si_falla=True)
            finally:
                servidor.lc, servidor.vivo = original, antes
            d = json.loads(json.dumps(
                __import__("plistlib").loads(
                    (pathlib.Path(d) / f"{servidor.PUENTE}.plist").read_bytes())))
        self.assertEqual(d["KeepAlive"], {"SuccessfulExit": False})
        self.assertEqual(d["ProgramArguments"][0], "/usr/bin/node")

    def test_sin_node_prender_dice_por_que_en_vez_de_callarse(self):
        # El peor final posible: prendes, se ve prendido, y el latido le habla
        # a un puerto donde no hay nadie. Igualito a un latido callado.
        with tempfile.TemporaryDirectory() as d:
            servidor.CONFIG = pathlib.Path(d) / "config.json"
            servidor.CONFIG.write_text(json.dumps(
                {"whatsapp": {"token": "w", "chat_id": "56@s.whatsapp.net"}}))
            cfg_real = servidor.CONFIG
            original, servidor.shutil.which = servidor.shutil.which, lambda x: None
            try:
                falta = servidor.falta_para_whatsapp()
                self.assertIn("node", falta)
                self.assertFalse(servidor.accion("prender")["ok"])
                # Y con la ruta puesta a mano en config.json, deja de faltar.
                servidor.CONFIG.write_text(json.dumps(
                    {"node": "/usr/bin/node",
                     "whatsapp": {"token": "w", "chat_id": "56@s.whatsapp.net"}}))
                self.assertEqual(servidor.falta_para_whatsapp(), "")
            finally:
                servidor.shutil.which, servidor.CONFIG = original, cfg_real

    def test_cortar_el_pareo_no_mata_a_un_desconocido(self):
        # Esto era `pkill -f "puente.js --parear"`, que también mata a
        # cualquiera con ese texto en su línea de comando. Mató una sesión de
        # ssh probándolo. Ahora se anota el PID y se confirma quién es.
        import subprocess as sp
        ajeno = sp.Popen(["sleep", "30"])
        with tempfile.TemporaryDirectory() as d:
            crudo = (servidor.PID, servidor.SISTEMA)
            servidor.PID = pathlib.Path(d) / "parear.pid"
            servidor.SISTEMA = "launchd"        # la rama que mata por PID
            try:
                servidor.PID.write_text(str(ajeno.pid))
                servidor.desvincular_proceso()
                self.assertIsNone(ajeno.poll(), "mató un proceso que no era suyo")
                self.assertFalse(servidor.PID.exists())   # y limpia el rastro
            finally:
                servidor.PID, servidor.SISTEMA = crudo
                ajeno.kill(); ajeno.wait()

    def test_en_systemd_el_pareo_va_en_su_propia_unidad(self):
        # Como hijo de la página, systemd lo mata al reiniciar el servicio — y
        # "Prender" reinicia el servicio. Se moría justo al apretar el botón.
        vistos = []
        crudo = (servidor.SISTEMA, servidor.sc, servidor.PID)
        servidor.SISTEMA = "systemd"
        servidor.sc = lambda *a: vistos.append(a) or types.SimpleNamespace(
            returncode=0, stdout="", stderr="")
        try:
            servidor.desvincular_proceso()
        finally:
            servidor.SISTEMA, servidor.sc, servidor.PID = crudo
        self.assertEqual(vistos, [("stop", "latido-parear.service")])

    def test_nadie_volvio_a_poner_un_pkill_por_patron(self):
        # Mirando llamadas y no texto: el comentario que explica por qué no se
        # usa pkill también dice "pkill", y no es lo que se está prohibiendo.
        arbol = ast.parse(pathlib.Path("servidor.py").read_text())
        for n in ast.walk(arbol):
            if isinstance(n, ast.Call):
                for arg in ast.walk(n):
                    self.assertNotEqual(
                        getattr(arg, "value", None), "pkill",
                        "volvió un pkill: mata por patrón, no por proceso")

    def test_cambiar_de_canal_reinicia_la_oreja(self):
        # La oreja lee el canal al arrancar y nada más. Sin reiniciarla,
        # pareabas, escribías por WhatsApp y no pasaba nada: seguía colgada de
        # Telegram, y todo se veía sano.
        hechos = []
        crudo = (servidor.vivo, servidor.parar_agente, servidor.arrancar_agente)
        servidor.vivo = lambda label: label == servidor.OREJA
        servidor.parar_agente = lambda l: hechos.append(("parar", l))
        servidor.arrancar_agente = lambda l: hechos.append(("arrancar", l))
        try:
            servidor.recargar_oreja()
        finally:
            (servidor.vivo, servidor.parar_agente,
             servidor.arrancar_agente) = crudo
        self.assertEqual(hechos, [("parar", servidor.OREJA),
                                  ("arrancar", servidor.OREJA)])

    def test_desvincular_borra_la_sesion_de_verdad(self):
        # Dejarla es dejar una credencial viva: tu teléfono la sigue contando
        # como dispositivo vinculado aunque la página diga que no hay nada.
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            crudo = (servidor.CONFIG, servidor.SESION, servidor.QR,
                     servidor.lc, servidor.desvincular_proceso)
            servidor.CONFIG = d / "config.json"
            servidor.SESION = d / "sesion"
            servidor.QR = d / "qr.txt"
            servidor.lc = lambda *a: types.SimpleNamespace(returncode=0, stdout="", stderr="")
            servidor.desvincular_proceso = lambda: None
            oreja, servidor.recargar_oreja = servidor.recargar_oreja, lambda: None
            try:
                servidor.SESION.mkdir()
                (servidor.SESION / "creds.json").write_text("{}")
                servidor.QR.write_text("un qr viejo")
                servidor.CONFIG.write_text(json.dumps(
                    {"cadencia": 3600, "telegram": {"token": "t", "chat_id": "1"},
                     "whatsapp": {"token": "w", "chat_id": "56@s.whatsapp.net"}}))
                servidor.desvincular()
                self.assertFalse(servidor.SESION.exists())
                self.assertFalse(servidor.QR.exists())
                quedo = json.loads(servidor.CONFIG.read_text())
                self.assertNotIn("whatsapp", quedo)
                # Y lo demás intacto: desvincular no es reinstalar.
                self.assertEqual(quedo["telegram"]["token"], "t")
                self.assertEqual(quedo["cadencia"], 3600)
                # Sin el bloque, el latido vuelve solo a Telegram.
                self.assertEqual(latido.canal(quedo)["api"], latido.API)
            finally:
                (servidor.CONFIG, servidor.SESION, servidor.QR,
                 servidor.lc, servidor.desvincular_proceso) = crudo
                servidor.recargar_oreja = oreja

    def test_el_qr_llega_a_la_pagina_mientras_dura_el_pareo(self):
        with tempfile.TemporaryDirectory() as d:
            crudo = (servidor.CONFIG, servidor.QR)
            servidor.CONFIG = pathlib.Path(d) / "config.json"
            servidor.QR = pathlib.Path(d) / "qr.txt"
            try:
                servidor.CONFIG.write_text(json.dumps({}))
                self.assertEqual(servidor.whatsapp()["qr"], "")
                servidor.QR.write_text("███ dibujo ███")
                w = servidor.whatsapp()
                self.assertIn("dibujo", w["qr"])
                self.assertFalse(w["pareado"])
                # Y uno viejo no se muestra: lo dejó un pareo que ya murió, y
                # escanearlo no haría nada sin decir por qué.
                viejo = time.time() - 600
                os.utime(servidor.QR, (viejo, viejo))
                self.assertEqual(servidor.whatsapp()["qr"], "")
            finally:
                servidor.CONFIG, servidor.QR = crudo

    def test_quien_habla_por_telegram_no_necesita_node(self):
        with tempfile.TemporaryDirectory() as d:
            servidor.CONFIG = pathlib.Path(d) / "config.json"
            servidor.CONFIG.write_text(json.dumps(
                {"telegram": {"token": "t", "chat_id": "1"},
                 "whatsapp": {"token": "", "chat_id": ""}}))
            cfg_real = servidor.CONFIG
            original, servidor.shutil.which = servidor.shutil.which, lambda x: None
            try:
                self.assertEqual(servidor.falta_para_whatsapp(), "")
                self.assertTrue(servidor.puente())      # nada que hacer, y bien
            finally:
                servidor.shutil.which, servidor.CONFIG = original, cfg_real


class Canal(unittest.TestCase):
    """Por dónde habla. Elegir mal es quedar mudo sin que nada se vea roto."""

    TG = {"token": "t", "chat_id": "1"}
    WA = {"token": "w", "chat_id": "56912345678@s.whatsapp.net"}

    def test_sin_whatsapp_sigue_siendo_telegram(self):
        c = latido.canal({"telegram": self.TG})
        self.assertEqual(c["api"], latido.API)
        self.assertEqual(c["chat_id"], "1")

    def test_con_whatsapp_pareado_manda_whatsapp(self):
        c = latido.canal({"telegram": self.TG, "whatsapp": self.WA})
        self.assertIn("127.0.0.1", c["api"])
        self.assertEqual(c["chat_id"], self.WA["chat_id"])

    def test_un_whatsapp_a_medio_parear_no_secuestra_el_canal(self):
        # Es el bloque que trae config.example.json: existe y está vacío. Si
        # ganara, el latido hablaría a un puente que no está y se quedaría
        # mudo — el peor resultado, porque se ve igual que uno callado.
        for medias in ({"token": "w", "chat_id": ""}, {"token": "", "chat_id": "x"}, {}):
            c = latido.canal({"telegram": self.TG, "whatsapp": medias})
            self.assertEqual(c["api"], latido.API, medias)

    def test_sin_nada_configurado_no_revienta(self):
        self.assertFalse(latido.canal({}).get("token"))

    def test_la_oreja_pregunta_por_donde_habla_el_latido(self):
        # Dos definiciones de "por dónde" es una de más: la oreja escucharía
        # en Telegram mientras el latido contesta por WhatsApp.
        self.assertIs(escucha.canal, latido.canal)


class Entrega(unittest.TestCase):
    """Telegram corta en 4096 y el fallo se contaba como éxito."""

    def test_un_mensaje_corto_va_entero(self):
        self.assertEqual(latido.trozos("hola"), ["hola"])

    def test_ninguno_se_pasa_del_limite(self):
        largo = "\n".join(f"linea {i}" for i in range(2000))
        for t in latido.trozos(largo):
            self.assertLessEqual(len(t), latido.LIMITE_TELEGRAM)

    def test_no_se_pierde_ni_un_caracter_al_partir(self):
        largo = "\n".join(f"linea {i}" for i in range(2000))
        self.assertEqual("".join(latido.trozos(largo)).replace("\n", ""),
                         largo.replace("\n", ""))

    def test_parte_aunque_no_haya_saltos_de_linea(self):
        for t in latido.trozos("x" * 10000):
            self.assertLessEqual(len(t), latido.LIMITE_TELEGRAM)

    def test_si_falla_un_trozo_el_envio_entero_es_falso(self):
        # Media respuesta es peor que ninguna: parece completa.
        intentos = []
        original = latido._enviar_uno
        latido._enviar_uno = lambda cfg, t: (intentos.append(t), len(intentos) < 2)[1]
        try:
            ok = latido.enviar({}, "\n".join(f"linea {i}" for i in range(2000)))
        finally:
            latido._enviar_uno = original
        self.assertFalse(ok)


class EtiquetaDelModelo(unittest.TestCase):
    """El registro decía Haiku en corridas que eran de Sonnet."""

    # Medido en el VPS: el CLI mete una llamada corta a Haiku ANTES de la
    # buena, y modelUsage la trae primera.
    REAL = {"claude-haiku-4-5-20251001": {"costUSD": 0.000946},
            "claude-sonnet-5": {"costUSD": 0.0402868}}

    def test_gana_el_que_hizo_el_trabajo_no_el_primero(self):
        self.assertEqual(latido.modelo_principal(self.REAL), "claude-sonnet-5")

    def test_sin_datos_no_revienta(self):
        self.assertEqual(latido.modelo_principal(None), "")
        self.assertEqual(latido.modelo_principal({}), "")

    def test_aguanta_una_entrada_sin_costo(self):
        self.assertEqual(
            latido.modelo_principal({"a": None, "b": {"costUSD": 1}}), "b")


class FuentesDeSoloLectura(unittest.TestCase):
    """--add-dir entrega lectura Y escritura: está probado contra el CLI real."""

    def test_lo_que_se_escriba_en_el_espejo_no_toca_la_fuente(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            fuente = raiz / "boveda"
            fuente.mkdir()
            (fuente / "nota.md").write_text("lo que escribió Tomás")
            destino = raiz / "espejo"
            destino.mkdir()

            copias = latido.espejar({"fuentes": [{"ruta": str(fuente)}]}, destino)

            self.assertEqual(len(copias), 1)
            copia = pathlib.Path(copias[0]["ruta"])
            (copia / "nota.md").write_text("lo que escribió un agente")
            (copia / "nuevo.md").write_text("inventado")

            self.assertEqual((fuente / "nota.md").read_text(), "lo que escribió Tomás")
            self.assertFalse((fuente / "nuevo.md").exists())

    def test_la_carpeta_se_rehace_y_no_arrastra_lo_de_antes(self):
        # La ruta es fija para que el agente pueda anotarla en su memoria, así
        # que hay que asegurarse de que no quede basura de la corrida anterior.
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            fuente = raiz / "boveda"
            fuente.mkdir()
            (fuente / "nota.md").write_text("x")
            destino = raiz / "espejo"
            destino.mkdir()
            (destino / "sobra.md").write_text("de la corrida pasada")

            latido.espejar({"fuentes": [{"ruta": str(fuente)}]}, destino)

            self.assertFalse((destino / "sobra.md").exists())
            self.assertTrue((destino / "boveda" / "nota.md").exists())

    def test_un_enlace_simbolico_no_desvia_la_copia(self):
        # La ruta del espejo es fija, así que si alguien alcanza a plantar un
        # enlace ahí, copytree le entregaría la bóveda entera.
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            fuente = raiz / "boveda"
            fuente.mkdir()
            (fuente / "secreto.md").write_text("privado")
            ajena = raiz / "ajena"
            ajena.mkdir()
            destino = raiz / "espejo"
            destino.symlink_to(ajena, target_is_directory=True)

            latido.espejar({"fuentes": [{"ruta": str(fuente)}]}, destino)

            self.assertFalse(destino.is_symlink())
            self.assertEqual(list(ajena.iterdir()), [])   # no le llegó nada

    def test_el_prompt_nombra_el_espejo_y_no_la_fuente_real(self):
        # Si el prompt sigue nombrando la ruta de verdad, el agente va a mirar
        # donde no se le entregó nada — y el espejo no sirve para nada.
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            fuente = raiz / "boveda"
            fuente.mkdir()
            destino = raiz / "espejo"
            destino.mkdir()
            cfg = {"fuentes": [{"ruta": str(fuente), "que_es": "la bóveda"}]}
            fuentes = latido.espejar(cfg, destino)
            texto = latido.armar_prompt(cfg, [], fuentes)

        self.assertIn(str(destino), texto)
        self.assertNotIn(str(fuente) + "`", texto)

    def test_dos_fuentes_con_el_mismo_nombre_no_se_pisan(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = pathlib.Path(d)
            for padre in ("a", "b"):
                (raiz / padre / "notas").mkdir(parents=True)
                (raiz / padre / "notas" / "x.md").write_text(padre)
            destino = raiz / "espejo"
            destino.mkdir()
            copias = latido.espejar(
                {"fuentes": [{"ruta": str(raiz / "a" / "notas")},
                             {"ruta": str(raiz / "b" / "notas")}]}, destino)
        self.assertEqual(len(copias), 2)
        self.assertNotEqual(copias[0]["ruta"], copias[1]["ruta"])


if __name__ == "__main__":
    unittest.main()


class SalidaEnEventos(unittest.TestCase):
    """`stream-json` manda una línea por evento, no un objeto solo."""

    RESULT = json.dumps({"type": "result", "result": "hola",
                         "usage": {"input_tokens": 7, "output_tokens": 2},
                         "total_cost_usd": 0.01, "num_turns": 3})

    def test_encuentra_el_resultado_entre_los_eventos(self):
        bruto = "\n".join([
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps({"type": "assistant", "message": {"content": []}}),
            self.RESULT])
        texto, gasto, fallo = latido.leer_salida(bruto)
        self.assertEqual(texto, "hola")
        self.assertEqual(gasto["entrada"], 7)
        self.assertEqual(gasto["turnos"], 3)
        self.assertFalse(fallo)

    def test_el_objeto_solo_de_siempre_sigue_funcionando(self):
        texto, gasto, _ = latido.leer_salida(self.RESULT)
        self.assertEqual(texto, "hola")
        self.assertEqual(gasto["salida"], 2)

    def test_texto_pelado_de_otro_cli_pasa_entero(self):
        texto, gasto, _ = latido.leer_salida("respuesta cualquiera")
        self.assertEqual(texto, "respuesta cualquiera")
        self.assertIsNone(gasto)

    def test_eventos_cortados_no_mandan_json_crudo(self):
        # Si la corrida se corta antes del `result`, mandarle el chorro de
        # eventos a Telegram es peor que quedarse mudo y dejar hablar a stderr.
        bruto = json.dumps({"type": "assistant", "message": {"content": []}})
        texto, _, _ = latido.leer_salida(bruto)
        self.assertEqual(texto, "")


class AvisoDeProgreso(unittest.TestCase):
    """El mensaje temporal: qué herramienta anuncia y cuándo se calla."""

    def progreso(self):
        p = latido.Progreso({"telegram": {"token": "t", "chat_id": "1"},
                             "verbos": {"mcp__x__ver": "mirando la bandeja"}})
        p.llamadas = []
        p._api = lambda m, **d: (p.llamadas.append((m, d)),
                                 {"result": {"message_id": 9}})[1]
        return p

    def test_el_primer_uso_manda_y_los_siguientes_editan(self):
        p = self.progreso()
        p.herramienta("Read")
        p.ultimo = 0            # sin esto el freno de 3s se come el segundo
        p.herramienta("Bash")
        self.assertEqual([m for m, _ in p.llamadas],
                         ["sendMessage", "editMessageText"])

    def test_el_verbo_sale_de_la_config_y_no_del_codigo(self):
        p = self.progreso()
        p.herramienta("mcp__x__ver")
        self.assertIn("mirando la bandeja", p.llamadas[0][1]["text"])

    def test_una_herramienta_desconocida_no_filtra_su_nombre(self):
        p = self.progreso()
        p.herramienta("mcp__secreto__cosa_privada")
        self.assertNotIn("secreto", p.llamadas[0][1]["text"])

    def test_la_misma_herramienta_dos_veces_no_reescribe(self):
        p = self.progreso()
        p.herramienta("Read")
        p.ultimo = 0
        p.herramienta("Read")
        self.assertEqual(len(p.llamadas), 1)

    def test_mirar_saca_la_herramienta_del_evento(self):
        p = self.progreso()
        p.mirar(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "voy a mirar"},
            {"type": "tool_use", "name": "Read"}]}}))
        self.assertIn("leyendo", p.llamadas[0][1]["text"])

    def test_una_linea_que_no_es_json_no_revienta(self):
        p = self.progreso()
        p.mirar("esto no es json")
        p.mirar("")
        self.assertEqual(p.llamadas, [])

    def test_cerrar_borra_el_mensaje_una_sola_vez(self):
        p = self.progreso()
        p.herramienta("Read")
        p.cerrar()
        p.cerrar()
        self.assertEqual([m for m, _ in p.llamadas].count("deleteMessage"), 1)

    def test_sin_telegram_no_intenta_nada(self):
        p = latido.Progreso({})
        p.herramienta("Read")      # no debe reventar ni dejar id
        self.assertIsNone(p.id)


class EjecutarElCli(unittest.TestCase):
    """`ejecutar` reemplaza a subprocess.run sin cambiar el contrato."""

    def test_devuelve_lo_mismo_que_run(self):
        salida, error, codigo = latido.ejecutar(
            ["sh", "-c", "echo hola; echo feo >&2; exit 3"], 30)
        self.assertEqual(salida.strip(), "hola")
        self.assertEqual(error.strip(), "feo")
        self.assertEqual(codigo, 3)

    def test_llama_al_callback_por_cada_linea(self):
        vistas = []
        latido.ejecutar(["sh", "-c", "echo a; echo b"], 30, vistas.append)
        self.assertEqual([v.strip() for v in vistas], ["a", "b"])

    def test_pasarse_del_tiempo_sigue_siendo_TimeoutExpired(self):
        with self.assertRaises(latido.subprocess.TimeoutExpired):
            latido.ejecutar(["sleep", "5"], 0.3)

    def test_sin_callback_funciona_igual(self):
        salida, _, codigo = latido.ejecutar(["sh", "-c", "echo solo"], 30)
        self.assertEqual((salida.strip(), codigo), ("solo", 0))


class EmojiEnElAviso(unittest.TestCase):
    """El emoji viaja dentro del verbo, no lo pone el código."""

    def test_los_verbos_de_serie_traen_emoji(self):
        self.assertTrue(all(v[0] not in "abcdefghijklmnopqrstuvwxyz"
                            for v in latido.VERBOS.values()))

    def test_un_verbo_propio_manda_tal_cual(self):
        p = latido.Progreso({"telegram": {"token": "t", "chat_id": "1"},
                             "verbos": {"X": "🍋 exprimiendo"}})
        p.llamadas = []
        p._api = lambda m, **d: (p.llamadas.append((m, d)),
                                 {"result": {"message_id": 9}})[1]
        p.herramienta("X")
        self.assertEqual(p.llamadas[0][1]["text"], "🍋 exprimiendo…")


class CorreoSinShell(unittest.TestCase):
    """El latido deja correo.txt y latido.py lo manda. Nunca hay una shell."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        carpeta = pathlib.Path(self.tmp.name)
        self.correo = carpeta / "correo.txt"
        self.original = latido.CORREO
        latido.CORREO = self.correo
        self.addCleanup(setattr, latido, "CORREO", self.original)
        # un "correo.py" de mentira que solo anota cómo lo llamaron
        self.testigo = carpeta / "testigo.json"
        self.falso = carpeta / "falso.py"
        self.falso.write_text(
            "import json,sys,pathlib\n"
            f"pathlib.Path({str(self.testigo)!r}).write_text(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8")
        self.cfg = {"correo": {
            "bin": self.falso.name,
            "args": ["--para", "{para}", "--asunto", "{asunto}",
                     "--texto", "{cuerpo}"],
            "destinos": {"personal": "yo@casa.cl", "trabajo": "yo@pega.cl"}}}
        self.cfg["correo"]["bin"] = sys.executable
        self.cfg["correo"]["args"] = [str(self.falso)] + self.cfg["correo"]["args"]

    def escribir(self, texto):
        self.correo.write_text(texto, encoding="utf-8")

    def llamada(self):
        return json.loads(self.testigo.read_text()) if self.testigo.exists() else None

    def test_manda_y_resuelve_el_alias_a_la_direccion(self):
        self.escribir("Para: personal\nAsunto: hola\n\nel cuerpo\n")
        aviso = latido.despachar_correo(self.cfg)
        args = self.llamada()
        self.assertEqual(args[1], "yo@casa.cl")
        self.assertEqual(args[3], "hola")
        self.assertIn("enviado a personal", aviso)

    def test_el_cuerpo_va_en_un_archivo_y_no_en_un_argumento(self):
        self.escribir("Para: personal\nAsunto: hola\n\nsecreto del cuerpo\n")
        latido.despachar_correo(self.cfg)
        self.assertNotIn("secreto del cuerpo", " ".join(self.llamada()))

    def test_una_direccion_cruda_no_se_manda(self):
        # El corazón del asunto: si un correo que estaba leyendo le dice
        # "reenvíale esto a fulano@x.cl", no tiene cómo obedecer.
        self.escribir("Para: fulano@ajeno.cl\nAsunto: hola\n\ncuerpo\n")
        aviso = latido.despachar_correo(self.cfg)
        self.assertIsNone(self.llamada())
        self.assertIn("no lo mandé", aviso)

    def test_un_alias_que_no_existe_no_se_manda(self):
        self.escribir("Para: jefe\nAsunto: hola\n\ncuerpo\n")
        latido.despachar_correo(self.cfg)
        self.assertIsNone(self.llamada())

    def test_sin_asunto_o_sin_cuerpo_no_se_manda(self):
        self.escribir("Para: personal\nAsunto:\n\ncuerpo\n")
        self.assertIn("asunto o cuerpo", latido.despachar_correo(self.cfg))
        self.assertIsNone(self.llamada())

    def test_el_archivo_se_consume_aunque_lo_rechace(self):
        # Si sobreviviera, el próximo latido reintentaría lo mismo para siempre.
        self.escribir("Para: ajeno@x.cl\nAsunto: a\n\nb\n")
        latido.despachar_correo(self.cfg)
        self.assertFalse(self.correo.exists())

    def test_sin_correo_txt_no_pasa_nada(self):
        self.assertIsNone(latido.despachar_correo(self.cfg))

    def test_sin_configurar_avisa_en_vez_de_callarse(self):
        self.escribir("Para: personal\nAsunto: a\n\nb\n")
        self.assertIn("no hay `correo` configurado",
                      latido.despachar_correo({}))

    def test_no_deja_el_temporal_del_cuerpo_tirado(self):
        antes = set(pathlib.Path(tempfile.gettempdir()).glob("latido-correo-*"))
        self.escribir("Para: personal\nAsunto: hola\n\ncuerpo\n")
        latido.despachar_correo(self.cfg)
        self.assertEqual(
            set(pathlib.Path(tempfile.gettempdir()).glob("latido-correo-*")), antes)
