import re, math

# (код страны Apple Music, название, вес). Россия - в первую очередь.
CIS = [
    ("ru", "Россия", 40),
    ("kz", "Казахстан", 8),
    ("by", "Беларусь", 6),
    ("ua", "Украина", 6),
    ("uz", "Узбекистан", 5),
    ("am", "Армения", 3),
    ("az", "Азербайджан", 3),
    ("kg", "Киргизия", 2),
    ("md", "Молдова", 2),
]
OTHER = [
    ("us", "США", 14),
    ("kr", "Корея", 8),
    ("gb", "Британия", 6),
    ("jp", "Япония", 5),
    ("de", "Германия", 4),
    ("br", "Бразилия", 4),
    ("fr", "Франция", 3),
    ("tr", "Турция", 3),
    ("mx", "Мексика", 3),
    ("in", "Индия", 3),
    ("it", "Италия", 2),
    ("es", "Испания", 2),
    ("ca", "Канада", 2),
    ("au", "Австралия", 2),
    ("pl", "Польша", 2),
]
COUNTRY_NAMES = {c[0]: c[1] for c in CIS + OTHER}

# жанры: (ключ, подпись, регулярка по названию жанра из Apple Music на любом языке)
GENRES = [
    ("pop", "Поп", r"(?<!\w)pop(?!\w)|(?<!\w)поп(?!\w)|эстрад"),
    ("rap", "Хип-хоп / Рэп", r"hip[\s-]?hop|(?<!\w)rap(?!\w)|рэп|хип|(?<!\w)trap(?!\w)|drill"),
    ("rock", "Рок", r"(?<!\w)rock(?!\w)|(?<!\w)рок(?!\w)|punk|панк"),
    ("metal", "Метал", r"metal|метал"),
    ("electro", "Электроника / Танцы", r"electro|dance|house|techno|(?<!\w)edm(?!\w)|электрон|танцев|транс|trance|dubstep"),
    ("rnb", "R&B / Соул", r"r&b|r&amp;b|r\s?n\s?b|soul|соул"),
    ("alt", "Альтернатива / Инди", r"alternativ|indie|инди|альтернатив"),
    ("latin", "Латино", r"latin|reggaeton|urbano|salsa|bachata|латин|mexican|regional"),
    ("kpop", "K-Pop", r"k-?pop"),
    ("jpop", "J-Pop", r"j-?pop|anime|аниме"),
    ("country", "Кантри", r"country|кантри"),
    ("chanson", "Шансон / Бард", r"chanson|шансон|(?<!\w)bard|бард"),
]
GENRES = [(k, label, re.compile(rx, re.I)) for k, label, rx in GENRES]
GENRE_LABELS = {k: label for k, label, _ in GENRES}
# стабильные id жанров Apple Music
GENRE_IDS = {"14": "pop", "18": "rap", "21": "rock", "1153": "metal", "7": "electro", "17": "electro",
             "15": "rnb", "20": "alt", "12": "latin", "51": "kpop", "27": "jpop", "6": "country"}

# поиск на YouTube по жанрам (запасной путь, если чарты недоступны или в них нет нужного жанра)
GENRE_QUERIES = {
    "pop": ["поп клип премьера", "pop official video"],
    "rap": ["русский рэп клип", "rap official video"],
    "rock": ["рок клип official", "rock official video"],
    "metal": ["metal official video"],
    "electro": ["electronic official video", "dance official video"],
    "rnb": ["r&b official video"],
    "alt": ["инди клип", "indie official video"],
    "latin": ["reggaeton official video", "latino video oficial"],
    "kpop": ["kpop MV official"],
    "jpop": ["jpop MV official"],
    "country": ["country official video"],
    "chanson": ["шансон клип", "русский шансон клип"],
}


COUNTRY_NAMES.update({
    "tj": "Таджикистан", "tm": "Туркменистан", "ge": "Грузия", "se": "Швеция", "no": "Норвегия",
    "ie": "Ирландия", "pr": "Пуэрто-Рико", "co": "Колумбия", "bb": "Барбадос", "dk": "Дания",
    "be": "Бельгия", "nl": "Нидерланды", "pt": "Португалия", "ar": "Аргентина", "cl": "Чили",
})
COUNTRY_W = {c[0]: c[2] for c in CIS + OTHER}
CIS_SET = {"ru", "kz", "by", "ua", "uz", "am", "az", "kg", "md", "tj", "tm"}
LISTED = {c[0] for c in CIS + OTHER}

CATEGORIES = [("mix", "Всё"), ("new", "Новинки"), ("popular", "Популярное"), ("legend", "Легендарки")]
CAT_KEYS = [k for k, _ in CATEGORIES]
CAT_LABEL = {"new": "Новинка", "popular": "Популярное", "legend": "Легендарка"}
MIX_WEIGHTS = {"new": 4, "popular": 4, "legend": 2}

SOURCES = [("yt", "YouTube"), ("vk", "VK Видео"), ("rt", "Rutube"), ("dm", "Dailymotion")]
SOURCE_KEYS = [k for k, _ in SOURCES]

DEFAULT_SETTINGS = {
    "cis_only": False,
    "cis": [c[0] for c in CIS],
    "other": ["us", "kr", "gb", "jp", "de", "br", "fr", "tr", "it", "es"],
    "genres": [],
    "category": "mix",
    "sources": list(SOURCE_KEYS),
    "autonext": True,
    "vk_token": "",
}

CHART_SIZE = 100           # сколько позиций чарта рассматриваем
CHART_TTL = 6 * 3600       # как долго держим чарт (сек)
NEW_DAYS = 60              # "новинка" - вышла не раньше этого
NEW_DAYS_WIDE = 150        # если новинок в чарте мало
POP_MIN_AGE = 150          # "популярное" - в чарте и вышло давно
READY_TARGET = 4           # сколько клипов готовим заранее
WORKERS = 6                # параллельных "искателей" клипов
STREAM_MAX_AGE = 4 * 3600  # ссылки на видео живут несколько часов
GET_TIMEOUT = 45
CHART_COOLDOWN = 600
HTTP_TIMEOUT = 6
SEARCH_TIMEOUT = 9         # общий лимит на поиск клипа по всем площадкам
MIN_DUR, MAX_DUR = 90, 540  # клип: от 1.5 до 9 минут
EXPLORE_RATE = 0.10        # доля треков мимо вкусов
FAV_RATE = 0.15            # доля клипов "ещё от любимого артиста" (во вкладке «Всё»)

# sp=...: сортировка по просмотрам + период + только видео
SP_WEEK = "CAMSBAgDEAE%253D"
SP_YEAR = "CAMSBAgFEAE%253D"

MARKER_WORDS = {"official", "клип", "mv", "премьера", "видео", "video", "clip"}

# --- что НЕ является музыкальным клипом: лирик-видео, аудио, live, каверы, ремиксы, нарезки и т.д.
BAD_RE = re.compile(
    r"(?<!\w)(?:lyrics?|lyric video|lyrical|с текстом|текст|караоке|karaoke|reaction|реакция|"
    r"slowed|reverb|sped up|speed up|nightcore|8d|instrumental|минусовка|tutorial|разбор|обзор|"
    r"remix|ремикс|mashup|megamix|playlist|compilation|подборка|сборник|shorts|fan ?made|fanmade|"
    r"full album|official audio|audio only|visuali[sz]er|art ?track|behind the scenes|making of|"
    r"dance practice|choreography|teaser|тизер|trailer|трейлер|concert|концерт|acoustic|акустика|"
    r"акустическая|cover by|cover version|кавер|piano version|vertical video)(?!\w)",
    re.I,
)
AUDIO_RE = re.compile(r"[\(\[]\s*(?:official\s+)?audio\s*[\)\]]|(?<!\w)аудио(?!\w)|(?<!\w)audio\s*$", re.I)
LIVE_RE = re.compile(
    r"[\(\[|]\s*live\b|(?<!\w)live\s*[\)\]]|(?<!\w)live\s+(?:at|from|in|on|session|sessions|performance|"
    r"version|stream|concert)\b|(?<!\w)лайв(?!\w)|(?<!\w)live$",
    re.I,
)
# ИИ-клипы и ИИ-музыка (по названию и каналу)
AI_TITLE_RE = re.compile(
    r"(?<!\w)(?:ai[\s\-_]*(?:generated|made|cover|music|song|video|clip|art|version|remix|vocals?|voice|mv)|"
    r"(?:generated|made|created|produced)\s+(?:by|with|using)\s+ai|suno(?:\s*ai)?|нейро\w*|нейросет\w*|"
    r"искусственн\w+\s+интеллект\w*|сгенерирован\w*|ии[\s\-_]*(?:клип|кавер|версия|музыка|песня))(?!\w)",
    re.I,
)
# ... и по описанию / тегам ролика
AI_DESC_RE = re.compile(
    r"(?<!\w)(?:suno|midjourney|stable diffusion|udio\.com|kling ai|runway ml|ai[\s\-]generated|ai[\s\-]made|"
    r"generated\s+(?:by|with|using)\s+ai|(?:made|created|produced)\s+(?:by|with|using)\s+ai|"
    r"ai\s+(?:cover|voice|song|music video|music)|artificial intelligence|deepfake|нейросет\w*)",
    re.I,
)
# каналы лейблов / официальные площадки
LABEL_RE = re.compile(
    r"(vevo|warner|sony music|universal music|atlantic records|republic records|interscope|"
    r"def jam|columbia records|rca records|capitol|island records|emi |hybe|sm town|smtown|"
    r"jyp|yg entertainment|1thek|ador|pledis|starship|cube entertainment|zhara|black star|"
    r"gazgolder|first music|первое музыкальное|яндекс музыка|yandex music|вк музыка|vk музыка|"
    r"stream records|ghetto|booking machine|bomba|бомба|rhymes music|velvet music|союз|soyuz|"
    r"kontora|believe|bmg|the orchard|atlantic russia|moroz records|мороз records)",
    re.I,
)
CYR_RE = re.compile(r"[\u0400-\u04FF]")

LEGENDS_RAW = """
# артист | трек | страна | год | жанр
Michael Jackson|Thriller|us|1983|pop
Michael Jackson|Billie Jean|us|1983|pop
Michael Jackson|Beat It|us|1983|pop
Michael Jackson|Smooth Criminal|us|1988|pop
Michael Jackson|Black or White|us|1991|pop
Queen|Bohemian Rhapsody|gb|1975|rock
Queen|Don't Stop Me Now|gb|1978|rock
Queen|I Want to Break Free|gb|1984|rock
Queen|Radio Ga Ga|gb|1984|rock
Nirvana|Smells Like Teen Spirit|us|1991|rock
Nirvana|Heart-Shaped Box|us|1993|rock
Guns N' Roses|November Rain|us|1992|rock
Guns N' Roses|Sweet Child O' Mine|us|1987|rock
Guns N' Roses|Don't Cry|us|1991|rock
Metallica|Enter Sandman|us|1991|metal
Metallica|Nothing Else Matters|us|1992|metal
AC/DC|Highway to Hell|au|1979|rock
AC/DC|Thunderstruck|au|1990|rock
Aerosmith|Cryin'|us|1993|rock
Aerosmith|I Don't Want to Miss a Thing|us|1998|rock
Bon Jovi|It's My Life|us|2000|rock
Bon Jovi|Livin' on a Prayer|us|1986|rock
Scorpions|Wind of Change|de|1990|rock
Scorpions|Still Loving You|de|1984|rock
a-ha|Take On Me|no|1985|pop
Madonna|Like a Prayer|us|1989|pop
Madonna|Vogue|us|1990|pop
Madonna|Hung Up|us|2005|pop
Prince|Kiss|us|1986|pop
Whitney Houston|I Wanna Dance with Somebody|us|1987|pop
Whitney Houston|I Will Always Love You|us|1992|pop
George Michael|Careless Whisper|gb|1984|pop
Wham!|Last Christmas|gb|1984|pop
Depeche Mode|Enjoy the Silence|gb|1990|electro
Depeche Mode|Personal Jesus|gb|1989|electro
Cyndi Lauper|Girls Just Want to Have Fun|us|1983|pop
Rick Astley|Never Gonna Give You Up|gb|1987|pop
Boney M.|Rasputin|de|1978|pop
ABBA|Dancing Queen|se|1976|pop
ABBA|Mamma Mia|se|1975|pop
Bee Gees|Stayin' Alive|gb|1977|pop
Elton John|I'm Still Standing|gb|1983|pop
Oasis|Wonderwall|gb|1995|rock
Oasis|Don't Look Back in Anger|gb|1995|rock
Blur|Song 2|gb|1997|alt
Radiohead|Creep|gb|1992|alt
The Verve|Bitter Sweet Symphony|gb|1997|alt
Coldplay|Yellow|gb|2000|alt
Coldplay|Viva La Vida|gb|2008|alt
Linkin Park|In the End|us|2001|rock
Linkin Park|Numb|us|2003|rock
Linkin Park|Faint|us|2003|rock
Green Day|Boulevard of Broken Dreams|us|2004|rock
Green Day|Basket Case|us|1994|rock
The Offspring|Pretty Fly|us|1998|rock
Red Hot Chili Peppers|Californication|us|1999|rock
Red Hot Chili Peppers|Under the Bridge|us|1992|rock
System of a Down|Chop Suey!|us|2001|metal
System of a Down|Toxicity|us|2001|metal
Rammstein|Du Hast|de|1997|metal
Rammstein|Sonne|de|2001|metal
Rammstein|Ich Will|de|2001|metal
Rammstein|Mein Herz Brennt|de|2004|metal
Slipknot|Duality|us|2004|metal
Evanescence|Bring Me to Life|us|2003|rock
Lady Gaga|Bad Romance|us|2009|pop
Lady Gaga|Poker Face|us|2008|pop
Katy Perry|Firework|us|2010|pop
Katy Perry|Roar|us|2013|pop
Rihanna|Umbrella|bb|2007|pop
Rihanna|We Found Love|bb|2011|pop
Beyoncé|Single Ladies|us|2008|rnb
Beyoncé|Crazy in Love|us|2003|rnb
Britney Spears|Toxic|us|2003|pop
Britney Spears|...Baby One More Time|us|1998|pop
Shakira|Hips Don't Lie|co|2006|latin
Shakira|Waka Waka|co|2010|latin
Ricky Martin|Livin' la Vida Loca|pr|1999|latin
Luis Fonsi|Despacito|pr|2017|latin
Daddy Yankee|Gasolina|pr|2004|latin
PSY|Gangnam Style|kr|2012|kpop
BTS|Dynamite|kr|2020|kpop
BLACKPINK|DDU-DU DDU-DU|kr|2018|kpop
Eminem|Lose Yourself|us|2002|rap
Eminem|Without Me|us|2002|rap
Eminem|The Real Slim Shady|us|2000|rap
Eminem|Stan|us|2000|rap
Eminem|Love the Way You Lie|us|2010|rap
50 Cent|In da Club|us|2003|rap
Snoop Dogg|Drop It Like It's Hot|us|2004|rap
2Pac|California Love|us|1996|rap
Kanye West|Stronger|us|2007|rap
OutKast|Hey Ya!|us|2003|rap
Daft Punk|Around the World|fr|1997|electro
Daft Punk|One More Time|fr|2000|electro
Daft Punk|Get Lucky|fr|2013|electro
The Prodigy|Firestarter|gb|1996|electro
Aqua|Barbie Girl|dk|1997|pop
Spice Girls|Wannabe|gb|1996|pop
Backstreet Boys|I Want It That Way|us|1999|pop
Avril Lavigne|Complicated|ca|2002|rock
Avril Lavigne|Sk8er Boi|ca|2002|rock
The White Stripes|Seven Nation Army|us|2003|rock
Muse|Supermassive Black Hole|gb|2006|alt
The Killers|Mr. Brightside|us|2004|alt
Arctic Monkeys|Do I Wanna Know?|gb|2013|alt
Amy Winehouse|Rehab|gb|2006|rnb
Adele|Rolling in the Deep|gb|2010|pop
Adele|Hello|gb|2015|pop
Ed Sheeran|Shape of You|gb|2017|pop
Ed Sheeran|Thinking Out Loud|gb|2014|pop
Taylor Swift|Shake It Off|us|2014|pop
Taylor Swift|Blank Space|us|2014|pop
The Weeknd|Blinding Lights|ca|2019|pop
The Weeknd|Starboy|ca|2016|pop
Billie Eilish|bad guy|us|2019|alt
Dua Lipa|Levitating|gb|2020|pop
Gotye|Somebody That I Used to Know|au|2011|alt
Wiz Khalifa|See You Again|us|2015|rap
Imagine Dragons|Radioactive|us|2012|alt
Imagine Dragons|Believer|us|2017|alt
My Chemical Romance|Welcome to the Black Parade|us|2006|rock
Paramore|Misery Business|us|2007|rock
Nickelback|How You Remind Me|ca|2001|rock
Blink-182|All the Small Things|us|1999|rock
Roxette|It Must Have Been Love|se|1990|pop
Ace of Base|The Sign|se|1993|pop
Europe|The Final Countdown|se|1986|rock
Modern Talking|You're My Heart, You're My Soul|de|1985|pop
Scooter|How Much Is the Fish?|de|1998|electro
Bonnie Tyler|Total Eclipse of the Heart|gb|1983|pop
Survivor|Eye of the Tiger|us|1982|rock
Journey|Don't Stop Believin'|us|1981|rock
Toto|Africa|us|1982|rock
Dire Straits|Money for Nothing|gb|1985|rock
The Police|Every Breath You Take|gb|1983|rock
U2|With or Without You|ie|1987|rock
R.E.M.|Losing My Religion|us|1991|alt
Celine Dion|My Heart Will Go On|ca|1997|pop
Mariah Carey|All I Want for Christmas Is You|us|1994|pop
Lana Del Rey|Summertime Sadness|us|2012|alt
Sia|Chandelier|au|2014|pop
Pharrell Williams|Happy|us|2013|pop
Kendrick Lamar|HUMBLE.|us|2017|rap
Drake|Hotline Bling|ca|2015|rap
Justin Timberlake|Cry Me a River|us|2002|pop
Justin Bieber|Baby|ca|2010|pop
Miley Cyrus|Wrecking Ball|us|2013|pop
Avicii|Wake Me Up|se|2013|electro
Swedish House Mafia|Don't You Worry Child|se|2012|electro
Stromae|Alors on danse|be|2009|electro
Stromae|Papaoutai|be|2013|electro
Måneskin|Zitti e buoni|it|2021|rock
Кино|Звезда по имени Солнце|ru|1989|rock
Кино|Группа крови|ru|1988|rock
Ленинград|Экспонат|ru|2016|rock
Ленинград|В Питере — пить|ru|2011|rock
Ленинград|Кабриолет|ru|2013|rock
Мумий Тролль|Владивосток 2000|ru|2000|rock
Мумий Тролль|Медведица|ru|1998|rock
Мумий Тролль|Утекай|ru|1998|rock
Земфира|Ариведерчи|ru|1999|rock
Земфира|Искала|ru|1999|rock
Земфира|Хочешь?|ru|2000|rock
Земфира|До свидания|ru|2000|rock
Сплин|Выхода нет|ru|1998|rock
Сплин|Орбит без сахара|ru|1998|rock
Би-2|Полковнику никто не пишет|ru|2000|rock
Би-2|Мой рок-н-ролл|ru|2000|rock
Ночные Снайперы|31 весна|ru|2000|rock
Звери|Районы-кварталы|ru|2003|pop
Звери|До скорой встречи|ru|2003|pop
Звери|Напиши мне письмо|ru|2007|pop
Наутилус Помпилиус|Я хочу быть с тобой|ru|1986|rock
Алиса|Небо славян|ru|1992|rock
Король и Шут|Лесник|ru|2001|rock
Король и Шут|Кукла колдуна|ru|1999|rock
Король и Шут|Прыгну со скалы|ru|2003|rock
Любэ|Комбат|ru|1996|rock
Любэ|Атас|ru|1993|rock
Любэ|Давай за|ru|1997|rock
Ляпис Трубецкой|Воины света|by|2007|rock
Руки Вверх!|18 мне уже|ru|1998|pop
Руки Вверх!|Крошка моя|ru|1999|pop
t.A.T.u.|Нас не догонят|ru|2001|pop
t.A.T.u.|All the Things She Said|ru|2002|pop
Иванушки International|Тополиный пух|ru|1998|pop
Глюкоза|Невеста|ru|2003|pop
Ласковый май|Белые розы|ru|1988|pop
Мираж|Музыка нас связала|ru|1988|pop
Технология|Нажми на кнопку|ru|1988|electro
Дискотека Авария|Новогодняя|ru|2001|electro
Фабрика|Про любовь|ru|2003|pop
Ирина Аллегрова|Угонщица|ru|1998|pop
Серебро|Мама Люба|ru|2011|pop
Серебро|Song #1|ru|2010|pop
Дима Билан|Believe|ru|2008|pop
Дима Билан|Never Let You Go|ru|2006|pop
Децл|Вечеринка|ru|2000|rap
Баста|Сансара|ru|2010|rap
Баста|Моя игра|ru|2008|rap
Каста|Вокруг шум|ru|2006|rap
Мот|Сопрано|ru|2015|rap
Макс Корж|Малый повзрослел|by|2018|pop
Макс Корж|Жить в кайф|by|2018|pop
Miyagi & Эндшпиль|Captain|ru|2019|rap
Miyagi & Эндшпиль|Minor|ru|2018|rap
Miyagi & Эндшпиль|I Got Love|ru|2018|rap
HammAli & Navai|Птичка|ru|2020|pop
Скриптонит|Положение|kz|2019|rap
Artik & Asti|Грустный дэнс|ru|2019|pop
Zivert|Beverly Hills|ru|2019|pop
Quest Pistols|Белая стрекоза любви|ua|2010|pop
Время и Стекло|Имя 505|ua|2014|pop
Океан Ельзи|Обійми|ua|2006|rock
Kazka|Плакала|ua|2018|pop
Ruslana|Wild Dances|ua|2004|pop
Jamala|1944|ua|2016|pop
Go_A|Шум|ua|2021|electro
Verka Serduchka|Dancing Lasha Tumbai|ua|2007|pop
Dimash Kudaibergen|SOS d'un terrien en détresse|kz|2017|pop
Sirusho|Qélé Qélé|am|2008|pop
Ell & Nikki|Running Scared|az|2011|pop
"""


def norm(s):
    return re.sub(r"[\W_]+", " ", (s or "").lower()).strip()


def has(text, needle):
    """Слово/фраза целиком внутри нормализованного текста."""
    return bool(needle) and f" {needle} " in f" {text} "


def split_artists(raw):
    raw = re.sub(r"^\s*by\s+", "", raw or "", flags=re.I)
    parts = re.split(r"\s*(?:,|&|\bfeat\.?|\bft\.?)\s*", raw, flags=re.I)
    return [p.strip() for p in parts if p.strip()]


def clean_title(name):
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", name or "").strip()  # (Extended Version), [feat. ...]


def is_bad_text(s):
    s = s or ""
    return bool(BAD_RE.search(s) or AUDIO_RE.search(s) or LIVE_RE.search(s) or AI_TITLE_RE.search(s))


def title_marker(title_norm):
    return bool(set(title_norm.split()) & MARKER_WORDS)



def _track(key, artist_raw, title, released="", genres=(), rank=0, **extra):
    artists = split_artists(artist_raw) or [artist_raw]
    t = {
        "key": key, "rank": rank, "artist_raw": artist_raw, "artists": artists,
        "names": [norm(a) for a in artists if norm(a)], "title": title,
        "released": (released or "")[:10], "genres": list(genres),
    }
    t.update(extra)
    return t



def channel_is_official(c, track):
    ch = norm(c.get("channel"))
    if not ch or ch == "topic" or ch.endswith(" topic"):  # авто-каналы "Artist - Topic" - это не клипы
        return False
    names = track["names"]
    if any(len(n) >= 3 and (ch == n or has(ch, n) or (len(ch) >= 4 and has(n, ch))) for n in names):
        return True
    if "vevo" in ch or LABEL_RE.search(ch):
        return True
    if c.get("verified"):
        title = norm(c.get("title"))
        return title_marker(title) or any(has(title, n) for n in names)
    return False


def eval_candidate(c, track):
    """None - ролик не подходит; иначе (официальный_канал, есть_маркер_клипа)."""
    raw_title = c.get("title") or ""
    if is_bad_text(raw_title):
        return None
    ch = norm(c.get("channel"))
    if ch == "topic" or ch.endswith(" topic") or AI_TITLE_RE.search(c.get("channel") or ""):
        return None
    d = c.get("duration")
    if d and not (MIN_DUR <= d <= MAX_DUR):
        return None
    title = norm(raw_title)
    names = track["names"]
    marker = title_marker(title)
    name = norm(track["title"])
    name_ok = has(title, name)
    artist_t = any(has(title, n) for n in names)
    artist_c = any(len(n) >= 3 and (has(ch, n) or (len(ch) >= 4 and has(n, ch))) for n in names)
    if not (artist_t or artist_c):                      # трек с таким же названием, но другого артиста
        return None
    # название трека может быть на другом алфавите (корейский, японский) - тогда смотрим на артиста
    if not (name_ok or (artist_t and marker)):
        return None
    official = channel_is_official(c, track)
    if not (official or marker):
        return None
    return official, marker


