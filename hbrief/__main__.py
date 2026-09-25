"""사용법:
  python -m hbrief draft [--date YYYY-MM-DD]     기사 수집 → 선별 → 초안 작성 → 카드·본문 생성
  python -m hbrief render drafts/2026-09-28      content.json을 고친 뒤 카드·본문 다시 만들기
  python -m hbrief publish [--dry-run]            승인된(메인에 합쳐진) 초안을 인스타그램에 게시
  python -m hbrief refresh-token                  인스타그램 토큰 연장 (새 토큰을 출력)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
KST = timezone(timedelta(hours=9))


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def cmd_draft(args, config):
    from .collect import cluster, collect
    from .render import render_all
    from .write import write_issue

    issue_date = args.date or datetime.now(KST).strftime("%Y-%m-%d")
    issue_dir = DRAFTS / issue_date
    if (issue_dir / "content.json").exists():
        sys.exit(f"{issue_dir}에 이미 초안이 있어요.")
    issue_dir.mkdir(parents=True, exist_ok=True)

    print("1/3 기사 수집")
    articles = collect(config)
    clusters = cluster(articles)
    if len(clusters) < config["stories_per_issue"]:
        sys.exit(f"후보 이슈가 {len(clusters)}개뿐이라 초안을 만들지 않았어요.")
    (issue_dir / "candidates.json").write_text(json.dumps(clusters, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"2/3 Claude로 원고 작성 (후보 {len(clusters)}개)")
    content = write_issue(config, clusters, issue_date)
    (issue_dir / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")

    print("3/3 카드뉴스·뉴스레터 생성")
    render_all(issue_dir, config["brand"])
    print(f"완료: {issue_dir}")
    _write_github_output(issue_date=issue_date, issue_title=content["issue_title"])


def cmd_render(args, config):
    from .render import render_all

    render_all(Path(args.issue_dir), config["brand"], cards=not args.skip_cards)
    print("다시 만들었어요.")


def cmd_publish(args, config):
    from .instagram import Instagram

    repo, sha = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_SHA")
    pending = [d for d in sorted(DRAFTS.iterdir())
               if (d / "content.json").exists() and (d / "cards").is_dir() and not (d / "published.json").exists()]
    if not pending:
        print("게시할 새 초안이 없어요.")
        return

    for issue_dir in pending:
        cards = sorted((issue_dir / "cards").glob("*.jpg"))
        rel = issue_dir.relative_to(ROOT).as_posix()
        urls = [f"https://raw.githubusercontent.com/{repo}/{sha}/{rel}/cards/{c.name}" for c in cards]
        caption = (issue_dir / "caption.txt").read_text(encoding="utf-8")
        print(f"{issue_dir.name}: 카드 {len(cards)}장 게시")
        if args.dry_run:
            print("\n".join(urls))
            continue
        info = Instagram(config["instagram"]["api_version"]).publish_carousel(urls, caption)
        (issue_dir / "published.json").write_text(json.dumps({"instagram": info}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  게시 완료: {info.get('permalink')}")


def cmd_refresh_token(args, config):
    from .instagram import refresh_token

    data = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    print(f"새 토큰 유효기간: {data['expires_in'] // 86400}일", file=sys.stderr)
    print(data["access_token"])


def _write_github_output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for key, value in values.items():
                f.write(f"{key}={value}\n")


def main():
    parser = argparse.ArgumentParser(prog="hbrief")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("draft")
    p.add_argument("--date")
    p = sub.add_parser("render")
    p.add_argument("issue_dir")
    p.add_argument("--skip-cards", action="store_true")
    p = sub.add_parser("publish")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("refresh-token")

    args = parser.parse_args()
    config = load_config()
    handlers = {"draft": cmd_draft, "render": cmd_render, "publish": cmd_publish, "refresh-token": cmd_refresh_token}
    handlers[args.command](args, config)


if __name__ == "__main__":
    main()
