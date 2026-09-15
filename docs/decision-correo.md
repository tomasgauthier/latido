# Decisión: SMTP actual vs Resend para el correo del agente

Investigación de solo lectura, 2026-09-15. Todo lo de la sección DNS es
literal (`dig`), comprobado desde este Mac. Lo demás distingue comprobado de supuesto.

## 1. Lo que devolvió el DNS

| Consulta | Resultado |
|---|---|
| `TXT gauthier.cl` (SPF, filtrado) | `v=spf1 include:_spf.mailersend.net include:_spf.mx.cloudflare.net include:icloud.com ~all` |
| `TXT _dmarc.gauthier.cl` | `v=DMARC1; p=none; rua=mailto:...@dmarc-reports.cloudflare.net` — **sin `sp=`** |
| `MX gauthier.cl` | `10 mx01.mail.icloud.com` / `10 mx02.mail.icloud.com` |
| `TXT/CNAME *._domainkey.gauthier.cl` probados: `mta`, `mta1`, `mta2`, `mlsend1`, `mlsend2`, `ms1`, `ms2`, `mailersend`, `default`, `dkim`, `google` | **ninguno existe** |
| `CNAME sig1._domainkey.gauthier.cl` | **sí existe** → apunta a `sig1.dkim.gauthier.cl.at.icloudmailadmin.com` (DKIM de Apple/iCloud, dominio personalizado) |
| `TXT envios.gauthier.cl` (SPF) | vacío — no hay registro en la raíz del subdominio |
| `TXT _dmarc.envios.gauthier.cl` | vacío — no tiene DMARC propio |
| `TXT resend._domainkey.envios.gauthier.cl` (DKIM) | **existe**, clave RSA válida de Resend |
| `TXT send.envios.gauthier.cl` (SPF de retorno de Resend) | `v=spf1 include:amazonses.com ~all` |
| `MX send.envios.gauthier.cl` | `10 feedback-smtp.sa-east-1.amazonses.com` — confirma región `sa-east-1` |

## 2. Diagnóstico

**Resend / `envios.gauthier.cl`**: DKIM y SPF están completos y correctamente
encadenados (Resend corre sobre AWS SES; el SPF de retorno vive en
`send.envios.gauthier.cl`, el DKIM en la raíz del subdominio). Ambos alinean
en modo relajado con el dominio organizacional `gauthier.cl`. Autenticación
objetivamente sólida.

**SMTP actual / `agente@gauthier.cl`**: acá hay un hallazgo, no una certeza.
El SPF de `gauthier.cl` incluye `_spf.mailersend.net`, lo que sugiere que el
envío pasa por MailerSend — pero **no encontré ningún selector DKIM de
MailerSend publicado** (probé los nombres típicos, incluido `mta`, que es el
que usa por convención). Si `correo.py` efectivamente manda por MailerSend,
hoy sale **sin DKIM alineado a gauthier.cl**. El único DKIM real que hay en
el dominio es el de Apple/iCloud (`sig1`), ligado al feature de "dominio
personalizado" de iCloud Mail — probablemente para el correo personal de
Tomás en Apple Mail, no necesariamente para lo que dispara un script en el
VPS. **No pude confirmar cuál de los dos usa `correo.py` sin leer ese
archivo, que vive en el VPS y quedó fuera de alcance por la restricción de
esta tarea.**

Con `p=none` y sin `sp=`, la política de DMARC de `gauthier.cl` cubre
también a `envios.gauthier.cl` (heredada) y a cualquier otro subdominio: hoy
nada se rechaza ni se pone en cuarentena por política propia. Eso no es
"todo bien" — es que el dominio no está forzando nada, así que la
entregabilidad depende enteramente de si SPF/DKIM alinean en cada envío. Si
el SMTP actual manda por MailerSend sin DKIM, y el SPF de MailerSend no
alinea con el `Return-Path` real de gauthier.cl, ese correo puede estar
pasando hoy con **cero mecanismo alineado** — lo cual, aunque `p=none` no lo
rechace, sí lo hace ver "menos confiable" para los filtros de Gmail/Outlook,
que califican por señales propias más allá de la política DMARC publicada.

## 3. El costo de migrar a Resend

Confirmado leyendo `latido.py`: `despachar_correo()` (línea 406) arma el
comando como `[conf["bin"]] + args`, donde `args` sale de `CORREO_ARGS`
(línea 296) o de `conf["args"]` — plantilla `["--para", "{para}", "--asunto",
"{asunto}", "--texto", "{cuerpo}"]`. `{cuerpo}` se reemplaza por la **ruta de
un archivo temporal** (línea 457-462), nunca por el texto crudo. Migrar de
SMTP a Resend no toca `latido.py`: solo hay que apuntar `correo.bin` de la
config a un programa nuevo que acepte esos mismos tres flags.

**Pero** hay un freno real: `correo.py` también manda `.ics` como
`text/calendar; method=REQUEST`. Según un issue abierto en el repo de Resend
(`resend/resend-node#198`), la API de Resend no expone forma de fijar el
parámetro `method=REQUEST` en el `Content-Type` del adjunto — Gmail suele
reconocer igual el `.ics`, pero Outlook no, porque exige ese parámetro
explícito. Migrar completo degradaría las invitaciones de calendario para
cualquier destinatario en Outlook.

## 4. Recomendación

**No migrar todavía a Resend en bloque.** Primero: confirmar (leyendo
`correo.py` en el VPS, sin necesidad de tocarlo, solo leerlo) qué SMTP usa
hoy de verdad. Si es MailerSend, el arreglo más barato es agregar sus dos
CNAME de DKIM (selector `mta` por omisión, se sacan gratis del panel de
MailerSend) a la zona `gauthier.cl` — cinco minutos, cero código, cero
migración, y cierra la brecha de alineación sin arriesgar el `.ics`.

Si más adelante se quiere de todas formas pasar a Resend por comodidad
operativa (API HTTP en vez de credenciales SMTP en el VPS), lo prudente es
un híbrido: correo de texto por Resend/`envios.gauthier.cl` (ya está
perfecto en DKIM+SPF), y las invitaciones `.ics` se quedan en el camino
SMTP actual hasta que Resend soporte `method=REQUEST` o se confirme que
todos los destinatarios de esas invitaciones usan Gmail.

**Qué se pierde con esta recomendación**: por ahora, no se gana la
comodidad de una sola API HTTP para todo el correo del agente, y sigue
habiendo una pieza (el SMTP real que usa `correo.py`) que no quedó
verificada en esta sesión por no poder leer el archivo en el VPS.
