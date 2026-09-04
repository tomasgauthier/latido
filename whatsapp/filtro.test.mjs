import { test } from 'node:test';
import assert from 'node:assert/strict';
import { esMio, filtrar } from './filtro.js';

const YO = { id: '56912345678:23@s.whatsapp.net', lid: '67427329167522:23@lid' };
const MARCA = '⏱ *Latido*\n────────────\n';
const base = { fromMe: true, jid: '56912345678@s.whatsapp.net', texto: 'hola',
               id: 'A1', mios: new Set(), marca: MARCA, yo: YO };

test('tu número y tu LID son los dos el mismo chat', () => {
  assert.ok(esMio('56912345678@s.whatsapp.net', YO));
  assert.ok(esMio('67427329167522@lid', YO));
  assert.ok(esMio('56912345678:23@s.whatsapp.net', YO));   // con dispositivo
});

test('el chat de otro no es el tuyo', () => {
  assert.ok(!esMio('56999999999@s.whatsapp.net', YO));
  assert.ok(!esMio('120363000@g.us', YO));
  assert.ok(!esMio('', YO));
});

test('lo tuyo pasa', () => assert.equal(filtrar(base), null));

test('lo de un desconocido no pasa aunque escriba a tu número', () =>
  assert.equal(filtrar({ ...base, fromMe: false }), 'ajeno'));

test('un grupo tuyo tampoco pasa', () =>
  assert.equal(filtrar({ ...base, jid: '120363000@g.us' }), 'otro-chat'));

test('lo que mandó este mismo proceso no vuelve a entrar', () =>
  assert.equal(filtrar({ ...base, mios: new Set(['A1']) }), 'eco'));

test('lo que mandó el proceso de antes tampoco: para eso está la marca', () =>
  assert.equal(filtrar({ ...base, texto: MARCA + 'algo', mios: new Set() }), 'eco'));

test('sin las dos redes se contestaría solo', () =>
  assert.equal(filtrar({ ...base, texto: MARCA + 'algo', marca: '' }), null));

test('un mensaje vacío no despierta nada', () =>
  assert.equal(filtrar({ ...base, texto: '   ' }), 'vacio'));
