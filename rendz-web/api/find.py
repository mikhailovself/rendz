"""GET /api/find — подбирает один клип (YouTube-ID) под настройки. Без состояния и без yt-dlp."""
import json, os, random, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote_plus, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _data import *  # noqa: E402,F401,F403
from _data import (CIS, OTHER, CIS_SET, LISTED, COUNTRY_NAMES, CAT_LABEL, MIX_WEIGHTS, GENRES, GENRE_IDS, GENRE_LABELS,  # noqa: E402
                   GENRE_QUERIES, LEGENDS_RAW, CHART_SIZE, NEW_DAYS, NEW_DAYS_WIDE, POP_MIN_AGE, MIN_DUR, MAX_DUR,
                   CYR_RE, LABEL_RE, norm, has, clean_title, is_bad_text, title_marker, eval_candidate, _track)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def http(url, timeout=6):
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
    html = http("https://www.youtube.com/results?hl=en&search_query=" + quote_plus(q), 8)
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
        out.append({"id": v["videoId"], "title": txt("title"), "channel": txt("ownerText"), "duration": dur,
                    "verified": "VERIFIED" in json.dumps(v.get("ownerBadges") or [])})
    return out


def embeddable(vid):
    try:
        http("https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + vid, 4)
        return True
    except urllib.error.HTTPError:
        return False
    except Exception:  # noqa: BLE001
        return True


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
            return dict(t, origin="ru" if CYR_RE.search(t["artist_raw"]) else code)
    return None


def pick_legend(c):
    cand = [t for t in LEG if t["key"] not in c["ex"] and allowed(t["origin"], c) and not set(t["names"]) & c["bad"]
            and (not c["genres"] or c["genres"] & set(t["genres"]))]
    return random.choice(cand) if cand else None


def build(v, tr, chip):
    return {"id": "yt:" + v["id"], "vid": v["id"], "key": tr["key"], "title": tr["title"], "artist": ", ".join(tr["artists"]),
            "chip": chip, "names": tr["names"], "genres": tr["genres"], "country": tr.get("origin", ""),
            "tags": [GENRE_LABELS[g] for g in tr["genres"] if g in GENRE_LABELS][:3],
            "url": "https://www.youtube.com/watch?v=" + v["id"]}


def chip(cat, tr):
    parts = [CAT_LABEL.get(cat, "")]
    parts.append(tr["released"][:4] if tr.get("legend") else (f"№{tr['rank']}" if tr.get("rank") else ""))
    parts.append(COUNTRY_NAMES.get(tr.get("origin"), ""))
    return " · ".join(p for p in parts if p)


def clip_for(tr, cat, c):
    c["ex"].add(tr["key"])
    q = f"{', '.join(tr['artists'][:2])} {tr['title']}"
    ranked = []
    for i, v in enumerate(yt_search(q + (" клип" if CYR_RE.search(q) else " official video"))):
        ev = eval_candidate(v, tr)
        if ev:
            ranked.append((0 if ev[0] else 1, 0 if ev[1] else 1, i, v))
    ranked.sort(key=lambda x: x[:3])
    for *_r, v in ranked[:3]:
        if embeddable(v["id"]):
            return build(v, tr, chip(cat, tr))
    return None


def generic(queries, c, cat, must=None):
    cands = yt_search(random.choice(queries))
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
        tr = _track("yt:" + v["id"], a, n)
        if tr["key"] in c["ex"] or not embeddable(v["id"]):
            continue
        return build(v, tr, f"Ещё от {must.title()}" if must else CAT_LABEL.get(cat, ""))
    return None


def make(q):
    S = lambda k: {x for x in q.get(k, "").split("|" if k in ("ex", "bad") else ",") if x}  # noqa: E731
    c = {"only": q.get("only") == "1", "cis": S("cis"), "other": S("other"), "genres": S("genres"), "ex": S("ex"), "bad": S("bad")}
    end, last = time.time() + 24, ""
    for n in range(8):
        if time.time() > end:
            break
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
            if clip:
                return clip
        except Exception as e:  # noqa: BLE001
            last = str(e)
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
