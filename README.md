<img src="logo.svg" width="72" align="right" alt="">

# Latido

*[English](README.en.md)*

Un agente que despierta solo, mira si pasó algo que valga la pena, y te escribe
por Telegram cuando sí. En la enorme mayoría de los latidos se calla, que es el
punto: uno que dice "todo bien" cada rato se silencia en dos días.

Corre sobre Claude Code en modo headless. **No depende de ninguna sesión
abierta**: cada latido es una sesión nueva que vive segundos y muere, y su
continuidad entre latidos vive en un archivo de memoria configurable (la
clave `memoria` en `config.json`; por omisión, `estado.md`). Puedes cerrar
todo y sigue latiendo.

## Qué necesitas

- **macOS o Linux.** En Mac los tres agentes se instalan con `launchd`; en
  Linux, con unidades de usuario de `systemd`. Se elige solo — lo que cambia
  es el sistema de arranque, no el latido.
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
2. **Fuentes** — las carpetas que le importan. Hay un botón *Elegir…* que abre
   un explorador: no hace falta escribir rutas. Al lado de cada una, qué es en
   una frase — esa descripción es la que usa para saber qué buscar ahí.
3. **Ritmo** — cada cuánto mira por su cuenta. Cuatro horas es un buen punto de
   partida; media hora sirve para probarlo el primer día.
4. **Motor** — qué programa despierta en cada latido. Se detecta solo cuáles
   tienes instalados; si es Claude Code, no toques nada.
5. **Prender**.

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
| `prompt.md` | Su conducta: cuándo callarse, cómo escribir, qué ignorar. Es un ejemplo: la clave `prompt` de `config.json` lo apunta a donde quieras. |
| `config.json` | Tu configuración y el token. En `600`, fuera de git. |

## Dónde queda el registro

El latido escribe hasta dos cosas sobre tu vida: `bitacora/`, un archivo por
día con lo que dijo o por qué se calló, y —si tienes memoria configurada— el
archivo que le pongas en `memoria` (`config.json`; por omisión, `estado.md`).
Esa bitácora es lo que hace calibrable la cosa — lees por qué se calló y
ajustas el prompt hasta que hable cuando debe.

La memoria es opcional: ponla en `null` si la continuidad entre latidos ya
vive en otra parte —un sistema de pendientes, una base de datos— y no quieres
que el latido le invente un archivo aparte. Sin ella, el latido no lee ni
reescribe nada entre un latido y el siguiente; toda su memoria es la bitácora
del día.

Cada archivo de la bitácora parte con un `# YYYY-MM-DD`. Si el registro vive
en una bóveda con schema propio —Obsidian con Tolaria, donde una nota sin
`type` no entra al grafo—, la clave `encabezado` de `config.json` es el texto
que va antes de ese título; `{dia}` se reemplaza por la fecha.

**Por omisión van dentro del repositorio, y probablemente no es lo que quieres.**
En *Registro* de la página puedes apuntarlas a otra carpeta: una bóveda de
Obsidian, por ejemplo, donde las lees como cualquier otra nota. Estos archivos
están fuera de git a propósito — son tu diario, no la herramienta, y no tienen
por qué viajar si algún día publicas esto.

## ¿Y por qué no un control remoto?

Existen controles remotos de sesiones —el Remote Control de Claude Code, por
ejemplo— que te conectan desde el teléfono a una sesión que ya está corriendo.
Son mejores que esto en casi todo: potencia completa, conversación de verdad,
cualquier repositorio. Si tienes una sesión abierta y quieres preguntarle algo,
usa eso.

| | Un control remoto | Un latido |
|---|---|---|
| Quién empieza | Tú, siempre | Él también |
| Necesita una sesión viva | Sí | No: la crea |
| Alcance | Total, conversacional | Un tiro corto, herramientas contadas |
| Cuando no hay nada abierto | No hay a qué conectarse | Sigue funcionando |

La diferencia entera cabe en la primera fila. **Un control remoto no tiene
iniciativa**: te acerca a tu sesión, pero nunca te va a escribir él. Este
existe para la otra mitad — que algo te avise un domingo a las ocho de la
mañana, con el computador cerrado y sin que hubiera nada corriendo, porque una
propuesta lleva nueve días parada.

Es un foso angosto. Pero es el único que un control remoto no puede cruzar.

## Hablarle tú

Escríbele al bot cuando quieras: la oreja está despierta y dispara un latido en
cuanto llega tu mensaje. La cadencia solo gobierna cada cuánto mira **por su
cuenta**, sin que preguntes.

Solo tiene las herramientas que le des en `herramientas` (`config.json`). De
fábrica lee archivos y escribe; si quieres que use un servidor MCP tuyo, agrega
su nombre a esa lista.

## Por WhatsApp en vez de Telegram

Si el chat que ocupas todo el día es WhatsApp, el latido puede escribirte ahí:
a tu **chat contigo mismo**, el que ya usas de libreta. Vinculas el latido como
un dispositivo más —el mismo QR de *Dispositivos vinculados*— y desde ahí ese
chat es de los dos.

WhatsApp no tiene un bot que puedas pedir como el de Telegram, así que hace
falta un puente. Vive en `whatsapp/`, es lo único del repo con dependencias, y
por dentro es [Baileys](https://github.com/WhiskeySockets/Baileys) — el cliente
de WhatsApp Web que usa, entre otros, el agente de Hermes para esto mismo.

```sh
cd whatsapp && npm install
node puente.js --parear          # sale un QR: escanéalo desde tu teléfono
```

Node se busca solo, como el binario de Claude Code; si lo tienes en un lugar
raro, agrega `"node": "/ruta/al/binario"` a `config.json`.

Con eso queda anotado tu chat en `config.json`. Vuelve a la página y aprieta
**Prender**: aparece un cuarto agente, `local.latido.whatsapp`, que mantiene el
puente vivo igual que a la oreja.

**El latido no se entera de nada de esto.** El puente habla la misma API de
Telegram —los cinco métodos que el latido usa— en `127.0.0.1`, así que de
`latido.py` para abajo no hay una sola rama nueva: cambia una URL en
`config.json` y ya. Mientras el bloque `whatsapp` esté completo se habla por
ahí; si está a medio llenar, se sigue por Telegram. No hay un interruptor
aparte a propósito — es una forma más de quedar mudo.

| Archivo | Qué es |
|---|---|
| `whatsapp/puente.js` | El puente. Baileys por dentro, cara de Telegram por fuera. |
| `whatsapp/filtro.js` | Quién entra y quién no. Aparte para poder probarlo. |
| `whatsapp/sesion/` | Tu vínculo. Fuera de git — es una credencial. |

### Contestarse solo

En un chat contigo mismo **todo llega marcado como tuyo**, incluso lo que acaba
de decir el latido. Sin cuidado, cada mensaje suyo dispara otro latido que
responde, para siempre. Hay dos redes, y las dos hacen falta:

- La lista de lo que mandó este proceso, por id de mensaje.
- Una marca al principio de cada mensaje (`⏱ *Latido*`). Es la que sirve
  después de reiniciar el puente, cuando esa lista ya se vació y del mensaje
  solo queda el texto.

De paso, la marca es lo que distingue en el chat lo que dijo él de lo que
anotaste tú.

Y el filtro es el mismo que el `chat_id` de Telegram, fallando cerrado: solo
existe tu chat contigo mismo. Un grupo, un estado o el mensaje de un
desconocido se descartan **sin leerse**.

### Lo que estás aceptando

Baileys no es un cliente oficial: habla el protocolo de WhatsApp Web por
ingeniería inversa. WhatsApp puede bloquear un número si detecta automatización,
y acá el número es el tuyo de siempre. El chat contigo mismo es el patrón menos
expuesto que hay —nadie más lo ve, el volumen es de unos pocos mensajes al día—
y por eso es el que usa Hermes, pero el riesgo no es cero. Telegram no tiene
nada de esto: el bot es una función del producto. Si el número te importa más
que el chat, quédate en Telegram.

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

## Otro CLI, otro proveedor

El latido no le pide nada especial a nadie: ejecuta el CLI oficial de tu
proveedor, en su modo no interactivo, con tu propia sesión ya iniciada. No
extrae credenciales, no las reenvía a ningún lado, no monta un proxy, no
automatiza una interfaz y no raspa nada. Es exactamente lo que escribirías tú en
la terminal — solo que lo escribe un temporizador.

Por eso la invocación es configurable. Cualquier CLI que **reciba un prompt como
argumento y devuelva texto por stdout** sirve:

```json
"cli": {
  "bin": "claude",
  "args": ["-p", "{prompt}", "--model", "{modelo}",
           "--permission-mode", "acceptEdits",
           "--allowedTools", "{herramientas}",
           "--output-format", "json"],
  "flag_carpeta": "--add-dir"
}
```

- `{prompt}` se reemplaza por las instrucciones completas.
- `{modelo}` por lo que elijas en la página.
- `{herramientas}` se expande en varios argumentos, uno por herramienta.
- `--output-format json` es lo que permite anotar lo que costó cada latido.
  Si tu CLI no lo tiene, sácalo: funciona igual, solo se queda sin cifras.
- `flag_carpeta` se repite por cada fuente. Déjalo vacío si tu CLI no tiene ese
  concepto — entonces el modelo lee las rutas por el prompt y con sus propias
  herramientas.

Lo único que el latido necesita del otro lado es que el modelo **pueda escribir
un archivo**: `salida.txt` es su único canal de voz.

**Sobre los términos de servicio:** cada proveedor tiene los suyos y cambian.
Esto no los esquiva de ninguna manera —usa el cliente oficial tal como viene—,
pero si vas a correrlo de forma desatendida, la responsabilidad de leer los
términos de tu proveedor es tuya, no de este repositorio.
