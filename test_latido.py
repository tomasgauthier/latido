#!/usr/bin/env python3
"""Red de seguridad mínima. `python3 -m unittest` y listo.

Sin dependencias ni framework, igual que el resto del repo. No prueba todo:
prueba lo que ya se rompió una vez, que es lo único que se sabe que se rompe.

Ojo: latido.py y servidor.py guardan sus rutas en constantes de módulo. Cada
prueba que escriba algo las redirige a una carpeta temporal — si no, esto le
pisa el config.json y el buzón de verdad al dueño.
"""
import http.client
import inspect
import json
import pathlib
import tempfile
import threading
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
