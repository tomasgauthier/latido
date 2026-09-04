/**
 * El puente de WhatsApp.
 *
 * Habla la API de bots de Telegram —los cinco métodos que latido usa— y por
 * dentro es Baileys. Así el latido no se entera de por dónde habla: cambia
 * una URL en config.json y todo lo demás sigue igual.
 *
 * Va contra el "chat contigo mismo", igual que Hermes: te vinculas por QR como
 * un dispositivo más, y el único chat que existe para el puente es el tuyo con
 * tu propio número. Nadie más entra, ni puede.
 *
 *   node puente.js --parear    vincula por QR y anota tu JID en config.json
 *   node puente.js             deja el puente escuchando
 */

import { makeWASocket, useMultiFileAuthState, DisconnectReason,
         fetchLatestBaileysVersion, jidNormalizedUser } from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';
import pino from 'pino';   // lo trae Baileys igual, pero se declara
import http from 'node:http';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { readFileSync, writeFileSync, chmodSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { esMio as _esMio, filtrar } from './filtro.js';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const CONFIG = path.join(AQUI, '..', 'config.json');
const SESION = path.join(AQUI, 'sesion');
const PAREAR = process.argv.includes('--parear');

// Lo que va delante de cada cosa que dice el latido. Hace dos trabajos, y el
// segundo es el que importa: en un chat contigo mismo, lo que manda el puente
// vuelve a entrar como mensaje tuyo. Esta marca es cómo se reconoce a sí mismo
// después de reiniciarse, cuando la lista de ids que mandó ya se perdió.
const MARCA = '⏱ *Latido*\n────────────\n';

const log = (...a) => console.log(`[${new Date().toTimeString().slice(0, 8)}]`, ...a);

function config() {
  return JSON.parse(readFileSync(CONFIG, 'utf8'));
}

function guardar(cfg) {
  writeFileSync(CONFIG, JSON.stringify(cfg, null, 2) + '\n');
  chmodSync(CONFIG, 0o600);   // lleva el token: no se relaja al reescribirlo
}

// ── Lo que ya mandó ────────────────────────────────────────────────────────
// Un mensaje que manda el puente vuelve como mensaje entrante marcado
// `fromMe`: en un chat contigo mismo no hay otra cosa. Sin esto el latido se
// contesta a sí mismo para siempre. Se limita el tamaño porque es memoria que
// nadie vacía.
const mios = new Set();
function recordar(id) {
  if (!id) return;
  mios.add(id);
  while (mios.size > 512) mios.delete(mios.values().next().value);
}

// ── La cola de entrada ─────────────────────────────────────────────────────
// getUpdates de Telegram: cada mensaje lleva un número que sube, y el que
// pregunta confirma lo leído mandando el siguiente en `offset`. Se replica tal
// cual para que escucha.py no note la diferencia.
// ponytail: la cola vive en memoria. Si el puente se cae entre que escribes y
// que la oreja pregunta, ese mensaje se perdió. Persistirla es un archivo más
// que mantener a la par de `.offset`; se hace si alguna vez duele.
let cola = [];
let siguiente = 1;
let esperando = [];        // peticiones getUpdates abiertas, esperando algo

function encolar(texto, jid) {
  cola.push({ update_id: siguiente++, message: { text: texto, chat: { id: jid } } });
  if (cola.length > 100) cola.shift();   // nadie está leyendo: no crezcas sin fin
  for (const despertar of esperando.splice(0)) despertar();
}

// ── WhatsApp ───────────────────────────────────────────────────────────────
let sock = null;
let estado = 'desconectado';
let mio = null;            // tu JID normalizado: el único chat que existe acá

// Todos los envíos en fila india. Dos sendMessage a la vez sobre el mismo
// socket pueden entregarse cruzados, y acá hay tres cosas que escriben:
// el mensaje, el "escribiendo…" y el aviso de progreso.
let fila = Promise.resolve();
function enFila(fn) {
  const tarea = fila.then(fn, fn);
  fila = tarea.catch(() => {});   // la fila sigue aunque uno falle
  return tarea;                   // pero el que llamó SÍ se entera
}

const esMio = (jid) => _esMio(jid, sock?.user);

async function conectar() {
  const { state, saveCreds } = await useMultiFileAuthState(SESION);
  let version;
  try { ({ version } = await fetchLatestBaileysVersion()); } catch {}

  sock = makeWASocket({
    ...(version ? { version } : {}),
    auth: state,
    logger: pino({ level: 'silent' }),
    printQRInTerminal: false,
    browser: ['Latido', 'Chrome', '120.0'],
    syncFullHistory: false,
    markOnlineOnConnect: false,      // que no te marque en línea a las 4am
    // Sin esto, en Baileys 7 los mensajes que necesitan rehacer la sesión
    // cifrada llegan vacíos y se pierden sin ruido.
    getMessage: async () => ({ conversation: '' }),
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log('\n📱 Escanea esto desde WhatsApp → Dispositivos vinculados:\n');
      qrcode.generate(qr, { small: true });
      console.log('\nEsperando…\n');
    }

    if (connection === 'open') {
      estado = 'conectado';
      mio = jidNormalizedUser(sock.user.id);
      log('conectado como', mio);
      if (PAREAR) return parear();
    }

    if (connection === 'close') {
      estado = 'desconectado';
      const razon = lastDisconnect?.error?.output?.statusCode;
      if (razon === DisconnectReason.loggedOut) {
        // Cerraron la sesión desde el teléfono. Reintentar es pedir un QR
        // nuevo cada tres segundos para siempre, y quien nos revive lo haría
        // eterno. Se sale con CERO a propósito: el agente está puesto para
        // revivir solo cuando el puente se cae, y un cero le dice "terminé".
        // Que se note es trabajo del interruptor de hombre muerto: sin puente
        // el latido no logra hablar y `.ultimo` deja de moverse.
        log('sesión cerrada desde el teléfono. Borra whatsapp/sesion y vuelve a parear.');
        process.exit(0);
      }
      // 515 es "reinicia", y es lo normal justo después de parear.
      const espera = razon === 515 ? 1000 : 3000;
      log(`conexión caída (${razon}); reintento en ${espera / 1000}s`);
      setTimeout(() => conectar().catch((e) => log('no pude reconectar:', e.message)), espera);
    }
  });

  sock.ev.on('messages.upsert', ({ messages, type }) => {
    // En el chat contigo mismo tus mensajes llegan como 'append' tanto como
    // 'notify', según por dónde entren.
    if (type !== 'notify' && type !== 'append') return;

    for (const m of messages) {
      const jid = m.key?.remoteJid;
      const texto = m.message?.conversation
                 || m.message?.extendedTextMessage?.text || '';

      const razon = filtrar({ fromMe: m.key?.fromMe, jid, texto,
                              id: m.key?.id, mios, marca: MARCA, yo: sock?.user });
      if (razon === 'ajeno' || razon === 'otro-chat') {
        log(`mensaje descartado sin leerse (${razon})`);
        continue;
      }
      if (razon) continue;              // eco propio o vacío: ni vale anotarlo

      encolar(texto.trim(), mio);
    }
  });
}

function parear() {
  const cfg = config();
  const wa = cfg.whatsapp || (cfg.whatsapp = {});
  wa.chat_id = mio;
  wa.token = wa.token || randomBytes(24).toString('hex');
  wa.api = wa.api || 'http://127.0.0.1:8738/bot{}/{}';
  guardar(cfg);
  console.log(`\n✅ listo. Tu chat: ${mio}`);
  console.log('   Anotado en config.json. Prende el latido desde la página.\n');
  process.exit(0);
}

// ── La cara de Telegram ────────────────────────────────────────────────────
const wa = config().whatsapp || {};
const TOKEN = wa.token || '';
const PUERTO = Number(new URL((wa.api || 'http://127.0.0.1:8738/bot{}/{}')
                              .replace(/\{\}/g, 'x')).port) || 8738;

function responder(res, cuerpo) {
  const b = JSON.stringify(cuerpo);
  res.writeHead(200, { 'content-type': 'application/json',
                       'content-length': Buffer.byteLength(b) });
  res.end(b);
}

async function metodo(nombre, p) {
  if (nombre === 'getUpdates') {
    let desde = Number(p.get('offset') || 0);
    if (desde > siguiente) desde = 0;   // offset de otro canal, o el puente reinició
    const techo = Math.min(Number(p.get('timeout') || 0), 50) * 1000;
    cola = cola.filter((u) => u.update_id >= desde);   // lo confirmado se va
    if (!cola.length && techo) {
      // Se deja la petición abierta, como el long poll de Telegram: esperar
      // así no cuesta nada y el latido sale al instante cuando escribes.
      await new Promise((listo) => {
        const despertar = () => {
          clearTimeout(t);
          // indexOf da -1 si `encolar` ya lo sacó, y splice(-1,1) sobre un
          // arreglo vacío no hace nada: por eso no se comprueba.
          const i = esperando.indexOf(despertar);
          if (i >= 0) esperando.splice(i, 1);
          listo();
        };
        const t = setTimeout(despertar, techo);
        esperando.push(despertar);
      });
    }
    return { ok: true, result: cola.filter((u) => u.update_id >= desde) };
  }

  // Solo se le habla a tu propio chat. El latido manda el chat_id que tiene en
  // config.json; si por lo que sea no es el tuyo, no sale nada.
  const jid = p.get('chat_id');
  if (estado !== 'conectado') return { ok: false, description: 'sin conexión a WhatsApp' };
  if (!jid || !esMio(jid)) return { ok: false, description: 'ese chat no es el tuyo' };

  if (nombre === 'sendChatAction') {
    await enFila(() => sock.sendPresenceUpdate('composing', mio));
    return { ok: true, result: true };
  }

  if (nombre === 'sendMessage') {
    const enviado = await enFila(() => sock.sendMessage(mio, { text: MARCA + (p.get('text') || '') }));
    recordar(enviado?.key?.id);
    return { ok: true, result: { message_id: enviado?.key?.id } };
  }

  if (nombre === 'editMessageText') {
    const key = { id: p.get('message_id'), fromMe: true, remoteJid: mio };
    const enviado = await enFila(() => sock.sendMessage(mio, { text: MARCA + (p.get('text') || ''), edit: key }));
    recordar(enviado?.key?.id);
    return { ok: true, result: { message_id: p.get('message_id') } };
  }

  if (nombre === 'deleteMessage') {
    const key = { id: p.get('message_id'), fromMe: true, remoteJid: mio };
    await enFila(() => sock.sendMessage(mio, { delete: key }));
    return { ok: true, result: true };
  }

  return { ok: false, description: `método desconocido: ${nombre}` };
}

const servidor = http.createServer(async (req, res) => {
  // Escucha en 127.0.0.1, pero eso no basta: un navegador con una página
  // cualquiera abierta puede mandarle peticiones. El Host tiene que ser el
  // loopback, y el token va en la ruta como en Telegram.
  const host = (req.headers.host || '').split(':')[0];
  if (host !== '127.0.0.1' && host !== 'localhost') {
    return responder(res, { ok: false, description: 'solo loopback' });
  }

  const url = new URL(req.url, 'http://127.0.0.1');
  const m = url.pathname.match(/^\/bot([^/]+)\/([A-Za-z]+)$/);
  if (!m || !TOKEN || m[1] !== TOKEN) {
    return responder(res, { ok: false, description: 'llave equivocada' });
  }

  let cuerpo = '';
  for await (const t of req) {
    cuerpo += t;
    if (cuerpo.length > 1e6) return req.destroy();   // nadie manda tanto
  }
  const p = new URLSearchParams(cuerpo || url.search);

  try {
    responder(res, await metodo(m[2], p));
  } catch (e) {
    responder(res, { ok: false, description: String(e?.message || e) });
  }
});

if (PAREAR) {
  console.log('📱 vinculando. Session:', SESION, '\n');
  conectar().catch((e) => { console.error(e); process.exit(1); });
} else if (!TOKEN) {
  console.error('sin parear todavía: corre `node puente.js --parear`');
  process.exit(1);
} else {
  servidor.listen(PUERTO, '127.0.0.1', () => {
    log(`puente en 127.0.0.1:${PUERTO} — solo tu chat contigo mismo`);
    conectar().catch((e) => { log('no pude conectar:', e.message); process.exit(1); });
  });
}
