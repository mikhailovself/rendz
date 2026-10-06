'use strict';
// Эндпоинт GET /api/clip?ex=id1,id2,... -> {id, title, artist, chip, key} или {error}
// Работает как функция Vercel и как обработчик локального server.js.
const { findClip } = require('../lib/finder');

module.exports = async function handler(req, res) {
  const u = new URL(req.url, 'http://localhost');
  const seen = new Set((u.searchParams.get('ex') || '').split(',').map((s) => s.trim()).filter(Boolean).slice(-120));
  let out;
  try {
    out = await findClip(seen);
  } catch (e) {
    out = { error: String((e && e.message) || e) };
  }
  res.statusCode = out.error ? 503 : 200;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(out));
};
