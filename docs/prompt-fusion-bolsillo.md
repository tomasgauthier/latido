# Prompt para la sesión de latido

Lánzala desde `~/Desarrollos/latido`, que es donde vive el repo.

---

Trabajamos sobre `~/Desarrollos/latido`. Hay dos cosas sobre la mesa y la primera manda
sobre la segunda, así que resuélvela conmigo antes de tocar nada. (Había una tercera; se
fue a su propio archivo, ver §3.)

## Paso 0 — hecho el 2026-09-15. Esto ya no se pregunta.

Se leyó el VPS (`ssh agente@personal-agents`, solo lectura). Lo que sigue es evidencia, no
suposición, y **deja obsoleta media hoja de este prompt**:

- **El disparador es systemd, cerrado.** `crontab -l` → «no crontab for agente».
  `latido.timer` existe con `OnUnitActiveSec=43200s`, `OnBootSec=3min`, `Persistent=true`, y
  se rearma desde el **arranque** de la corrida anterior, no desde el final (LAST 16:38:13 →
  NEXT 04:38:13, doce horas exactas). `latido.service` es `Type=oneshot`,
  `WorkingDirectory=/home/agente/latido`,
  `ExecStart=/usr/bin/python3 /home/agente/latido/latido.py`, `TimeoutStartSec=900`.
  **Ojo para el renombre: esa ruta está escrita dos veces y a mano.**
- **El «wrapper que hace git» no existe.** Nunca existió. Los commits de `agente` en la
  bóveda los hace `~/bin/sincronizar-bovedas.sh` por `bovedas.timer`, que corre **cada diez
  minutos** y es ajeno al latido. Por eso los intervalos entre commits parecían derivar: son
  hora de término del latido redondeada al siguiente múltiplo de diez minutos. No busques
  ese script; no está.
- **Vivos ahora mismo**: `escucha.service`, `web.service`, `whatsapp.service` y el timer.
  `.oreja` respondiendo al segundo. El clon del VPS está en `d9ed71f`, el mismo HEAD que el
  Mac: el repo **sí** está sincronizado, y lo que diverge es solo lo que nunca estuvo en git.
- **El correo YA está enchufado en el VPS.** `config.json` tiene bloque `correo` con
  `bin=/home/agente/bin/correo.py` y destinos `personal` y `trabajo`. `correo.py` manda por
  **SMTP desde `agente@gauthier.cl`**, con la clave en `~/.correo-env` (600), y también sabe
  mandar citas `.ics` como `text/calendar; METHOD:REQUEST`. **La §2 de más abajo está
  resuelta**: lo único vivo ahí es si conviene cambiarse a Resend por entregabilidad, y eso
  está estudiado aparte en `decision-correo.md`.
- **Las manos también están, y enchufadas.** `~/bin/mcp-bolsillo.js` expone
  `bolsillo_capturar` y `bolsillo_hecho` contra la API de bolsillo, con el portador en
  `~/.bolsillo-token` (600); el servidor MCP `bolsillo` está registrado en scope de usuario
  en `~/.claude.json`, y las dos herramientas están en la lista `herramientas` del config.
  A propósito **no** hay herramienta de lectura: el latido ya lee las tareas de los `.md` de
  belki en la bóveda que tiene sincronizada. **El Paso 3 de más abajo está construido.**
- **El VPS va en UTC**, confirmado por `date` y por el offset `+0000` de los commits.

**Lo que quedó realmente pendiente, que es bastante menos y bastante mejor de lo que este
prompt suponía:**

1. **El cerebro corre con el prompt de un muerto.** `config.json` del VPS tiene
   `prompt = /home/agente/transito/agente/prompt.md`. Tránsito está jubilado desde el 11 de
   septiembre. Ese archivo es hoy lo que define quién es el agente, y habla de una bandeja
   que ya no existe. **Es el arreglo de mayor rendimiento de toda la lista**, y no toca
   infraestructura: es un archivo de texto.
2. **~~`memoria: null`~~ — falsa alarma, es deliberado.** El docstring de `memoria()`
   (`latido.py:128`) dice que `null` significa que la continuidad vive en otra parte, y el
   prompt del VPS lo confirma en su sección «Tu memoria es belki»: la continuidad son las
   tareas de belki más el registro en `Latido/`. No hay nada que arreglar acá.
3. **La hora.** `ahora()` le dice al modelo la hora UTC, así que cree que es de madrugada
   cuando son las seis de la tarde. Rompe cualquier «hoy», «mañana» o «a esta hora».
4. **Las preguntas 0 y 2 siguen siendo tuyas** (qué oreja, y qué significa un mensaje). Nada
   de lo que se leyó en el VPS las contesta, porque no son técnicas.
5. **El renombre**, que es lo de menor rendimiento y mayor riesgo de toda la lista: ver el
   Paso 2.

## 1 · El nombre, que en realidad es una pregunta de arquitectura

Quiero que latido pase a llamarse **bolsillo**. Pero **ya existe algo llamado bolsillo**:
`~/Desarrollos/bolsillo`, repo `github.com/tomasgauthier/bolsillo`, con proyecto en Vercel,
construido el 2026-09-11 con su propio SDD en `docs/superpowers/`. Se describe como «el
brazo móvil de belki: capturar, ver y marcar hecho desde el celular».

Mira los dos antes de proponerme nada, porque no son dos versiones de lo mismo: son
arquitecturas opuestas y sospechosamente complementarias.

| | latido (`~/Desarrollos/latido`) | bolsillo (`~/Desarrollos/bolsillo`) |
|---|---|---|
| Dónde corre | **mi VPS personal**, como usuario `agente` | Vercel, serverless |
| Lenguaje | Python, sin dependencias | JavaScript, funciones en `api/` |
| Telegram | **envía**; la oreja (`escucha.py`) lee por `getUpdates` | **recibe** por webhook, y envía |
| WhatsApp | puente propio (`whatsapp/puente.js`) que imita la API de Telegram; si está pareado, manda por ahí | — |
| Bóveda | clon git de `brain-replika` en el VPS (a juzgar por los commits de autor `agente`); `latido.py` solo puede **leer** las fuentes (las copia a `.espejo` y las borra al terminar) | escribe `_belki_files/Data/AAAA-MM.md` por la **API de GitHub**, con `sha` como control de concurrencia |
| Inteligencia | despierta `claude -p` con un prompt y una lista de herramientas | ninguna: `lib/belki.js` parsea y serializa el formato del plugin, deriva listas, marca hechas |
| Estado entre corridas | opcional (`memoria` en `config.json`) más el registro `Latido/` en la bóveda | ninguno (serverless) |
| Disponible | siempre | siempre |

**Tres cosas que el repo local no te va a decir, y que necesitas saber antes de opinar:**

- **El repo local no es lo que corre.** El `config.json` de acá es el del Mac, del 28 de
  agosto: apunta al prompt de Tránsito (`~/Desarrollos/transito/agente/prompt.md`) y a
  herramientas `mcp__transito__*`, y Tránsito está jubilado desde el 2026-09-11 (lo dice su
  propio último commit). La bitácora que el VPS escribe en la bóveda habla de belki
  (`_belki_files/Data`), de tareas con `agendar`+`due`, y trae un frontmatter de Tolaria que
  la config local no genera. O sea: el VPS tiene **su propio `config.json`, su propio prompt
  su propio prompt**. (El «script que hace git» resultó no existir: ver el Paso 0.) Ninguno
  de los dos está en git, y los dos se leyeron el 15: están respaldados en el VPS en
  `~/respaldos-latido/antes-fusion-20260915.tgz`.
- **Cómo se dispara** — contestado arriba: systemd. Lo que sigue queda como rastro del
  razonamiento, no como duda abierta. Yo decía cron. Pero `servidor.py` tiene una rama completa de `systemd` para Linux (unidades de
  usuario `latido.timer`, `escucha.service`, `web.service`, `whatsapp.service`, con
  `EnvironmentFile=~/.claude.env`). Los intervalos entre commits de `agente` en la bóveda
  (`git log --author=agente`, que es hora de arranque más lo que dure la corrida) parten el
  asunto en dos épocas: del 6 al 11 de septiembre son **siempre de más de 12h** —12h12,
  12h12, 12h08, 12h09, 12h08, 12h09, 12h06, 12h08— que es lo que hace un reloj que se
  rearma **cuando la corrida termina** (`OnUnitActiveSec`); del 12 en adelante oscilan
  **alrededor de 12h**, por arriba y por abajo —11h57, 11h56, 12h01, 11h54, 12h10—, que es
  lo que hace una hora fija con corridas de largo variable. Algo se movió el 11, el día que
  reconstruí medio sistema. Dato lateral, contra lo que yo creía: **un latido fuera de hora
  no corre el reloj** (el 14: 04:42 → 11:15 a mano → 16:45, o sea 12h03 contados desde las
  04:42), lo que calza con que `escucha.py` lance `latido.py` directo y no por el
  disparador. Lo de `launchd` en el código y el README es la rama de Mac, no herencia
  muerta: el repo sirve en los dos. **Comprueba en el VPS `systemctl --user list-timers` y
  `crontab -l`, las dos**, antes de creer ninguna: desde acá no se decide.
- **El VPS se ve desde acá sin ssh.** Cada latido termina en un commit de autor `agente` en
  `~/Dropbox/Obsidian/Brain-replika` (`git log --author=agente`), y `Latido/ultimo.txt` es su
  interruptor de hombre muerto: hoy dice `2026-09-15T16:38:49`. Esa es la comprobación de
  cada paso de abajo. Cómo entrar al VPS está anotado en una tarea migrada
  (`~/Desarrollos/bolsillo/tests/fixtures/2026-09.md`, cerca de la línea 460).

**Lo que ya está contestado, con evidencia**: es **un solo bot**. `getMe` con el token de
`config.json` devuelve id `8975301098`, usuario `@TransitoTG_bot`, nombre visible
«Bolsillo»; el `.env` de bolsillo lleva el mismo id de bot y el mismo `chat_id`; y
`getWebhookInfo` muestra el webhook apuntando a `bolsillo-…vercel.app/api/telegram` desde el
11 de septiembre. También lo usa el aviso de intake de Blaeind (`api/_aviso.js`, solo
envía). La consecuencia no es estética: **Telegram entrega las actualizaciones de un bot por
webhook o por `getUpdates`, nunca por los dos.** Con el webhook puesto, `getUpdates`
responde 409. **Pero eso no me deja sordo: la oreja del VPS es WhatsApp**, con un puente
propio sobre Baileys (`whatsapp/puente.js`, sesión con `useMultiFileAuthState`) leyendo mi
chat conmigo mismo. Telegram quedó de boca, y `sendMessage` funciona igual con el webhook
puesto. Y el renombre visible ya ocurrió: el bot se llama Bolsillo desde el 11.

Eso deja **cuatro preguntas** que la fusión tiene que contestar, en este orden:

0. **Dos orejas en canales distintos, y hay que elegir.** Yo le escribo a latido por
   **WhatsApp**, a mi propio chat, con el puente de Baileys que corre en el VPS; bolsillo
   recibe por **Telegram**, por webhook. La boca, en cambio, ya es común: el mismo bot
   Bolsillo. Un agente fusionado con dos orejas en dos aplicaciones es raro de usar y raro
   de mantener, así que plantéame el trade-off en vez de elegir tú:
   - **Baileys no es una API oficial**: es WhatsApp Web por dentro. La sesión se cae, hay
     que re-parear con QR, y la cuenta corre riesgo si WhatsApp lo nota. A cambio, es donde
     yo escribo sin pensar.
   - **Telegram con bot oficial es estable y notifica de verdad.** Ahí está su ventaja
     grande: el self-chat de WhatsApp está silenciado por diseño, así que lo que le mando
     por ahí no me vuelve como notificación. Ese fue el motivo de que el aviso de intake de
     Blaeind se hiciera por Telegram y no por WhatsApp.
   Revisa también `whatsapp/filtro.js` antes de mover nada: está escrito para que un
   mensaje propio que vuelve a entrar no deje al agente contestándose a sí mismo para
   siempre. Esa lógica no se pierde en la fusión.

   **Y ojo con el orden: esta pregunta decide si la 2 existe.** Si la oreja se queda en
   WhatsApp, cada mensaje tiene un solo dueño por el canal en que llegó —bolsillo captura
   por Telegram, latido conversa por WhatsApp— y la pregunta 2 se puede posponer. Si la
   oreja se muda a Telegram, los dos consumidores pelean el mismo texto y la 2 pasa a ser
   obligatoria y bloqueante.
1. **Quién hospeda al agente fusionado.** El cerebro —`claude -p`, prompt, memoria,
   registro, el clon de la bóveda— solo puede vivir en el VPS: Vercel no corre un CLI. La
   puerta —el webhook— necesita una URL pública con TLS, que Vercel ya tiene y el VPS no. Y
   el spec de bolsillo **ya dibujó esa costura**: `BOLSILLO_API_TOKEN` se agregó el 11
   «para que Latido (y cualquier cron o MCP) consulte Bolsillo sin navegador» (sección
   «Clientes sin navegador»). Cerebro en el VPS, puerta y manos en Vercel es la respuesta
   diseñada; confírmamela o discútela, pero di qué se gana y qué se pierde si en cambio se
   absorbe todo a un lado: todo al VPS es exponer HTTPS y administrar un node; todo a Vercel
   es quedarse sin CLI ni memoria, o sea sin agente.
2. **Qué significa un mensaje al bot.** No es «cuál receptor sobra»: los dos hacen cosas
   distintas con el mismo texto. `lib/telegram.js` de bolsillo convierte cada mensaje del
   chat autorizado en una tarea y contesta «Anotado en la bandeja»; latido lo convertía en
   una pregunta al agente y respondía. Hoy gana bolsillo, porque el webhook gana. La fusión
   tiene que fijar el protocolo —un prefijo, una palabra clave, o que bolsillo reenvíe al VPS,
   que es infraestructura nueva— y eso lo decido yo, no el código.
3. **Tres escritores, una bóveda.** Ya no son dos caminos, son tres, y todos terminan en
   GitHub: el Mac respalda Dropbox cada diez minutos (`cl.gauthier.brain-replika-backup`), el
   VPS hace commit como `agente` después de cada latido, y bolsillo escribe por la API de
   Contents. El `merge=union` de `.gitattributes` cubre **solo** `_belki_files/Data/*.md`. La
   pregunta real es si el wrapper del VPS hace `pull` antes de leer y `push` después de
   escribir, y qué pasa con `Latido/` cuando choca. Y como latido no puede escribir las
   fuentes, «manos» para el agente significa un MCP o el patrón de `correo.txt`
   (un archivo que `latido.py` despacha con un binario acotado) contra los endpoints de
   bolsillo. Eso es construir: ver el final de este prompt.

**Pregúntame qué quiero antes de mover un archivo.** La razón por la que dije que «ahora
sí parece un agente real» es que despierta solo y me habla sin que yo abra nada: lo que le
falta para serlo del todo es lo que decidan las preguntas 1 y 2, no cómo se llame la carpeta.

### El plan, si seguimos: un paso, una comprobación

- **Paso 0 — ~~leer el VPS antes de tocar nada~~. HECHO el 2026-09-15, ver arriba.**
  Quedó por leer, si hace falta más adelante: `cat .oreja`, `cat Latido/ultimo.txt`,
  `systemctl --user list-timers` **y** `crontab -l`, el wrapper que hace git,
  `config.json` (fuentes, prompt, memoria, bloque `whatsapp`, y si hay bloque `correo`), la
  configuración de Himalaya, y `claude auth status`. **La hora ya está contestada y no hace
  falta preguntarla: el VPS va en UTC.** Los commits de `agente` traen offset `+0000` —el de
  hoy es `2026-09-15 16:49:13 +0000` contra el `16:38:49` de `ultimo.txt`—, así que `ahora()`
  en `latido.py` le está diciendo al modelo una hora corrida tres o cuatro horas de la de
  Chile. Eso ya no es una sospecha, es un arreglo pendiente: anótalo acá y no lo toques
  todavía. Comprobación: nada se cambia; sales con las respuestas escritas.
- **Paso 1 — destapar la oreja** según lo que decidan las preguntas 0 y 2. Comprobación: un
  mensaje mío produce un latido fuera de hora en la bitácora y una respuesta en el chat.
- **Paso 2 — el renombre, y solo después del 0.** Primero en el repo, en una rama: la
  superficie son 14 archivos (`grep -rli latido` sin `node_modules`: los tres `.py`,
  `test_latido.py`, `prompt.md`, los dos README, `index.html`, `logo.svg`, `whatsapp/*.js`,
  `filtro.test.mjs`, `package.json` y su lock), más las etiquetas `local.latido*` y los
  nombres de unidad de `servidor.py`, los logs `/tmp/<etiqueta>.log`, la `MARCA` de
  `puente.js`, el prefijo `latido-correo-` de los temporales y el nombre del repo en GitHub
  —`tomasgauthier/bolsillo` ya está tomado: renombrar uno, o monorepo, lo decido yo—. La
  carpeta `Latido/` de la bóveda la nombra el prompt del VPS y la indexa Tolaria: se queda,
  o se mueve en un paso aparte. Comprobación en el repo: `python3 -m unittest` verde (hoy
  son 64 pruebas y pasan) y el grep devuelve solo menciones históricas. El renombre no es
  solo de texto: `escucha.py` hace `from latido import canal`, `test_latido.py` importa
  `latido`, y `servidor.py` pasa `"latido.py"` y `"escucha.py"` como el guion de cada
  unidad. Después, **en una sola sesión en el VPS**: mover la carpeta, reescribir la ruta
  en el disparador —si resulta ser systemd, regenerar las unidades con `servidor.py` (las
  escribe con su propio `REPO`), no editarlas a mano; si es cron, editar la línea—, en el
  wrapper y en `git remote set-url`, **reiniciar la oreja y el puente** (son procesos vivos
  con `REPO` resuelto al arrancar: después del `mv` siguen sondeando y escribiendo
  `buzon.txt` en la ruta vieja sin caerse nunca), **dejar un symlink por cada nombre
  que el disparador viejo invoca** —`ln -s bolsillo latido` donde estaba la carpeta **y**
  `ln -s bolsillo.py bolsillo/latido.py` si el guion también se renombró, porque con solo el
  de la carpeta la ruta vieja termina en un `bolsillo/latido.py` que no existe y falla igual
  de callado; `REPO = pathlib.Path(__file__).resolve().parent` resuelve los dos y aterriza
  igual en `bolsillo`, así que el disparador viejo sobrevive una cadencia entera mientras
  compruebas— y correr el latido a mano como `agente`.
  Comprobación:
  `ultimo.txt` avanza y me llega un mensaje. Luego esperar una cadencia (12 h) y mirar
  desde el Mac que aparezca el commit de `agente` con la fecha nueva. Un renombre hecho solo
  en el repo local deja el reloj del VPS disparando una ruta que ya no existe, y eso falla en
  silencio: el agente simplemente deja de hablar y nadie se entera, que es exactamente lo que
  este proyecto existe para evitar.
- **Paso 3 — ~~las manos~~. YA ESTÁ CONSTRUIDO.** `~/bin/mcp-bolsillo.js` captura y marca
  hecho contra la API de bolsillo con el portador de `~/.bolsillo-token`, y está registrado
  como servidor MCP en scope de usuario. Lo que falta no es construirlo: es **comprobar que
  funciona de punta a punta** (`node ~/bin/mcp-bolsillo.js --test`, y después un latido real
  que capture algo y que aparezca en belki).

## 2 · Que latido mande correo — RESUELTO, salvo la entregabilidad

**Ya manda.** El VPS tiene el bloque `correo` enchufado y `~/bin/correo.py` mandando por SMTP
desde `agente@gauthier.cl`; el «programa que no consta» era ese. Lo único vivo es si conviene
cambiarse a Resend sobre `envios.gauthier.cl` por entregabilidad: está en
`decision-correo.md`. Lo de abajo queda como documentación del mecanismo, que sigue siendo
exacta y sirve para entenderlo. En `latido.py`:

- `despachar_correo(cfg)` (línea 406) lee lo que el agente dejó en `correo.txt`, lo consume
  pase lo que pase, y exige que `Para:` sea un **alias** de la lista `destinos` de la config,
  nunca una dirección. Está escrito así a propósito —el docstring lo explica— para no darle
  una shell a un agente que lee correo y páginas web: sabe hacer una sola cosa. Corre
  **después** de mandar el mensaje, así que un correo que falla no se traga lo que tenía
  que decir.
- `CORREO_ARGS = ["--para", "{para}", "--asunto", "{asunto}", "--texto", "{cuerpo}"]`
  (línea 296) define cómo se le habla al programa que manda; `correo.args` en la config lo
  reemplaza. Ojo: **`{cuerpo}` es la ruta de un archivo temporal, no el texto** —el cuerpo no
  pasa por la línea de comandos porque cualquiera de la máquina la ve—. El script tiene que
  leer ese archivo.
- La config exige `correo.bin` **y** `correo.destinos`; sin los dos, `despachar_correo`
  devuelve «CORREO: escribió uno pero no hay `correo` configurado» y no manda nada. Hoy
  **`config.json` no tiene sección `correo`** acá. En el VPS no lo sé: la bitácora registra
  correos «enviado a personal» el 4 y el 11 de septiembre, así que allá **algo** hubo en
  algún momento, con qué programa no consta. Otra cosa que se pregunta en el paso 0.

Lo que hay disponible para enchufarlo, ya verificado:

- **`envios.gauthier.cl`**: estado `verified` en Resend, envío habilitado, región
  `sa-east-1`. Es el dominio pensado para esto.
- **Resend con MCP**: el servidor `resend-personal` está instalado en scope de usuario, así
  que sus herramientas están en cualquier sesión de Claude Code **del Mac**. Sirve para
  verificar y para probar; no es el mecanismo, porque quien manda es el VPS.
- **Himalaya vive en el VPS**, que es justamente donde corre el emisor. También lo tengo en
  el Mac (`/opt/homebrew/bin/himalaya`, cuenta `agent` sobre `agente@gauthier.cl`), pero ese
  no es el que importa. **Sospecha fuerte: Himalaya del VPS es el «programa que no consta»
  con el que salieron los correos del 4 y el 11 de septiembre.** Compruébalo antes de
  proponer nada: mira el `config.json` del VPS y la configuración de Himalaya de allá.

**Empieza por lo que ya está allá, no por lo nuevo.** Si Himalaya del VPS ya manda, lo que
falta puede ser solo el bloque `correo` en el `config.json` de esa máquina —con su `bin` y
su lista de `destinos`— y no un programa nuevo. Sería el arreglo más corto y el que menos
mueve.

Un script propio en Python que llame a la API HTTP de Resend es la alternativa, y tiene una
ventaja concreta: `envios.gauthier.cl` está verificado en Resend, con DKIM y SPF, así que
lo que salga por ahí entra a bandeja de entrada. Si Himalaya del VPS manda por una casilla
sin esa configuración, termina en spam. Compara las dos por ese criterio —entregabilidad y
qué dominio firma— y recomiéndame una.

Cuida dos cosas al hacerlo:

- **La API key no pasa por la línea de comandos ni por el historial.** Déjala en el VPS en un
  archivo con `chmod 600` o en una variable de entorno que el script lea. Ojo: `read -rs`
  **no funciona** dentro del `!` de Claude Code —ese shell no es interactivo, el read falla
  y un `&&` corta la cadena en silencio—; hay que correrlo en la Terminal de verdad.
- **La lista blanca de destinatarios sigue siendo el punto**. Que el agente pueda mandar
  correo no significa que pueda mandárselo a cualquiera, y menos a una dirección que
  encontró dentro de un correo que estaba leyendo.

Las pruebas ya existen: `CorreoSinShell` en `test_latido.py` (nueve casos) cubre que sin
config avisa y no manda, que un alias fuera de la lista o una dirección cruda se rechazan,
que el archivo se consume aunque se rechace, que el cuerpo va en archivo y que el temporal
no queda tirado. **Lo que falta** es una prueba de que el programa de correo fallando
—código de salida distinto de cero, o timeout de 60 s— no tumba el latido: el código lo
maneja, pero nadie lo afirma. Agrégala, y una para el script nuevo si tiene lógica propia.

## 3 · Que el intake de Blaeind también avise por correo

Eso no es para esta sesión: vive en otro repo y tiene su propio prompt en
`prompt-blaeind-correo.md`, al lado de este archivo. Lánzalo desde `~/Desarrollos/Blaeind`
cuando toque.

## Cómo quiero que trabajes

Verifica antes de afirmar. Este repo tiene varias cosas escritas pero no enchufadas —el
correo es una— y la diferencia entre «está implementado» y «está funcionando» es justo lo
que se pierde si te fías del código sin correrlo. Y lo que está en el VPS no está en el
repo: lo que no puedas comprobar desde acá, pregúntamelo en vez de suponerlo.

Y si en algún momento el trabajo se convierte en construir infraestructura, dímelo: mi
restricción real no es técnica.
