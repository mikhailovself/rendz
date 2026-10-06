'use strict';
/**
 * rendz - поиск официальных клипов на самые популярные сейчас треки.
 * Чарты Apple Music по странам -> поиск на YouTube -> проверка "официальный" -> проверка, что видео можно встроить.
 * Только встроенный fetch (Node 18+), без зависимостей.
 */

// [код страны Apple Music, название, вес]. Россия - в первую очередь.
const COUNTRIES = [
  ['ru', 'Россия', 46], ['us', 'США', 14], ['kr', 'Корея', 8], ['gb', 'Британия', 6],
  ['jp', 'Япония', 5], ['de', 'Германия', 4], ['br', 'Бразилия', 4], ['fr', 'Франция', 3],
  ['tr', 'Турция', 3], ['kz', 'Казахстан', 3], ['it', 'Италия', 2], ['es', 'Испания', 2],
];

const CHART_SIZE = 40;          // сколько позиций чарта рассматриваем
const CHART_TTL = 6 * 3600e3;   // как долго держим чарт в памяти
const CHART_COOLDOWN = 10 * 60e3; // страну с недоступным чартом откладываем
const FRESH_DAYS = 120;         // свежие релизы выпадают чаще
const HTTP_TIMEOUT = 6000;
const SEARCH_BUDGET = 8000;     // сколько времени одному запросу на поиск клипа (мс)

const FALLBACK_QUERIES = [
  'премьера клипа', 'новый клип', 'official video русский', 'русский рэп клип',
  'official music video', 'official video', 'new music video', 'kpop MV',
];
// sp-параметр YouTube: сортировка по просмотрам, за эту неделю, только видео
const SP_HTML = 'CAMSBAgDEAE%253D';
const SP_API = 'CAMSBAgDEAE=';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';

// слова, по которым отсеиваем неофициальное
const BAD_RE = new RegExp(
  '(?<![\\p{L}\\p{N}_])(lyrics?|lyric video|текст|караоке|karaoke|cover|кавер|reaction|реакция|slowed|' +
  'sped up|speed up|nightcore|8d|instrumental|минус|tutorial|разбор|обзор|remix|ремикс|live|' +
  'concert|концерт|teaser|тизер|shorts|fan ?made|fanmade|full album|mix)(?![\\p{L}\\p{N}_])', 'iu');
// каналы лейблов и официальные площадки
const LABEL_RE = new RegExp(
  '(vevo|warner|sony music|universal music|atlantic records|republic records|interscope|def jam|' +
  'columbia records|rca records|capitol|island records|emi |hybe|sm town|smtown|jyp|yg entertainment|' +
  '1thek|ador|pledis|starship|cube entertainment|zhara|black star|gazgolder|first music|' +
  'первое музыкальное|яндекс музыка|yandex music|вк музыка|stream records|ghetto|booking machine|' +
  'bomba|бомба|rhymes music)', 'i');
const MARKERS = new Set(['official', 'клип', 'mv', 'премьера', 'видео', 'video']);

// ------------------------------------------------------------------ утилиты
const norm = (s) => (s || '').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function wpick(items, weights) {
  const total = weights.reduce((a, b) => a + b, 0);
  let x = Math.random() * total;
  for (let i = 0; i < items.length; i++) {
    x -= weights[i];
    if (x <= 0) return items[i];
  }
  return items[items.length - 1];
}

async function fetchT(url, opts = {}, ms = HTTP_TIMEOUT) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: ctl.signal });
  } finally {
    clearTimeout(t);
  }
}

async function getJson(url, opts = {}) {
  const r = await fetchT(url, { headers: { 'User-Agent': UA, ...(opts.headers || {}) } });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ------------------------------------------------------------------ чарты
function splitArtists(raw) {
  const s = (raw || '').replace(/^\s*by\s+/i, '');
  return s.split(/\s*(?:,|&|\bfeat\.?|\bft\.?)\s*/i).map((x) => x.trim()).filter(Boolean);
}
const cleanTitle = (n) => (n || '').replace(/\s*[(\[].*?[)\]]/g, '').trim();

function mkTrack(code, rank, id, artistRaw, name, released) {
  const artists = splitArtists(artistRaw);
  return {
    key: `${code}:${id}`,
    rank,
    artists,
    names: artists.map(norm).filter(Boolean),
    title: cleanTitle(name),
    released: (released || '').slice(0, 10),
  };
}

async function fetchChart(code) {
  const errs = [];
  for (const host of ['rss.applemarketingtools.com', 'rss.marketingtools.apple.com']) {
    try {
      const d = await getJson(`https://${host}/api/v2/${code}/music/most-played/${CHART_SIZE}/songs.json`);
      return d.feed.results.map((it, i) => mkTrack(code, i + 1, it.id, it.artistName, it.name, it.releaseDate));
    } catch (e) { errs.push(`${host}: ${e.message}`); }
  }
  try { // старый формат iTunes
    const d = await getJson(`https://itunes.apple.com/${code}/rss/topsongs/limit=${CHART_SIZE}/json`);
    return d.feed.entry.map((e, i) => mkTrack(code, i + 1, e.id.attributes['im:id'], e['im:artist'].label,
      e['im:name'].label, e['im:releaseDate'] && e['im:releaseDate'].label));
  } catch (e) { errs.push(`itunes: ${e.message}`); }
  throw new Error(errs.join('; '));
}

const chartCache = new Map();   // код -> {t, tracks}
const chartBadUntil = new Map(); // код -> время

async function loadChart(code) {
  const c = chartCache.get(code);
  if (c && Date.now() - c.t < CHART_TTL) return c.tracks;
  const tracks = await fetchChart(code);
  chartCache.set(code, { t: Date.now(), tracks });
  return tracks;
}

function trackWeight(t) {
  let w = 1 / (t.rank + 4); // чем выше в чарте, тем чаще
  const age = (Date.now() - Date.parse(t.released)) / 86400e3;
  if (Number.isFinite(age) && age <= FRESH_DAYS) w *= 3; // свежие релизы - заметно чаще
  return w;
}

// ------------------------------------------------------------------ поиск на YouTube
function parseDur(s) {
  if (!s) return null;
  const p = String(s).split(':').map(Number);
  if (p.some(Number.isNaN)) return null;
  return p.reduce((a, b) => a * 60 + b, 0);
}

function toEntry(vr) {
  const text = (o) => (o && (o.simpleText || (o.runs || []).map((r) => r.text).join(''))) || '';
  const owner = vr.ownerText || vr.longBylineText || vr.shortBylineText;
  return {
    id: vr.videoId,
    title: text(vr.title),
    channel: text(owner),
    verified: (vr.ownerBadges || []).some((b) => /VERIFIED|OFFICIAL_ARTIST/.test(JSON.stringify(b))),
    duration: parseDur(vr.lengthText && vr.lengthText.simpleText),
  };
}

function parseSearch(data) {
  const out = [];
  (function walk(o) {
    if (!o || typeof o !== 'object') return;
    if (o.videoRenderer && o.videoRenderer.videoId) { out.push(toEntry(o.videoRenderer)); return; }
    for (const k in o) walk(o[k]);
  })(data);
  return out;
}

async function ytSearchHtml(query, week) {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}&hl=en${week ? `&sp=${SP_HTML}` : ''}`;
  const r = await fetchT(url, {
    headers: {
      'User-Agent': UA,
      'Accept-Language': 'en-US,en;q=0.9',
      Cookie: 'SOCS=CAI; CONSENT=YES+cb.20210328-17-p0.en+FX+417',
    },
  });
  if (!r.ok) throw new Error(`youtube HTTP ${r.status}`);
  const html = await r.text();
  const m = html.match(/var ytInitialData = (\{.*?\});<\/script>/s);
  if (!m) throw new Error('youtube: нет данных поиска');
  return parseSearch(JSON.parse(m[1]));
}

async function ytSearchInnertube(query, week) {
  const body = {
    context: { client: { clientName: 'WEB', clientVersion: '2.20240601.00.00', hl: 'en', gl: 'US' } },
    query,
  };
  if (week) body.params = SP_API;
  const r = await fetchT('https://www.youtube.com/youtubei/v1/search?prettyPrint=false', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'User-Agent': UA },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`youtube api HTTP ${r.status}`);
  return parseSearch(await r.json());
}

const isoSec = (s) => {
  const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(s || '');
  return m ? (+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0) : null;
};

// Официальный YouTube Data API - если задан ключ YT_API_KEY (надёжнее, чем разбор страницы)
async function ytSearchKey(query, key, week) {
  const u = new URL('https://www.googleapis.com/youtube/v3/search');
  const q = { part: 'snippet', type: 'video', videoEmbeddable: 'true', videoCategoryId: '10', maxResults: '12', q: query, key };
  if (week) {
    q.order = 'viewCount';
    q.publishedAfter = new Date(Date.now() - 7 * 86400e3).toISOString();
  }
  for (const k in q) u.searchParams.set(k, q[k]);
  const j = await getJson(u.toString());
  const ids = (j.items || []).map((i) => i.id.videoId).filter(Boolean);
  if (!ids.length) return [];
  const d = await getJson(`https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id=${ids.join(',')}&key=${key}`);
  const dur = new Map((d.items || []).map((v) => [v.id, isoSec(v.contentDetails.duration)]));
  return j.items.map((i) => ({
    id: i.id.videoId, title: i.snippet.title, channel: i.snippet.channelTitle,
    verified: false, duration: dur.get(i.id.videoId) ?? null,
  }));
}

async function ytSearch(query, week = false) {
  const attempts = [];
  if (process.env.YT_API_KEY) attempts.push(() => ytSearchKey(query, process.env.YT_API_KEY, week));
  attempts.push(() => ytSearchHtml(query, week), () => ytSearchInnertube(query, week));
  let last;
  for (const f of attempts) {
    try { const r = await f(); if (r.length) return r; } catch (e) { last = e; }
  }
  if (last) throw last;
  return [];
}

// можно ли встроить видео на чужом сайте (oEmbed отвечает 401/403 для запрещённых)
async function isEmbeddable(id) {
  try {
    const r = await fetchT(`https://www.youtube.com/oembed?format=json&url=${encodeURIComponent('https://www.youtube.com/watch?v=' + id)}`,
      { headers: { 'User-Agent': UA } }, 4000);
    return r.ok;
  } catch { return true; } // сеть подвела - решит плеер на странице
}

// ------------------------------------------------------------------ "официальный клип"
const titleMarker = (t) => t.split(' ').some((w) => MARKERS.has(w));
const isTopic = (ch) => ch === 'topic' || ch.endsWith(' topic');

function channelIsOfficial(e, track) {
  const ch = norm(e.channel);
  if (!ch || isTopic(ch)) return false;
  const title = norm(e.title);
  const inChannel = track.names.some((n) => n.length >= 3 && (ch.includes(n) || (ch.length >= 3 && n.includes(ch))));
  const inTitle = track.names.some((n) => title.includes(n));
  if (inChannel || ch.includes('vevo') || LABEL_RE.test(ch)) return true;
  return !!(e.verified && (titleMarker(title) || inTitle));
}

function pickOfficial(entries, track) {
  const name = norm(track.title);
  const good = [];
  entries.forEach((e, idx) => {
    const raw = e.title || '';
    const title = norm(raw);
    if (BAD_RE.test(raw)) return;
    if (e.duration && !(e.duration >= 60 && e.duration <= 720)) return;
    if (isTopic(norm(e.channel))) return;
    const marker = titleMarker(title);
    const nameOk = !!name && title.includes(name);
    const artistInTitle = track.names.some((n) => title.includes(n));
    // название трека может быть на другом алфавите (корейский, японский) - тогда смотрим на артиста
    if (!(nameOk || (artistInTitle && marker))) return;
    if (!(channelIsOfficial(e, track) || marker)) return;
    good.push([marker ? 0 : 1, idx, e]);
  });
  if (!good.length) return null;
  good.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  return good[0][2];
}

// ------------------------------------------------------------------ сборка клипа
function pickTrack(seen) {
  const now = Date.now();
  const options = COUNTRIES.filter((c) => (chartBadUntil.get(c[0]) || 0) < now);
  return options.length ? wpick(options, options.map((c) => c[2])) : null;
}

async function chartClip(seen, log) {
  const c = pickTrack(seen);
  if (!c) return null;
  const [code, country] = c;
  let chart;
  try { chart = await loadChart(code); } catch (e) {
    chartBadUntil.set(code, Date.now() + CHART_COOLDOWN);
    log(`чарт «${country}» не загрузился: ${e.message}`);
    return null;
  }
  const tracks = chart.filter((t) => !seen.has(t.key));
  if (!tracks.length) return null;
  const track = wpick(tracks, tracks.map(trackWeight));
  seen.add(track.key); // в рамках этого запроса не берём повторно
  log(`${country} №${track.rank}: ${track.artists.join(', ')} — ${track.title}`);
  const entries = await ytSearch(`${track.artists.slice(0, 2).join(', ')} ${track.title} official video`);
  const hit = pickOfficial(entries, track);
  if (!hit || seen.has(hit.id)) { log('  официального клипа не нашёл'); return null; }
  if (!(await isEmbeddable(hit.id))) { log('  встраивание запрещено'); return null; }
  return {
    id: hit.id, key: track.key, title: track.title, artist: track.artists.join(', '),
    chip: `${country} · №${track.rank} в чарте`,
  };
}

async function fallbackClip(seen, log) {
  const q = FALLBACK_QUERIES[Math.floor(Math.random() * FALLBACK_QUERIES.length)];
  log(`ищу на YouTube популярное за неделю: «${q}»`);
  const entries = (await ytSearch(q, true)).slice(0, 15).sort(() => Math.random() - 0.5);
  for (const e of entries) {
    const title = norm(e.title);
    const ch = norm(e.channel);
    if (BAD_RE.test(e.title) || isTopic(ch) || seen.has(e.id)) continue;
    if (e.duration && !(e.duration >= 60 && e.duration <= 720)) continue;
    if (!(titleMarker(title) || e.verified || LABEL_RE.test(ch))) continue;
    if (!(await isEmbeddable(e.id))) continue;
    return {
      id: e.id, title: cleanTitle(e.title.replace(/\(?\s*official.*$/i, '')) || e.title,
      artist: e.channel, chip: 'YouTube · популярное за неделю',
    };
  }
  return null;
}

/** Находит один подходящий клип. seen - множество уже показанных id видео и ключей треков. */
async function findClip(seen = new Set(), budget = SEARCH_BUDGET) {
  const t0 = Date.now();
  const lines = [];
  const log = (m) => lines.push(m);
  let misses = 0;
  let lastErr = '';
  while (Date.now() - t0 < budget) {
    try {
      const clip = misses >= 2 && misses % 2 === 0 ? await fallbackClip(seen, log) : await chartClip(seen, log);
      if (clip) return clip;
      misses++;
    } catch (e) {
      lastErr = e.message;
      misses++;
      await sleep(250);
    }
  }
  return { error: lastErr || 'клип не найден, попробуй ещё раз', log: lines.slice(-6) };
}

module.exports = { findClip, pickOfficial, parseSearch, mkTrack, norm, isEmbeddable, COUNTRIES };
