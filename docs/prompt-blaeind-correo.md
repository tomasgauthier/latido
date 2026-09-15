# Prompt: que el intake de Blaeind también avise por correo

Lánzala desde `~/Desarrollos/Blaeind`, que es donde vive el repo. Sale del prompt de
latido (`prompt-latido.md`), donde estaba de más: es otro repo y otra sesión.

---

Hoy `api/_aviso.js` avisa por Telegram cuando alguien guarda su intake: manda el nombre del
cliente y el enlace al panel, con 4 s de espera y sin propagar errores, porque perder el
aviso molesta pero perder el intake no se puede. Funciona y está probado en producción. Usa
**el mismo bot** que latido y bolsillo (el comentario del archivo lo dice), solo para
enviar: no choca con nada.

Lo que falta no es duplicarlo: **Telegram dice «llegó», el correo debería decir «esto
dijo»**. Hoy, para leer las respuestas hay que entrar al panel. Un correo desde
`blaeind.com` —`verified` en Resend, con DKIM, SPF de envío y DMARC ya puestos— puede traer
las tres respuestas del intake completas y ahorrarse ese viaje.

Tres advertencias:

- **No metas el enlace con el token del cliente en un correo que no sea para Tomás.** Esa
  URL es la credencial de acceso del cliente.
- El aviso es un extra: si el correo falla, el intake ya se guardó y eso es lo que no se
  puede perder. Misma política que tiene hoy el aviso de Telegram.
- La key va como variable de entorno del proyecto de Blaeind en Vercel, y se crea en **mi**
  cuenta de Resend (la del MCP `resend-personal`). Nunca una de ECR: restricción 4.
