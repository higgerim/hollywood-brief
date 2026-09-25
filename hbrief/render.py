"""content.json으로 카드뉴스 이미지, 뉴스레터 본문, 인스타그램 캡션을 만들어요."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).parent / "templates"
STATUS_LABEL = {"확인됨": "✅ 공식 확인", "보도": "📰 외신 보도", "루머": "⚠️ 미확인 보도"}


def render_cards(content: dict, brand: dict, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    template = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True).get_template("card.html")
    stories = content["stories"]
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
        lines += [s["body"], ""]
        lines += [f"> **왜 화제일까?** {s['why_it_matters']}", ""]
        links = " · ".join(f"[{src['name']}]({src['url']})" for src in s["sources"])
        lines += [f"출처: {links}", ""]
    lines += ["---", "", f"오늘의 {brand['name']}는 여기까지예요. 재밌게 읽으셨다면 친구에게 공유해 주세요! 💌", ""]
    lines += [f"인스타그램 {brand['instagram_handle']}에서 카드뉴스로도 만나보세요.", ""]
    return "\n".join(lines)


def render_caption(content: dict, brand: dict) -> str:
    numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    lines = [content["caption_hook"], ""]
    lines += [f"{numbers[i]} {s['card_title']}" for i, s in enumerate(content["stories"])]
    lines += ["", "📩 이슈별 배경과 원문 링크는 프로필 링크의 뉴스레터에서 볼 수 있어요.", ""]
    outlets = []
    for s in content["stories"]:
        outlets += [src["name"] for src in s["sources"] if src["name"] not in outlets]
    lines += [f"출처: {', '.join(outlets)}", ""]
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
    content = json.loads((issue_dir / "content.json").read_text(encoding="utf-8"))
    card_paths = render_cards(content, brand, issue_dir) if cards else sorted((issue_dir / "cards").glob("*.jpg"))
    (issue_dir / "newsletter.md").write_text(render_newsletter(content, brand), encoding="utf-8")
    (issue_dir / "caption.txt").write_text(render_caption(content, brand), encoding="utf-8")
    (issue_dir / "README.md").write_text(render_preview(content, card_paths), encoding="utf-8")
