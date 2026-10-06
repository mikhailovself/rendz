"""GET /api/find — подбирает один клип (YouTube-ID) под настройки. Без состояния и без yt-dlp."""
import json, os, random, re, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _data import *  # noqa: E402,F401,F403
from _data import (CIS, OTHER, CIS_SET, LISTED, COUNTRY_NAMES, CAT_LABEL, MIX_WEIGHTS, GENRES, GENRE_IDS, GENRE_LABELS,  # noqa: E402
                   GENRE_QUERIES, LEGENDS_RAW, CHART_SIZE, NEW_DAYS, NEW_DAYS_WIDE, POP_MIN_AGE, MIN_DUR, MAX_DUR,
                   CYR_RE, LABEL_RE, norm, has, clean_title, is_bad_text, title_marker, eval_candidate, _track)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def http(url, timeout=3.5):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8",
                                               "Cookie": "CONSENT=YES+1; SOCS=CAI"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def classify(genres):
    keys = []
    for g in genres or []:
        k = GENRE_IDS.get(str(g.get("genreId")))
        if k and k not in keys:
            keys.append(k)
        for key, _l, rx in GENRES:
            if key not in keys and rx.search(g.get("name") or ""):
                keys.append(key)
    return keys


_charts = {}


def chart(code):
    c = _charts.get(code)
    if c and time.time() - c[0] < 6 * 3600:
        return c[1]
    err = None
    for host in ("rss.applemarketingtools.com", "rss.marketingtools.apple.com"):
        try:
            d = json.loads(http(f"https://{host}/api/v2/{code}/music/most-played/{CHART_SIZE}/songs.json"))
            tr = [_track(f"am:{it['id']}", it.get("artistName", ""), clean_title(it.get("name", "")),
                         it.get("releaseDate"), classify(it.get("genres")), i)
                  for i, it in enumerate(d["feed"]["results"], 1)]
            _charts[code] = (time.time(), tr)
            return tr
        except Exception as e:  # noqa: BLE001
            err = e
    raise err


LEG = []
for _ln in LEGENDS_RAW.splitlines():
    _ln = _ln.strip()
    if not _ln or _ln.startswith("#"):
        continue
    p = [x.strip() for x in _ln.split("|")]
    if len(p) < 3:
        continue
    y = p[3] if len(p) > 3 and p[3].isdigit() else ""
    g = p[4] if len(p) > 4 and p[4] in GENRE_LABELS else ""
    LEG.append(_track(f"lg:{norm(p[0])}:{norm(p[1])}", p[0], p[1], f"{y}-01-01" if y else "", [g] if g else [],
                      origin=p[2].lower(), legend=True))


def yt_search(q):
    html = http("https://www.youtube.com/results?hl=en&search_query=" + quote_plus(q), 4)
    m = re.search(r"ytInitialData\s*=\s*(\{.+?\});\s*</script>", html, re.S)
    if not m:
        return []
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("videoRenderer", {}).get("videoId"):
                found.append(o["videoRenderer"])
            else:
                for v in o.values():
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json.loads(m.group(1)))
    out = []
    for v in found[:15]:
        txt = lambda k: "".join(r.get("text", "") for r in ((v.get(k) or {}).get("runs") or []))  # noqa: E731
        dur = 0
        for x in ((v.get("lengthText") or {}).get("simpleText") or "").split(":"):
            dur = dur * 60 + int(x) if x.isdigit() else dur
        out.append({"src": "yt", "id": v["videoId"], "title": txt("title"), "channel": txt("ownerText"), "duration": dur,
                    "verified": "VERIFIED" in json.dumps(v.get("ownerBadges") or [])})
    return out


def embeddable(vid):
    try:
        http("https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + vid, 2.5)
        return True
    except urllib.error.HTTPError:
        return False
    except Exception:  # noqa: BLE001
        return True


def rt_search(q):
    d = json.loads(http("https://rutube.ru/api/search/video/?" + urlencode({"query": q, "format": "json"}), 3.5))
    out = []
    for r in (d.get("results") or [])[:15]:
        if not r.get("id") or r.get("is_hidden") or r.get("is_adult"):
            continue
        a = r.get("author") or {}
        out.append({"src": "rt", "id": r["id"], "title": r.get("title") or "", "channel": a.get("name") or "",
                    "duration": int(r.get("duration") or 0), "verified": bool(a.get("is_official") or r.get("is_official")),
                    "thumb": r.get("thumbnail_url") or ""})
    return out


def dm_search(q):
    d = json.loads(http("https://api.dailymotion.com/videos?" + urlencode({
        "search": q, "fields": "id,title,duration,owner.screenname,owner.verified,thumbnail_360_url", "limit": 15, "sort": "relevance"}), 3.5))
    return [{"src": "dm", "id": r["id"], "title": r.get("title") or "", "channel": r.get("owner.screenname") or "",
             "duration": int(r.get("duration") or 0), "verified": bool(r.get("owner.verified")),
             "thumb": r.get("thumbnail_360_url") or ""} for r in d.get("list") or [] if r.get("id")]


SEARCH = {"yt": yt_search, "rt": rt_search, "dm": dm_search}
PAGE = {"yt": "https://www.youtube.com/watch?v=", "rt": "https://rutube.ru/video/", "dm": "https://www.dailymotion.com/video/"}


def rank(found, tr, srcs):
    out = []
    for i, v in enumerate(found):
        ev = eval_candidate(v, tr)
        if ev:
            out.append(((0 if ev[0] else 1, 0 if ev[1] else 1, srcs.index(v["src"]), i), v))
    out.sort(key=lambda x: x[0])
    return out


def candidates(q, srcs, tr):
    pool = ThreadPoolExecutor(len(srcs))
    pend, found, end, got = {pool.submit(SEARCH[s], q) for s in srcs}, [], time.time() + 4.5, False
    try:
        while pend and time.time() < end:
            done, pend = wait(pend, timeout=max(0.1, end - time.time()), return_when=FIRST_COMPLETED)
            for f in done:
                try:
                    r = f.result()
                    found += r
                    if r and not got:   # первый ответ есть — остальным даём не больше секунды
                        got, end = True, min(end, time.time() + 1.0)
                except Exception:  # noqa: BLE001
                    pass
            rk = rank(found, tr, srcs)
            if rk and rk[0][0][0] == 0 and rk[0][1]["src"] == srcs[0]:   # официальный клип с главной площадки — не ждём остальных
                break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return rank(found, tr, srcs)


def ok_embed(v):
    return embeddable(v["id"]) if v["src"] == "yt" else True


def age(t):
    try:
        return (date.today() - datetime.strptime(t["released"], "%Y-%m-%d").date()).days
    except Exception:  # noqa: BLE001
        return None


def in_cat(t, cat, nd=NEW_DAYS):
    a = age(t)
    return (a is not None and a <= nd) if cat == "new" else (a is None or a > POP_MIN_AGE) if cat == "popular" else True


def allowed(code, c):
    if code in LISTED:
        return code in c["cis"] or (not c["only"] and code in c["other"])
    return code in CIS_SET or (bool(code) and not c["only"])


def pick_chart(cat, c):
    opts = [x for x in CIS if x[0] in c["cis"]] + ([] if c["only"] else [x for x in OTHER if x[0] in c["other"]])
    for _ in range(6):
        if not opts:
            return None
        code = random.choices(opts, [x[2] for x in opts])[0][0]
        try:
            ch = chart(code)
        except Exception:  # noqa: BLE001
            continue
        cand = [t for t in ch if t["key"] not in c["ex"] and not set(t["names"]) & c["bad"]]
        if c["genres"]:
            cand = [t for t in cand if c["genres"] & set(t["genres"])]
        if c["only"]:   # страну артиста по чарту не узнать — в режиме «только СНГ» берём кириллицу
            cand = [t for t in cand if CYR_RE.search(t["artist_raw"] + t["title"])]
        pool = [t for t in cand if in_cat(t, cat)]
        if cat == "new" and len(pool) < 3:
            pool = [t for t in cand if in_cat(t, cat, NEW_DAYS_WIDE)]
        if pool:
            t = random.choices(pool, [1 / (x["rank"] + 4) for x in pool])[0]
            c["ex"].add(t["key"])
            return dict(t, origin="ru" if CYR_RE.search(t["artist_raw"]) else code)
    return None


def pick_legend(c):
    cand = [t for t in LEG if t["key"] not in c["ex"] and allowed(t["origin"], c) and not set(t["names"]) & c["bad"]
            and (not c["genres"] or c["genres"] & set(t["genres"]))]
    t = random.choice(cand) if cand else None
    if t:
        c["ex"].add(t["key"])
    return t


def build(v, tr, chip):
    src = v.get("src", "yt")
    return {"id": src + ":" + v["id"], "vid": v["id"], "src": src, "key": tr["key"], "title": tr["title"],
            "artist": ", ".join(tr["artists"]), "chip": chip, "names": tr["names"], "genres": tr["genres"],
            "country": tr.get("origin", ""), "tags": [GENRE_LABELS[g] for g in tr["genres"] if g in GENRE_LABELS][:3],
            "url": PAGE[src] + v["id"] + ("/" if src == "rt" else ""),
            "thumb": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg" if src == "yt" else v.get("thumb", "")}


def chip(cat, tr):
    parts = [CAT_LABEL.get(cat, "")]
    parts.append(tr["released"][:4] if tr.get("legend") else (f"№{tr['rank']}" if tr.get("rank") else ""))
    parts.append(COUNTRY_NAMES.get(tr.get("origin"), ""))
    return " · ".join(p for p in parts if p)


def clip_for(tr, cat, c):
    c["ex"].add(tr["key"])
    q = f"{', '.join(tr['artists'][:2])} {tr['title']}"
    top = [v for _k, v in candidates(q + (" клип" if CYR_RE.search(q) else " official video"), c["srcs"], tr)[:3]]
    if not top:
        return None
    with ThreadPoolExecutor(len(top)) as pool:
        oks = list(pool.map(ok_embed, top))
    for v, ok in zip(top, oks):
        if ok:
            return build(v, tr, chip(cat, tr))
    return None


def generic(queries, c, cat, must=None):
    cands = SEARCH[random.choice(c["srcs"])](random.choice(queries))
    random.shuffle(cands)
    for v in cands:
        t = v["title"]
        ch = norm(v["channel"])
        if not t or is_bad_text(t) or ch.endswith(" topic") or not (MIN_DUR <= (v["duration"] or MIN_DUR) <= MAX_DUR):
            continue
        if not (title_marker(norm(t)) or v["verified"] or LABEL_RE.search(ch)):
            continue
        if must and not (has(norm(t), must) or has(ch, must)):
            continue
        if c["only"] and not CYR_RE.search(t + v["channel"]):
            continue
        a, n = v["channel"], t
        m = re.match(r"^\s*(.+?)\s+[-–—]\s+(.+)$", t)
        if m:
            a, n = m.group(1), m.group(2)
        n = clean_title(re.sub(r"(?i)\b(official\s+(?:music\s+)?video|official|клип)\b", "", n)).strip(" -–—|") or t
        tr = _track(v["src"] + ":" + v["id"], a, n)
        if tr["key"] in c["ex"] or not ok_embed(v):
            continue
        return build(v, tr, f"Ещё от {must.title()}" if must else CAT_LABEL.get(cat, ""))
    return None


def make(q):
    S = lambda k: {x for x in q.get(k, "").split("|" if k in ("ex", "bad") else ",") if x}  # noqa: E731
    c = {"only": q.get("only") == "1", "cis": S("cis"), "other": S("other"), "genres": S("genres"), "ex": S("ex"), "bad": S("bad"),
         "srcs": [x for x in q.get("src", "yt").split(",") if x in SEARCH] or ["yt"]}
    end, errs = time.time() + 22, []

    def one(n):
        cat = q.get("cat", "mix")
        if cat == "mix":
            cat = random.choices(list(MIX_WEIGHTS), list(MIX_WEIGHTS.values()))[0]
        try:
            clip = None
            if q.get("fav") and n == 0:
                clip = generic([q["fav"] + " official video"], c, "fav", must=q["fav"])
            if not clip:
                tr = pick_legend(c) if cat == "legend" else pick_chart(cat, c)
                clip = clip_for(tr, cat, c) if tr else None
            if not clip and n >= 3 and cat != "legend":
                qs = [x for g in c["genres"] for x in GENRE_QUERIES.get(g, [])] or (
                    ["премьера клипа", "новый клип", "официальный клип"] if c["only"] else ["official music video", "новый клип"])
                clip = generic(qs, c, cat)
            return clip
        except Exception as e:  # noqa: BLE001
            errs.append(str(e))
            return None

    pool = ThreadPoolExecutor(4)
    pending, nxt = {pool.submit(one, i) for i in range(3)}, 3
    try:
        while pending and time.time() < end:
            done, pending = wait(pending, timeout=max(0.1, end - time.time()), return_when=FIRST_COMPLETED)
            for f in done:
                if f.result():
                    return f.result()
                if nxt < 10:
                    pending.add(pool.submit(one, nxt))
                    nxt += 1
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    last = errs[-1] if errs else ""
    return {"error": "Не нашёл клип" + (f" ({last[:120]})" if last else "") + ". Нажми «Повторить» или расширь настройки (⚙)."}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try:
            out = make(q)
        except Exception as e:  # noqa: BLE001
            out = {"error": str(e)[:200]}
        body = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
