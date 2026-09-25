"""RSS와 레딧에서 최근 기사를 모으고, 같은 이슈끼리 묶어 화제성 순으로 정렬해요."""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

USER_AGENT = "Mozilla/5.0 (hollywood-brief newsletter bot)"

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "after", "about", "into", "over",
    "his", "her", "their", "they", "she", "him", "has", "have", "had", "was", "were", "are",
    "its", "new", "says", "said", "just", "reveals", "reveal", "why", "how", "what", "who",
    "will", "not", "but", "out", "all", "more", "first", "photos", "video", "watch", "exclusive",
    "report", "reportedly", "amid", "gets", "get", "star", "stars", "year", "years", "one", "two",
}


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
    return None


def fetch_feed(name: str, url: str, since: datetime, kind: str) -> list[dict]:
    parsed = feedparser.parse(url, agent=USER_AGENT)
    if parsed.get("status") == 429:  # 레딧은 요청이 몰리면 잠시 막아요
        time.sleep(15)
        parsed = feedparser.parse(url, agent=USER_AGENT)
    items = []
    for entry in parsed.entries:
        published = _published(entry)
        if published and published < since:
            continue
        title = _clean(entry.get("title", ""))
        if not title:
            continue
        items.append({
            "source": name,
            "kind": kind,  # "news" | "reddit"
            "title": title,
            "url": entry.get("link", ""),
            "published": published.isoformat() if published else None,
            "summary": _clean(entry.get("summary", ""))[:600] if kind == "news" else "",
        })
    return items


def collect(config: dict) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=config["lookback_hours"])
    articles = []
    for feed in config["feeds"]:
        found = fetch_feed(feed["name"], feed["url"], since, "news")
        print(f"  {feed['name']}: {len(found)}건")
        articles += found
    for feed in config.get("reddit", []):
        time.sleep(5)
        found = fetch_feed(feed["name"], feed["url"], since, "reddit")
        print(f"  {feed['name']}: {len(found)}건")
        articles += found
    return articles


def _tokens(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", title.lower())
    return {w.strip("'") for w in words if len(w) > 2 and w not in STOPWORDS}


def cluster(articles: list[dict], limit: int = 40) -> list[dict]:
    """제목이 비슷한 기사끼리 묶고, 여러 매체가 다룰수록 높은 점수를 줘요."""
    clusters: list[dict] = []
    for article in articles:
        tokens = _tokens(article["title"])
        best, best_score = None, 0.0
        for c in clusters:
            shared = len(tokens & c["tokens"])
            score = shared / (len(tokens | c["tokens"]) or 1)
            if shared >= 2 and score >= 0.2 and score > best_score:
                best, best_score = c, score
        if best:
            best["articles"].append(article)
            best["tokens"] |= tokens
        else:
            clusters.append({"tokens": set(tokens), "articles": [article]})

    now = datetime.now(timezone.utc)
    ranked = []
    for c in clusters:
        news = [a for a in c["articles"] if a["kind"] == "news"]
        if not news:
            continue  # 레딧에만 있는 이야기는 출처가 없어서 제외
        outlets = {a["source"] for a in news}
        reddit_hits = sum(1 for a in c["articles"] if a["kind"] == "reddit")
        newest = max((a["published"] for a in news if a["published"]), default=None)
        fresh = newest and now - datetime.fromisoformat(newest) < timedelta(hours=24)
        score = len(outlets) * 3 + reddit_hits * 2 + (2 if fresh else 0)
        ranked.append({"score": score, "outlets": sorted(outlets), "reddit_hits": reddit_hits,
                       "articles": c["articles"]})

    ranked.sort(key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(ranked[:limit], start=1):
        c["id"] = i
    return ranked[:limit]
