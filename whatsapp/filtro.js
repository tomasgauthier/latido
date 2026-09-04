/**
 * Quién entra y quién no. Sin Baileys a propósito: es la lógica que no puede
 * fallar —un mensaje propio que vuelve a entrar es un latido contestándose a
 * sí mismo para siempre— y así se prueba sin levantar nada.
 */

/** ¿Este chat es el tuyo contigo mismo?
 *
 * WhatsApp nombra la misma cuenta de dos maneras, el número de siempre y un
 * LID, y cuál llega depende del mensaje. Vale cualquiera: mirando solo una,
 * la mitad de tus propios mensajes se irían a la basura como ajenos.
 */
export function esMio(jid, yo) {
  const pelado = (v) => String(v || '').replace(/:.*@/, '@').replace(/@.*/, '');
  const mios = [pelado(yo?.id), pelado(yo?.lid)].filter(Boolean);
  const suyo = pelado(jid);
  return Boolean(suyo) && mios.includes(suyo);
}

/** Qué hacer con un mensaje que llegó. Devuelve por qué se descarta, o null
 *  si hay que procesarlo. */
export function filtrar({ fromMe, jid, texto, id, mios, marca, yo }) {
  // Se falla cerrado, igual que el chat_id de Telegram: acá solo existe tu
  // chat contigo mismo. Lo que entra va al prompt de un agente que lee tus
  // archivos, así que un grupo o un desconocido no pasan ni por error.
  if (!fromMe) return 'ajeno';
  if (!esMio(jid, yo)) return 'otro-chat';
  // Dos redes para lo mismo. Los ids atrapan lo que mandó este proceso; la
  // marca atrapa lo que mandó el proceso de antes, cuando la lista de ids se
  // fue con el reinicio y solo queda el texto para reconocerse.
  if (mios?.has?.(id)) return 'eco';
  if (marca && String(texto || '').startsWith(marca)) return 'eco';
  if (!String(texto || '').trim()) return 'vacio';
  return null;
}
