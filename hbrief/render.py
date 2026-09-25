"""content.json으로 카드뉴스 이미지, 뉴스레터 본문, 인스타그램 캡션을 만들어요."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).parent / "templates"
STATUS_LABEL = {"확인됨": "✅ 공식 확인", "보도": "📰 외신 보도", "루머": "⚠️ 미확인 보도"}


def _data_uri(path: Path) -> str:
    data = path.read_bytes()
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def render_cards(content: dict, brand: dict, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    template = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True).get_template("card.html")
    # 카드 HTML은 파일 경로로 이미지를 못 읽어서 데이터 URI로 넣어요
    stories = []
    for s in content["stories"]:
        img = s.get("image")
        files = [x["file"] for x in img["items"]] if img and img["type"] == "pair" else [img["file"]] if img else []
        photos = [_data_uri(out_dir / f) for f in files]
        stories.append({**s, "photos": photos, "photo": photos[0] if photos else None})
    pages = [{"kind": "cover", "stories": stories}]
    pages += [{"kind": "story", "story": s, "index": i, "total": len(stories)} for i, s in enumerate(stories, 1)]
    pages.append({"kind": "cta"})

    cards_dir = out_dir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("*.jpg"):
        old.unlink()

    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for n, ctx in enumerate(pages, 1):
            html = template.render(brand=brand, issue_date=content["issue_date"], **ctx)
            page.set_content(html, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            scale = page.evaluate("window.fitText()")
            if scale < 0.75:
                print(f"  ⚠️ {n:02d}번 카드 글이 길어서 글자를 {scale:.0%}로 줄였어요. 문구를 줄이는 걸 권해요.")
            path = cards_dir / f"{n:02d}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=92)
            paths.append(path)
        browser.close()
    return paths


def render_newsletter(content: dict, brand: dict) -> str:
    lines = [f"# {content['issue_title']}", "", content["intro"], ""]
    for i, s in enumerate(content["stories"], 1):
        lines += ["---", "", f"## {i}. {s['headline']}", "", f"`{s['category']}` · {STATUS_LABEL[s['status']]}", ""]
        if s.get("image"):
            img = s["image"]
            urls = [x["url"] for x in img["items"]] if img["type"] == "pair" else [img["url"]]
            lines += [" ".join(f"![{s['headline']}]({u})" for u in urls), "",
                      f"*이미지: {img['note']}*", ""]
        lines += [s["body"], ""]
        lines += [f"> **왜 화제일까?** {s['why_it_matters']}", ""]
        links = " · ".join(f"[{src['name']}]({src['url']})" for src in s["sources"])
        lines += [f"출처: {links}", ""]
    lines += ["---", "", f"오늘의 {brand['name']}는 여기까지예요. 재밌게 읽으셨다면 친구에게 공유해 주세요! 💌", ""]
    lines += [f"인스타그램 {brand['instagram_handle']}에서 카드뉴스로도 만나보세요.", ""]
    return "\n".join(lines)


def render_newsletter_html(content: dict, brand: dict) -> str:
    """메일리 에디터에 복사해 붙여넣는 용도. 브라우저에서 열어 복사하면 사진·링크가 함께 옮겨져요"""
    template = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True).get_template("newsletter.html")
    return template.render(content=content, brand=brand, status_label=STATUS_LABEL)


def render_caption(content: dict, brand: dict) -> str:
    numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    lines = [content["caption_hook"], ""]
    lines += [f"{numbers[i]} {s['card_title']}" for i, s in enumerate(content["stories"])]
    lines += ["", "📩 이슈별 배경과 원문 링크는 프로필 링크의 뉴스레터에서 볼 수 있어요.", ""]
    outlets = []
    for s in content["stories"]:
        outlets += [src["name"] for src in s["sources"] if src["name"] not in outlets]
    lines += [f"출처: {', '.join(outlets)}"]
    # 카드에 적힌 짧은 출처를 모아요 (퍼블릭 도메인처럼 표기 의무가 없는 건 빠져요)
    credits = [f"{i} {s['image']['credit'].removeprefix('Photo: ')}"
               for i, s in enumerate(content["stories"], 1) if s.get("image") and s["image"].get("credit")]
    if credits:
        lines += ["📷 " + " | ".join(credits) + " (위키미디어 공용 사진은 일부 잘라서 사용)"]
    lines += ["", ""]  # 해시태그 앞에 빈 줄
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in content["hashtags"][:25])
    caption = "\n".join(lines) + tags
    return caption[:2200]  # 인스타그램 캡션 최대 길이


def render_preview(content: dict, card_paths: list[Path]) -> str:
    """PR에서 한눈에 검토할 수 있는 미리보기 문서"""
    lines = [f"# {content['issue_date']} 초안 — {content['issue_title']}", "",
             "검토 순서: 카드 이미지 → caption.txt → newsletter.md. 고칠 부분은 **content.json**을 수정하면 이미지가 자동으로 다시 만들어져요.", ""]
    lines += [f"<img src=\"cards/{p.name}\" width=\"270\">" for p in card_paths]
    return "\n".join(lines) + "\n"


def render_all(issue_dir: Path, brand: dict, cards: bool = True) -> None:
    from .images import attach_images

    content_path = issue_dir / "content.json"
    content = json.loads(content_path.read_text(encoding="utf-8"))
    if attach_images(content, issue_dir):
        content_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    card_paths = render_cards(content, brand, issue_dir) if cards else sorted((issue_dir / "cards").glob("*.jpg"))
    (issue_dir / "newsletter.md").write_text(render_newsletter(content, brand), encoding="utf-8")
    (issue_dir / "newsletter.html").write_text(render_newsletter_html(content, brand), encoding="utf-8")
    (issue_dir / "caption.txt").write_text(render_caption(content, brand), encoding="utf-8")
    (issue_dir / "README.md").write_text(render_preview(content, card_paths), encoding="utf-8")
