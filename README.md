<img src="logo.svg" width="72" align="right" alt="">

# Latido

*[English](README.en.md)*

Un agente que despierta solo, mira si pasó algo que valga la pena, y te escribe
por Telegram cuando sí. En la enorme mayoría de los latidos se calla, que es el
punto: uno que dice "todo bien" cada rato se silencia en dos días.

Corre sobre Claude Code en modo headless. **No depende de ninguna sesión
abierta**: cada latido es una sesión nueva que vive segundos y muere, y la
continuidad vive en `estado.md`. Puedes cerrar todo y sigue latiendo.

## Qué necesitas

- **macOS.** Usa `launchd`; en Linux habría que traducir los tres agentes a
  systemd, y no está hecho.
- **[Claude Code](https://claude.com/claude-code)** instalado y con sesión
  iniciada. Compruébalo con `claude -p "hola"`.
- **Un bot de Telegram.** Se lo pides a [@BotFather](https://t.me/botfather) con
  `/newbot`; toma treinta segundos y te devuelve un token. Que sea un bot
  **propio del latido**: dos programas leyendo la misma cola de mensajes se los
  roban entre ellos.
- **Python 3.** El que trae macOS sirve. No hay dependencias que instalar.

## Instalación

```sh
git clone <este repo> latido && cd latido
cp config.example.json config.json && chmod 600 config.json
./servidor.py --instalar        # deja la página viva y la abre en cada arranque
open http://127.0.0.1:8737
```

Todo lo demás se hace desde esa página, en este orden:

1. **Telegram** — pega el token del bot y guarda. Después escríbele cualquier
   cosa al bot desde tu Telegram y aprieta **Detectar**: captura solo el chat.
   Hasta que ese paso no esté hecho, el latido no acepta mensajes de nadie.
2. **Qué mira** — las carpetas que le importan, y al lado qué es cada una en una
   frase. Esa descripción es la que usa para saber qué buscar ahí.
3. **Ritmo** — cada cuánto mira por su cuenta. Cuatro horas es un buen punto de
   partida; media hora sirve para probarlo el primer día.
4. **Prender**.

No hay rutas escritas a mano en ninguna parte: los agentes de launchd se generan
con la ubicación del repo que acabas de clonar, y el binario de Claude Code se
busca en el `PATH` y en los sitios habituales. Si lo tienes en un lugar raro,
agrega `"claude": "/ruta/al/binario"` a `config.json`.

El servidor escucha solo en `127.0.0.1` — edita archivos y carga agentes de
launchd, no tiene nada que hacer en la red.

## Cómo funciona

Son tres agentes de launchd, y la división importa: **escuchar es gratis,
pensar es lo que cuesta.**

```
  escucha.py  ── espera un mensaje tuyo (socket abierto, no cuesta nada)
       │
       └──> latido.py <──── el reloj, cada N horas
                │
                └──> claude -p ──> ¿algo que decir? ──> Telegram
```

| Agente | Qué es | Cómo vive |
|---|---|---|
| `local.latido.escucha` | La oreja. Te responde al toque | `KeepAlive` — si se cae, revive |
| `local.latido` | El reloj. Mira por su cuenta | `StartInterval` |
| `local.latido.web` | La página de configuración | `KeepAlive` |

La oreja es el **único** que lee de Telegram: dos consumidores de la misma cola
se roban los mensajes. Deja lo que llega en `buzon.txt` y el latido lo lee de
ahí.

**Solo pasa lo que venga del chat configurado.** Cualquiera que sepa el
`@usuario` de tu bot puede escribirle, y sin ese filtro su texto entraría al
prompt de un agente que lee tus archivos. Los mensajes de otros chats se
descartan sin leerse y quedan anotados en el log de la oreja. Mientras no hayas
hecho el paso de **Detectar**, no entra nadie — ni tú.

| Archivo | Qué es |
|---|---|
| `latido.py` | El latido. Lee el correo, despierta a Claude, manda y registra. |
| `escucha.py` | La oreja. Espera mensajes y dispara un latido al recibirlos. |
| `servidor.py` | La página de configuración. Biblioteca estándar, sin dependencias. |
| `index.html` | Esa página. Un archivo, sin build. |
| `prompt.md` | Su conducta: cuándo callarse, cómo escribir, qué ignorar. |
| `config.json` | Tu configuración y el token. En `600`, fuera de git. |

## Dónde queda el registro

El latido escribe dos cosas sobre tu vida: `bitacora/`, un archivo por día con
lo que dijo o por qué se calló, y `estado.md`, su memoria entre latidos. Esa
bitácora es lo que hace calibrable la cosa — lees por qué se calló y ajustas el
prompt hasta que hable cuando debe.

**Por omisión van dentro del repositorio, y probablemente no es lo que quieres.**
En *Registro* de la página puedes apuntarlas a otra carpeta: una bóveda de
Obsidian, por ejemplo, donde las lees como cualquier otra nota. Los dos archivos
están fuera de git a propósito — son tu diario, no la herramienta, y no tienen
por qué viajar si algún día publicas esto.

## Hablarle tú

Escríbele al bot cuando quieras: la oreja está despierta y dispara un latido en
cuanto llega tu mensaje. La cadencia solo gobierna cada cuánto mira **por su
cuenta**, sin que preguntes.

Solo tiene las herramientas que le des en `herramientas` (`config.json`). De
fábrica lee archivos y escribe; si quieres que use un servidor MCP tuyo, agrega
su nombre a esa lista.

## El modelo

Sonnet por defecto. La tarea es decidir **no** hablar, y ahí los modelos chicos
se van a un extremo: o hablan siempre o no hablan nunca. Haiku sirve si le
recortas el criterio a algo mecánico.

## Que no se muera en silencio

El silencio es su resultado normal, así que **un latido roto se ve igual que
uno callado**. Si mañana vence la sesión de Claude, no vas a notar nada.

Por eso escribe `.ultimo` al terminar — **pero solo si salió bien**. Si midiera
ejecución en vez de éxito, uno que corre y falla cada vez se vería sano. Apunta
cualquier vigilante de frescura a ese archivo con un límite de unas tres veces
la cadencia, y te enteras.

## Sin la página

```sh
./latido.py                                      # un latido ahora
./servidor.py --instalar                         # dejar la página siempre viva
launchctl bootout gui/$UID/local.latido          # apagar el reloj
launchctl bootout gui/$UID/local.latido.escucha  # apagar la oreja
tail -f /tmp/local.latido.escucha.log            # qué oye
```

## Por qué esto no incumple nada

`claude -p` es el modo headless documentado de Claude Code: mismo binario, misma
sesión autenticada, sin humano al teclado. Correrlo desde `launchd` es usar el
cliente de Anthropic en su modo no interactivo. Distinto sería exportar la
credencial de la suscripción hacia un cliente de terceros; eso no pasa acá.
