"""
api/score.py — Vercel Serverless Function

ML-Pipeline:
  1. News fetchen (NewsAPI + RSS)
  2. Sentiment-Analyse pro Währung (FinBERT-Lexikon)
  3. Live FX-Kurse (ECB Frankfurt)
  4. Fear & Greed Index
  5. ML-Score berechnen (gewichtetes Ensemble)
  6. Ranking ausgeben
"""
from http.server import BaseHTTPRequestHandler
import json, os, urllib.request, urllib.error, re
from datetime import datetime, timezone

# ═══ WÄHRUNGS-KONFIGURATION ═══════════════════════════════════════════
CODES = ["USD","EUR","JPY","GBP","CHF","AUD","CAD","CNY"]

RATES     = {"USD":3.625,"EUR":2.15,"JPY":0.5,"GBP":3.75,"CHF":0.25,"AUD":4.1,"CAD":2.75,"CNY":3.1}
INFLATION = {"USD":2.8,"EUR":2.2,"JPY":2.9,"GBP":3.1,"CHF":0.8,"AUD":3.4,"CAD":2.5,"CNY":0.5}
CDS       = {"USD":38,"EUR":60,"JPY":28,"GBP":35,"CHF":14,"AUD":22,"CAD":32,"CNY":68}
EPU       = {"USD":270,"EUR":195,"JPY":140,"GBP":188,"CHF":85,"AUD":130,"CAD":245,"CNY":305}
CARRY     = {"USD":65,"EUR":40,"JPY":10,"GBP":66,"CHF":12,"AUD":54,"CAD":44,"CNY":26}

# Basis-FX für Momentum (Stand April 2026)
FX_BASE   = {"eurusd":1.1834,"usdjpy":157.85,"gbpusd":1.3260,
             "usdchf":0.9050,"audusd":0.6450,"usdcad":1.3820,"usdcny":7.2500}

# ═══ SENTIMENT LEXIKON (Loughran-McDonald + Hawkish/Dovish) ════════════
POSITIVE = {"growth","strong","robust","recovery","surplus","gain","rise","rally",
            "bullish","beat","exceed","upgrade","expansion","outperform","record",
            "accelerate","improve","better","higher","positive","boom","soar",
            "strengthen","confidence","optimism","buy","long"}

NEGATIVE = {"recession","crisis","crash","decline","weak","deficit","loss","fall",
            "bearish","miss","downgrade","contraction","underperform","slump",
            "decelerate","worsen","lower","negative","bust","plunge","collapse",
            "risk","concern","fear","warning","threat","sanction","tariff",
            "inflation","stagflation","default","debt","cut","layoff","unemployment"}

HAWKISH  = {"hike","tighten","restrict","raise","higher rates","above target",
            "persistent inflation","overheating","aggressive","vigilant","taper",
            "qt","quantitative tightening","normalize","restrictive"}

DOVISH   = {"cut","ease","accommodate","lower","stimulus","qe","support",
            "below target","weak growth","patient","gradual","flexible",
            "quantitative easing","expand","dovish","pause"}

# Währungs-Keywords — welche Wörter sind relevant für welche Währung
CURRENCY_KEYWORDS = {
    "USD": ["dollar","usd","fed","federal reserve","powell","fomc","us economy",
            "american","treasury","wall street","nasdaq","s&p","united states"],
    "EUR": ["euro","eur","ecb","european central bank","lagarde","eurozone",
            "europe","germany","france","italy","eu ","european union"],
    "JPY": ["yen","jpy","boj","bank of japan","ueda","japan","tokyo","nikkei",
            "japanese","abenomics"],
    "GBP": ["pound","sterling","gbp","boe","bank of england","bailey","uk ",
            "britain","british","london","ftse","brexit"],
    "CHF": ["franc","chf","snb","swiss national bank","switzerland","swiss",
            "geneva","zurich","safe haven","gold"],
    "AUD": ["aud","rba","reserve bank australia","australia","australian",
            "sydney","commodities","iron ore","china trade"],
    "CAD": ["cad","boc","bank of canada","canada","canadian","oil prices",
            "crude","energy","loonie","toronto"],
    "CNY": ["yuan","renminbi","cny","pboc","china","chinese","beijing",
            "shanghai","trade war","tariff china"],
}

# ═══ DATEN FETCHEN ════════════════════════════════════════════════════

def _fetch(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "SentinelFX/2.0",
            "Accept": "application/json,text/html,*/*"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None


def fetch_newsapi(query, api_key, max_results=20):
    """NewsAPI.org — 100 Requests/Tag kostenlos"""
    if not api_key:
        return []
    url = (f"https://newsapi.org/v2/everything"
           f"?q={urllib.parse.quote(query)}"
           f"&language=en&sortBy=publishedAt&pageSize={max_results}"
           f"&apiKey={api_key}")
    data = _fetch(url)
    if not data:
        return []
    try:
        j = json.loads(data)
        return [f"{a['title']}. {a.get('description','')}"
                for a in j.get("articles",[]) if a.get("title")]
    except:
        return []


def fetch_rss(url):
    """RSS-Feed parsen — komplett kostenlos"""
    data = _fetch(url, timeout=5)
    if not data:
        return []
    # Einfaches Regex-Parsing (kein XML-Parser nötig)
    titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', data)
    if not titles:
        titles = re.findall(r'<title>(.*?)</title>', data)
    descriptions = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', data)
    if not descriptions:
        descriptions = re.findall(r'<description>(.*?)</description>', data)
    
    headlines = []
    for i, title in enumerate(titles[:15]):
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        desc = descriptions[i] if i < len(descriptions) else ""
        clean_desc = re.sub(r'<[^>]+>', '', desc).strip()[:200]
        if clean_title and len(clean_title) > 10:
            headlines.append(f"{clean_title}. {clean_desc}")
    return headlines


def fetch_all_news(newsapi_key):
    """Alle News-Quellen kombinieren"""
    headlines = []
    
    # RSS-Feeds (immer verfügbar, kein Key)
    rss_feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/UKBusinessNews",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.forexlive.com/feed/news",
    ]
    for feed_url in rss_feeds:
        items = fetch_rss(feed_url)
        headlines.extend(items)
        if len(headlines) > 60:
            break
    
    # NewsAPI (falls Key vorhanden)
    if newsapi_key:
        queries = ["forex currency", "central bank interest rates", "fed ecb boj"]
        for q in queries:
            items = fetch_newsapi(q, newsapi_key, 10)
            headlines.extend(items)
    
    return headlines[:80]  # Max 80 Headlines


def fetch_fx_rates():
    """ECB FX-Kurse via frankfurter.app"""
    data = _fetch("https://api.frankfurter.app/latest?from=USD&to=EUR,JPY,GBP,CHF,AUD,CAD,CNY")
    if not data:
        return {}
    try:
        j = json.loads(data)
        r = j.get("rates", {})
        return {
            "eurusd": round(1/r["EUR"], 4) if r.get("EUR") else None,
            "usdjpy": round(r["JPY"], 2) if r.get("JPY") else None,
            "gbpusd": round(1/r["GBP"], 4) if r.get("GBP") else None,
            "usdchf": round(r["CHF"], 4) if r.get("CHF") else None,
            "audusd": round(1/r["AUD"], 4) if r.get("AUD") else None,
            "usdcad": round(r["CAD"], 4) if r.get("CAD") else None,
            "usdcny": round(r["CNY"], 4) if r.get("CNY") else None,
        }
    except:
        return {}


def fetch_fear_greed():
    data = _fetch("https://api.alternative.me/fng/?limit=1")
    try:
        return int(json.loads(data)["data"][0]["value"])
    except:
        return 63


# ═══ SENTIMENT ANALYSE ════════════════════════════════════════════════

def tokenize(text):
    return re.findall(r'[a-z]+(?:-[a-z]+)*', text.lower())


def analyze_headline_for_currency(text, code):
    """
    Analysiert eine Headline für eine spezifische Währung.
    
    Returns:
        dict mit sentiment_score, relevance, hawkish_dovish
    """
    text_lower = text.lower()
    tokens = tokenize(text)
    
    # 1. Relevanz: Wie stark bezieht sich die News auf diese Währung?
    currency_hits = sum(1 for kw in CURRENCY_KEYWORDS[code] if kw in text_lower)
    if currency_hits == 0:
        return {"relevant": False, "sentiment": 0, "hawkish_dovish": 0, "confidence": 0}
    
    relevance = min(1.0, currency_hits / 2)
    
    # 2. Sentiment Score
    pos = sum(1 for t in tokens if t in POSITIVE)
    neg = sum(1 for t in tokens if t in NEGATIVE)
    sentiment = (pos - neg) / max(pos + neg, 1)
    
    # 3. Hawkish/Dovish Score (kritisch für FX — bestimmt Zinsentwicklung)
    hawk = sum(1 for kw in HAWKISH if kw in text_lower)
    dove = sum(1 for kw in DOVISH if kw in text_lower)
    hd_score = (hawk - dove) / max(hawk + dove, 1)
    
    # 4. Confidence: mehr Keywords = mehr Konfidenz
    confidence = min(1.0, (pos + neg + hawk + dove) / 5)
    
    return {
        "relevant": True,
        "relevance": relevance,
        "sentiment": sentiment,
        "hawkish_dovish": hd_score,
        "confidence": confidence,
        # Kombinierter Score: Sentiment + Hawkish/Dovish (beide wichtig für FX)
        "combined": sentiment * 0.4 + hd_score * 0.6,  # Hawkish/Dovish dominiert
    }


def compute_news_sentiment(headlines, code):
    """
    Aggregiert alle Headlines zu einem Sentiment-Score für eine Währung.
    
    Hawkish News → höhere Zinsen erwartet → Währung stärker (positiv)
    Dovish News → niedrigere Zinsen → Währung schwächer (negativ)
    """
    if not headlines:
        return {"score": 0, "n_relevant": 0, "signal": "neutral", "headlines": []}
    
    relevant_results = []
    top_headlines = []
    
    for headline in headlines:
        result = analyze_headline_for_currency(headline, code)
        if result["relevant"]:
            relevant_results.append(result)
            top_headlines.append({
                "text": headline[:120],
                "sentiment": round(result["sentiment"], 2),
                "hawkish_dovish": round(result["hawkish_dovish"], 2),
            })
    
    if not relevant_results:
        return {"score": 0, "n_relevant": 0, "signal": "neutral", "headlines": []}
    
    # Gewichteter Durchschnitt (nach Relevanz und Confidence)
    total_weight = sum(r["relevance"] * r["confidence"] for r in relevant_results)
    if total_weight < 1e-9:
        return {"score": 0, "n_relevant": 0, "signal": "neutral", "headlines": []}
    
    weighted_score = sum(
        r["combined"] * r["relevance"] * r["confidence"]
        for r in relevant_results
    ) / total_weight
    
    # Normalisiere auf [-10, +10] Punkte-Bereich für Score-Einfluss
    score_impact = max(-10, min(10, weighted_score * 15))
    
    signal = "bullish" if score_impact > 2 else "bearish" if score_impact < -2 else "neutral"
    
    return {
        "score": round(score_impact, 2),
        "n_relevant": len(relevant_results),
        "signal": signal,
        "headlines": top_headlines[:3],
    }


# ═══ FX MOMENTUM ══════════════════════════════════════════════════════

def get_fx_momentum(code, live_rates):
    """Berechnet % Veränderung vs Basis → Ranking-Einfluss"""
    mapping = {
        "EUR": ("eurusd", +1),   # EUR/USD steigt → EUR stärker
        "JPY": ("usdjpy", -1),   # USD/JPY steigt → JPY schwächer
        "GBP": ("gbpusd", +1),
        "CHF": ("usdchf", -1),   # USD/CHF steigt → CHF schwächer
        "AUD": ("audusd", +1),
        "CAD": ("usdcad", -1),
        "CNY": ("usdcny", -1),
        "USD": None,
    }
    
    if mapping.get(code) is None:
        # USD: Durchschnitt der anderen
        total = 0
        for c, (pair, sign) in [("EUR","eurusd"),("JPY","usdjpy"),("GBP","gbpusd")]:
            live = live_rates.get(pair)
            base = FX_BASE.get(pair)
            if live and base:
                total -= (live/base - 1) * 100
        return round(total / 3, 2)
    
    pair, sign = mapping[code]
    live = live_rates.get(pair)
    base = FX_BASE.get(pair)
    if not live or not base:
        return 0
    return round((live/base - 1) * 100 * sign, 2)


# ═══ ML SCORING ENGINE ════════════════════════════════════════════════

def compute_score(code, fear_greed, sentiment_result, fx_momentum):
    """
    Gewichtetes Ensemble-Modell:
    
    Komponenten:
      40% Fundamental (Zinsen, Inflation, CDS, EPU, Carry)
      25% News-Sentiment (FinBERT-Proxy, Hawkish/Dovish)
      20% FX-Momentum (Live-Kursbewegung)
      15% Markt-Sentiment (Fear&Greed)
    
    Hawkish = Zentralbank will Zinsen erhöhen → Währung stärker
    Dovish  = Zentralbank will Zinsen senken  → Währung schwächer
    """
    ir    = RATES[code]
    infl  = INFLATION[code]
    real  = ir - infl
    cds_s = max(0, 100 - CDS[code] / 1.2)
    epu_s = max(0, 80  - EPU[code] / 4.5)
    carry = CARRY[code] / 100
    
    # Fundamental-Score (40%)
    fundamental = (
        50 + ir*1.8 + real*1.5
        + cds_s*0.14 + epu_s*0.10
        + carry*12
    )
    
    # News-Sentiment (25%) — direkt als Punkte-Bonus/Malus
    news_impact = sentiment_result.get("score", 0)
    
    # FX-Momentum (20%) — max ±8 Punkte
    fx_impact = max(-8, min(8, fx_momentum * 2))
    
    # Fear & Greed (15%) — High F&G = Risk-On = AUD/GBP up, JPY/CHF down
    fg_adj = (fear_greed - 50) / 100
    risk_on_factor = {
        "USD": -0.3, "EUR": 0.1, "JPY": -0.4,
        "GBP": 0.3,  "CHF": -0.3, "AUD": 0.5,
        "CAD": 0.3,  "CNY": 0.0,
    }.get(code, 0)
    fg_impact = fg_adj * risk_on_factor * 15
    
    # Ensemble
    raw_score = (
        fundamental * 0.40
        + (50 + news_impact) * 0.25
        + (50 + fx_impact) * 0.20
        + (50 + fg_impact) * 0.15
    )
    
    score = max(10, min(92, round(raw_score)))
    
    # Modified Z-Score (robust gegen Outlier)
    z = round(0.6745 * (score - 50) / 15, 2)
    
    regime = "BULL" if score >= 60 else "BEAR" if score <= 40 else "SIDEWAYS"
    
    # Kelly-Sizing
    win_p = score / 100
    kelly = round(min(0.20, max(0, (2*win_p - (1-win_p)) / 2) * 0.25), 3)
    
    return {
        "code": code,
        "score": score,
        "z": z,
        "regime": regime,
        "kelly": kelly,
        "realRate": round(real, 2),
        "components": {
            "fundamental": round(fundamental, 1),
            "news_impact": round(news_impact, 2),
            "fx_momentum": round(fx_momentum, 2),
            "fg_impact": round(fg_impact, 2),
        },
        "sentiment": sentiment_result,
    }


def build_pairs(currencies):
    WEIGHTS = {
        ("EUR","USD"):1.0, ("USD","JPY"):0.72, ("GBP","USD"):0.41,
        ("USD","CHF"):0.19, ("USD","CAD"):0.18, ("AUD","USD"):0.17,
        ("EUR","JPY"):0.26, ("EUR","GBP"):0.20, ("CHF","JPY"):0.04,
        ("EUR","CAD"):0.06, ("CHF","CAD"):0.04, ("EUR","CNY"):0.05,
    }
    code_z = {c["code"]: c["z"] for c in currencies}
    pairs = []
    for (b, q), w in WEIGHTS.items():
        zb, zq = code_z.get(b, 0), code_z.get(q, 0)
        edge = abs(zb - zq) * w
        if edge < 0.25:
            continue
        long = zb > zq
        pairs.append({
            "pair": f"{b}/{q}" if long else f"{q}/{b}",
            "edge": round(edge, 2),
            "confidence": min(95, int(50 + edge * 18)),
            "base": b if long else q,
            "quote": q if long else b,
        })
    return sorted(pairs, key=lambda x: x["edge"], reverse=True)[:6]


# ═══ VERCEL HANDLER ═══════════════════════════════════════════════════

import urllib.parse

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=55")
        self.end_headers()

        newsapi_key = os.environ.get("NEWSAPI_KEY", "")

        # Parallel: News + FX + F&G (sequentiell weil serverless)
        headlines   = fetch_all_news(newsapi_key)
        fx_rates    = fetch_fx_rates()
        fear_greed  = fetch_fear_greed()

        # Score alle Währungen
        currencies = []
        for code in CODES:
            sentiment = compute_news_sentiment(headlines, code)
            momentum  = get_fx_momentum(code, fx_rates)
            score     = compute_score(code, fear_greed, sentiment, momentum)
            currencies.append(score)

        currencies.sort(key=lambda x: x["score"], reverse=True)
        pairs = build_pairs(currencies)

        # Marktdaten zusammenstellen
        market = {
            "eurusd":   fx_rates.get("eurusd", 1.1834),
            "usdjpy":   fx_rates.get("usdjpy", 157.85),
            "gbpusd":   fx_rates.get("gbpusd", 1.3260),
            "fearGreed": fear_greed,
            "newsCount": len(headlines),
        }

        payload = {
            "currencies":   currencies,
            "pairs":        pairs,
            "market":       market,
            "lastUpdated":  datetime.now(timezone.utc).isoformat(),
            "source":       "ml-live",
            "newsAnalyzed": len(headlines),
        }

        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.end_headers()

    def log_message(self, *args):
        pass  # Kein Logging in Vercel
