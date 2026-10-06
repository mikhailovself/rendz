'use strict';
// Локальный запуск: node server.js  ->  http://localhost:3000
// Без зависимостей, нужен только Node.js 18+.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const clip = require('./api/clip');

const PUBLIC = path.join(__dirname, 'public');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.ico': 'image/x-icon', '.svg': 'image/svg+xml', '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
};

const server = http.createServer((req, res) => {
  const { pathname } = new URL(req.url, 'http://localhost');
  if (pathname === '/api/clip') return clip(req, res);

  const rel = decodeURIComponent(pathname === '/' ? '/index.html' : pathname);
  const file = path.normalize(path.join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC)) { res.statusCode = 403; return res.end('403'); }
  fs.readFile(file, (err, data) => {
    if (err) { res.statusCode = 404; return res.end('404'); }
    res.setHeader('Content-Type', TYPES[path.extname(file)] || 'application/octet-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.end(data);
  });
});

function openBrowser(url) {
  if (process.env.NO_OPEN) return;
  const [cmd, args] =
    process.platform === 'win32' ? ['cmd', ['/c', 'start', '""', url]] :
    process.platform === 'darwin' ? ['open', [url]] : ['xdg-open', [url]];
  try { spawn(cmd, args, { stdio: 'ignore', detached: true }).on('error', () => {}).unref(); } catch { /* ignore */ }
}

function listen(port, tries = 0) {
  server.once('error', (e) => {
    if (e.code === 'EADDRINUSE' && tries < 10) listen(port + 1, tries + 1);
    else { console.error('Не удалось запустить сервер:', e.message); process.exit(1); }
  });
  server.listen(port, '127.0.0.1', () => {
    const url = `http://localhost:${port}`;
    console.log(`\n  rendz запущен: ${url}\n  Закрой это окно, чтобы остановить.\n`);
    openBrowser(url);
  });
}

listen(Number(process.env.PORT) || 3000);
