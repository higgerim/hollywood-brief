"""이슈별 대표 이미지를 찾아요. 소식의 장면에 가까운 순서로 시도해요.

인물 중심 소식(image_focus: people)
  1. 등장인물이 함께 찍힌 사진 (위키미디어 공용 '찍힌 인물' 태그로 확인)
  2. 등장인물 각자의 사진을 나란히 (예: 테일러 스위프트 | 트래비스 켈시)
  3. 관련 작품 이미지 → 4. 한 사람 사진
작품 중심 소식(image_focus: work)
  관련 작품 이미지(앨범 커버·공식 포스터)를 먼저 쓰고, 없으면 위의 인물 사진 순서로 찾아요.

인물 사진은 자유 라이선스(CC BY, CC BY-SA, CC0, 퍼블릭 도메인)만 쓰고, 작품 이미지는 공식 홍보 이미지를
보도·비평 목적으로 인용해요. 기사에 실린 통신사 사진은 쓰지 않아요. 아무것도 없으면 텍스트 카드로 만들어요.
"""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import requests

HEADERS = {"User-Agent": "hollywood-brief/1.0 (https://github.com/higgerim/hollywood-brief)"}
WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ITUNES_API = "https://itunes.apple.com/search"
# 비상업(NC)·변경금지(ND) 라이선스는 이 목록에 걸리지 않아서 자동으로 빠져요
FREE_LICENSE = re.compile(r"^(CC BY(-SA)? [\d.]+|CC0|Public domain)$", re.I)
WIDTH = 1200


def _get(url: str, **params) -> dict:
    resp = requests.get(url, params={"format": "json", "formatversion": 2, **params}, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html or ""))).strip()


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# ── 1순위: 이슈 자체의 이미지 ──────────────────────────────

def find_album_cover(title: str, artist: str) -> dict | None:
    resp = requests.get(ITUNES_API, params={"term": f"{artist} {title}", "entity": "album", "limit": 10, "country": "US"},
                        headers=HEADERS, timeout=20)
    resp.raise_for_status()
    # 커버 앨범·피아노 버전 같은 엉뚱한 결과를 피하려고 가수 이름이 맞는 것만 봐요
    results = [r for r in resp.json().get("results", []) if _norm(artist) in _norm(r.get("artistName", ""))]
    exact = [r for r in results if _norm(r["collectionName"]) == _norm(title)]
    partial = [r for r in results if _norm(title) in _norm(r["collectionName"])]
    album = (exact or partial or [None])[0]
    if not album:
        return None
    copyright_line = album.get("copyright") or f"© {album['artistName']}"
    return {
        "type": "artwork",
        "url": album["artworkUrl100"].replace("100x100bb", "1200x1200bb"),
        "page": album["collectionViewUrl"],
        "credit": f"앨범 커버 {copyright_line}",
        "note": f"앨범 커버 '{album['collectionName']}' ({copyright_line}), 보도·비평 목적 인용",
    }


def find_poster(wiki_title: str) -> dict | None:
    """위키백과 작품 문서의 대표 이미지(대부분 공식 포스터)"""
    pages = _get(WIKI_API, action="query", prop="pageimages", piprop="name|thumbnail", pithumbsize=WIDTH,
                 pilicense="any", titles=wiki_title, redirects=1)["query"]["pages"]
    page = pages[0] if pages else {}
    name, thumb = page.get("pageimage", ""), page.get("thumbnail", {})
    # 작품 문서에 로고만 있는 경우(주로 SVG)는 포스터가 아니라서 건너뛰어요
    if not thumb or name.lower().endswith(".svg") or "logo" in name.lower():
        return None
    return {
        "type": "artwork",
        "url": thumb["source"],
        "page": f"https://en.wikipedia.org/wiki/File:{name}",
        "credit": f"공식 포스터 · {page['title']}",
        "note": f"'{page['title']}' 공식 포스터, 보도·비평 목적 인용",
    }


# ── 2순위: 인물 사진 ───────────────────────────────────────

def _page_image(title: str) -> str | None:
    """위키백과 문서의 대표 사진 파일 이름"""
    pages = _get(WIKI_API, action="query", prop="pageimages", piprop="name", titles=title, redirects=1)["query"]["pages"]
    return pages[0].get("pageimage") if pages else None


def _commons_file(info: dict) -> dict | None:
    """공용 파일 정보에서 자유 라이선스 사진만 골라요"""
    if info.get("mime") not in ("image/jpeg", "image/png", "image/svg+xml"):
        return None
    meta = info["extmetadata"]
    license_name = _plain(meta.get("LicenseShortName", {}).get("value", ""))
    if not FREE_LICENSE.match(license_name):
        return None
    author = re.sub(r"^(photo(graph)?\s+)?by\s+", "", _plain(meta.get("Artist", {}).get("value", "")), flags=re.I) or "Unknown"
    author = author[:60]
    # SVG는 대부분 로고라서 자르지 않고 통째로 보여줘요 (공용이 PNG로 변환해 줘요)
    is_logo = info["mime"] == "image/svg+xml"
    return {
        "type": "logo" if is_logo else "photo",
        "url": info.get("thumburl") or info["url"],
        "page": info["descriptionurl"],
        # 퍼블릭 도메인은 출처 표기 의무가 없어서 카드에는 적지 않아요
        "credit": "" if license_name in ("Public domain", "CC0") else f"Photo: {author} / {license_name}",
        "note": f"{author} / {license_name} (위키미디어 공용{'' if is_logo else ', 일부 잘라서 사용'})",
        "portrait": info.get("thumbheight", 0) > info.get("thumbwidth", 1) * 1.1,
    }


def find_image(subject: str) -> dict | None:
    """subject: 영어 위키백과 문서 제목(예: "Taylor Swift") 또는 공용 파일 이름(예: "File:xxx.jpg")"""
    filename = subject[5:] if subject.startswith("File:") else _page_image(subject)
    if not filename:
        return None
    # 위키백과에만 올라간 사진(비자유 저작물)은 공용에 없어서 여기서 걸러져요
    pages = _get(COMMONS_API, action="query", prop="imageinfo", titles=f"File:{filename}",
                 iiprop="url|extmetadata|mime", iiurlwidth=WIDTH)["query"]["pages"]
    info = (pages[0].get("imageinfo") or [None])[0] if pages else None
    return _commons_file(info) if info else None


def _wikidata_id(title: str) -> str | None:
    pages = _get(WIKI_API, action="query", prop="pageprops", ppprop="wikibase_item", titles=title, redirects=1)["query"]["pages"]
    return pages[0].get("pageprops", {}).get("wikibase_item") if pages else None


def find_joint_photo(people: list[str]) -> dict | None:
    """모든 인물이 '찍힌 인물'로 태그된 공용 사진 중 가장 최근 것. 제목만 비슷한 거리 풍경 사진은 걸러져요"""
    ids = [_wikidata_id(p) for p in people]
    if len(ids) < 2 or not all(ids):
        return None
    query = " ".join(f"haswbstatement:P180={q}" for q in ids)
    pages = _get(COMMONS_API, action="query", generator="search", gsrnamespace=6, gsrlimit=20, gsrsearch=query,
                 prop="imageinfo", iiprop="url|extmetadata|mime|size", iiurlwidth=WIDTH).get("query", {}).get("pages", [])
    candidates = []
    for page in pages:
        info = page["imageinfo"][0]
        found = _commons_file(info) if info.get("width", 0) >= 800 else None
        if found and found["type"] == "photo":
            candidates.append((info["extmetadata"].get("DateTimeOriginal", {}).get("value", ""), found))
    return max(candidates, key=lambda c: c[0])[1] if candidates else None


# ── 이슈별로 고르기 ────────────────────────────────────────

def _wanted(story: dict) -> str:
    """이미지 선택에 영향을 주는 값. content.json에서 이 값이 바뀌면 이미지를 다시 찾아요"""
    return json.dumps([story.get("image_focus"), story.get("image_people"), story.get("image_work")], ensure_ascii=False)


def _work_image(story: dict) -> dict | None:
    work = story.get("image_work") or {}
    kind, title = work.get("kind", "none"), (work.get("title") or "").strip()
    if kind == "album" and title and work.get("artist"):
        return find_album_cover(title, work["artist"])
    if kind in ("movie", "tv") and title:
        return find_poster(title)
    return None


def _find_for_story(story: dict) -> dict | None:
    people = [p.strip() for p in story.get("image_people") or [] if p.strip()][:2]
    singles = [x for x in (find_image(p) for p in people) if x]
    photos = [x for x in singles if x["type"] == "photo"]

    def together():
        joint = find_joint_photo(people) if len(people) == 2 else None
        if joint:
            return joint
        if len(photos) == 2:
            return {"type": "pair", "items": photos,
                    "credit": ("Photo: " + " · ".join(x["credit"].removeprefix("Photo: ") for x in photos if x["credit"])
                               if any(x["credit"] for x in photos) else ""),
                    "note": " · ".join(x["note"] for x in photos)}
        return None

    work = lambda: _work_image(story)  # noqa: E731
    for step in ([work, together] if story.get("image_focus") == "work" else [together, work]):
        found = step()
        if found:
            return found
    return singles[0] if singles else None


def _download(image: dict, path: Path, issue_dir: Path) -> None:
    resp = requests.get(image["url"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    image["file"] = path.relative_to(issue_dir).as_posix()


def attach_images(content: dict, issue_dir: Path) -> bool:
    """image_focus·image_people·image_work가 바뀐 이슈만 이미지를 새로 찾아 images/에 저장해요. 바뀐 게 있으면 True"""
    img_dir = issue_dir / "images"
    changed = False
    for i, story in enumerate(content["stories"], 1):
        key = _wanted(story)
        current = story.get("image")
        if "image" in story and (current or {}).get("key", key) == key and (not current or (issue_dir / current["file"]).exists()):
            continue
        found = None
        try:
            found = _find_for_story(story)
            if found:
                img_dir.mkdir(exist_ok=True)
                if found["type"] == "pair":
                    for item, suffix in zip(found["items"], "ab"):
                        _download(item, img_dir / f"{i:02d}{suffix}.jpg", issue_dir)
                    found["file"] = found["items"][0]["file"]
                else:
                    _download(found, img_dir / f"{i:02d}.{'png' if found['type'] == 'logo' else 'jpg'}", issue_dir)
                found["key"] = key
        except requests.RequestException as e:
            print(f"  ⚠️ {i}번 이슈 이미지 검색 실패: {e}")
            found = None
        if found:
            label = {"artwork": "작품 이미지", "photo": "인물 사진", "pair": "인물 사진 나란히", "logo": "로고"}[found["type"]]
            print(f"  {i}번 이슈 {label}: {found['note']}")
        else:
            print(f"  {i}번 이슈는 쓸 수 있는 이미지가 없어 텍스트 카드로 만들어요.")
        story["image"] = found
        changed = True
    return changed
