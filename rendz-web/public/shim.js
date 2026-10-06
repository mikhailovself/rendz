// Заменяет pywebview.api: настройки и вкусы — в localStorage, клипы — через /api/find
(() => {
  const K = 'rendz.';
  const rd = (k, d) => { try { const v = localStorage.getItem(K + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
  const wr = (k, v) => { try { localStorage.setItem(K + k, JSON.stringify(v)); } catch (e) {} };
  window.gestured = false;
  const g = () => { if (window.gestured) return; window.gestured = true; try { applyVol(); } catch (e) {} };
  ['pointerdown', 'keydown', 'touchstart'].forEach(e => addEventListener(e, g, {capture: true}));
  window.ytReady = new Promise(r => { window.onYouTubeIframeAPIReady = r; });
  const t = document.createElement('script'); t.src = 'https://www.youtube.com/iframe_api'; document.head.appendChild(t);

  let O, settings, first = false, seen = [], metas = {}, done = new Set();
  let P = rd('profile', {artists: {}, genres: {}, countries: {}, liked: [], disliked: []});
  const sanitize = r => {
    r = r || {};
    const pick = (all, v) => all.filter(x => (v || []).includes(x));
    const s = {cis_only: !!r.cis_only, cis: pick(O.cis.map(x => x[0]), r.cis || O.defaults.cis),
      other: pick(O.other.map(x => x[0]), r.other || O.defaults.other), genres: pick(O.genres.map(x => x[0]), r.genres),
      category: ['mix', 'new', 'popular', 'legend'].includes(r.category) ? r.category : 'mix',
      sources: ['yt'], autonext: r.autonext !== false, vk_token: ''};
    if (!s.cis.length && (s.cis_only || !s.other.length)) s.cis = ['ru'];
    return s;
  };
  const core = s => { const c = {...s}; delete c.autonext; return JSON.stringify(c); };
  const eff = r => r > 0 ? r : r * 1.5;
  const bump = (tb, k, d) => { tb[k] = Math.max(-6, Math.min(6, (tb[k] || 0) + d)); };
  const spread = (m, w) => {
    (m.names || []).forEach(n => bump(P.artists, n, w));
    (m.genres || []).forEach(x => bump(P.genres, x, w * .5));
    if (m.country) bump(P.countries, m.country, w * .3);
  };
  const save = () => wr('profile', P);

  const api = {
    async get_state(){
      O = await (await fetch('options.json')).json();
      const raw = rd('settings', null); first = !raw; settings = sanitize(raw);
      return {settings, first_run: first, options: O};
    },
    async save_settings(raw){
      const n = sanitize(raw), changed = core(n) !== core(settings);
      settings = n; wr('settings', n); if (changed) seen = [];
      return {settings: n, changed};
    },
    async next_clip(){
      const s = settings, bad = Object.keys(P.artists).filter(k => P.artists[k] <= -3);
      const favs = Object.entries(P.artists).filter(e => e[1] >= 1.5).sort((a, b) => b[1] - a[1]).slice(0, 20);
      const p = new URLSearchParams({cat: s.category, only: s.cis_only ? 1 : 0, cis: s.cis.join(), other: s.other.join(),
        genres: s.genres.join(), bad: bad.join('|'), ex: seen.slice(-60).concat(P.disliked.slice(-60)).join('|')});
      if (s.category === 'mix' && favs.length && Math.random() < .15) p.set('fav', favs[Math.floor(Math.random() * favs.length)][0]);
      let err = '';
      for (let i = 0; i < 2; i++){
        try {
          const j = await (await fetch('/api/find?' + p)).json();
          if (j.error){ err = j.error; continue; }
          if (seen.includes(j.key)){ continue; }
          seen.push(j.key); metas[j.id] = {key: j.key, names: j.names, genres: j.genres, country: j.country, url: j.url, rating: 0};
          return j;
        } catch (e) { err = String(e); }
      }
      return {error: err || 'Клип не найден. Нажми «Повторить».'};
    },
    async rate(id, r){
      const m = metas[id]; if (!m) return false;
      const old = m.rating || 0; if (old === r) return true;
      m.rating = r; spread(m, eff(r) - eff(old));
      P.disliked = P.disliked.filter(k => k !== m.key); P.liked = P.liked.filter(k => k !== m.key);
      if (r === -1) P.disliked.push(m.key); if (r === 1) P.liked.push(m.key);
      save(); return true;
    },
    async watch(id, secs, dur){
      const m = metas[id]; if (!m || done.has(id) || m.rating || dur <= 0) return false;
      const w = secs / dur >= .85 ? .35 : (secs < 4 ? -.4 : 0); if (!w) return false;
      done.add(id); spread(m, w); save(); return true;
    },
    async playback(){ return true; },
    async get_stats(){ return {likes: P.liked.length, dislikes: P.disliked.length}; },
    async reset_profile(){ P = {artists: {}, genres: {}, countries: {}, liked: [], disliked: []}; save(); return true; },
    open_browser(id){ const m = metas[id]; if (m) window.open(m.url, '_blank', 'noopener'); },
    async toggle_fullscreen(){
      try { document.fullscreenElement ? await document.exitFullscreen() : await document.documentElement.requestFullscreen(); } catch (e) {}
      return true;
    }
  };
  window.pywebview = {api};
  addEventListener('load', () => window.dispatchEvent(new Event('pywebviewready')));
})();
