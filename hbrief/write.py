"""후보 이슈 중 한국 독자용 기사를 고르고, Claude로 한국어 초안을 작성해요."""
from __future__ import annotations

import json
import os
import subprocess

SYSTEM_PROMPT = """당신은 한국 독자에게 해외 할리우드 소식을 전하는 소식지의 편집자입니다.
같은 원고가 두 곳에 쓰입니다: 인스타그램 카드뉴스(짧고 강렬하게)와 이메일 뉴스레터(맥락과 해설 중심).

선별 기준:
- 여러 매체가 동시에 다루고 레딧 반응이 큰 이슈를 우선합니다.
- 한국 독자가 이름을 알 만한 스타, 한국 개봉·OTT 공개 작품, 한국계 배우·K-콘텐츠 관련 이슈는 가산점입니다.
- 비슷한 이슈를 두 번 고르지 마세요. 영화·드라마·음악·연애·법정 등 주제가 한쪽에 몰리지 않게 섞으세요.
- 미성년자 사생활, 사망·자살의 구체적 묘사, 근거가 약한 성적 루머는 고르지 마세요.

작성 원칙 (법적 위험 때문에 반드시 지켜야 합니다):
- 원문을 번역하지 말고, 제공된 자료의 사실을 바탕으로 직접 요약·해설하세요.
- 자료에 없는 사실, 숫자, 인용문을 만들어내지 마세요. 모르는 내용은 쓰지 않습니다.
- 확인되지 않은 내용은 반드시 "○○ 보도에 따르면", "~로 알려졌다"처럼 출처를 밝혀 쓰세요.
  status는 공식 발표·본인 확인이면 "확인됨", 매체 보도면 "보도", 익명 소식통 중심이면 "루머"입니다.
- 모든 문장은 친근한 "~해요"체로 통일하세요 (카드, 뉴스레터, 캡션 모두).
- 인물을 비하하거나 조롱하지 마세요. 가십 톤은 유지하되 사실 전달이 우선입니다.
- 한국에서 통용되는 표기를 쓰세요 (예: 테일러 스위프트, 티모시 샬라메). 작품명은 한국 공개 제목이 있으면 그것을 씁니다.
- why_it_matters에는 한국 독자가 "그래서 왜 난리야?"에 답을 얻도록 배경을 설명하세요.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "issue_title": {"type": "string", "description": "이번 호 제목. 가장 큰 이슈를 담아 30자 이내"},
        "intro": {"type": "string", "description": "뉴스레터 첫 인사와 이번 호 요약, 2~3문장"},
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cluster_id": {"type": "integer", "description": "근거로 쓴 후보 이슈의 id"},
                    "category": {"type": "string", "enum": ["영화", "드라마", "음악", "연애", "법정", "시상식", "패션", "K-콘텐츠", "이슈"]},
                    "status": {"type": "string", "enum": ["확인됨", "보도", "루머"]},
                    "card_title": {"type": "string", "description": "카드뉴스 제목. 22자 이내, 궁금증을 일으키게"},
                    "points": {
                        "type": "array", "items": {"type": "string"},
                        "description": "카드뉴스 핵심 요약 정확히 3개. 각 40자 이내의 짧은 문장",
                    },
                    "why_it_matters": {"type": "string", "description": "왜 화제인지, 80자 이내"},
                    "headline": {"type": "string", "description": "뉴스레터용 제목, 40자 이내"},
                    "body": {"type": "string", "description": "뉴스레터 본문. 2~4개 문단, 문단 사이 빈 줄. 배경·경과·반응 순서"},
                },
                "required": ["cluster_id", "category", "status", "card_title", "points", "why_it_matters", "headline", "body"],
                "additionalProperties": False,
            },
        },
        "caption_hook": {"type": "string", "description": "인스타그램 캡션 첫 줄. 스크롤을 멈추게 하는 한 문장"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "description": "해시태그 10~15개, # 없이. 인물명·작품명 한국어/영어 혼합"},
    },
    "required": ["issue_title", "intro", "stories", "caption_hook", "hashtags"],
    "additionalProperties": False,
}


def _format_candidates(clusters: list[dict]) -> str:
    lines = []
    for c in clusters:
        lines.append(f"### 후보 {c['id']} — 보도 매체 {len(c['outlets'])}곳 ({', '.join(c['outlets'])}), 레딧 인기글 {c['reddit_hits']}개")
        for a in c["articles"]:
            if a["kind"] == "news":
                lines.append(f"- [{a['source']}] {a['title']} ({a['published'] or '날짜 없음'})")
                if a["summary"]:
                    lines.append(f"  요약: {a['summary']}")
            else:
                lines.append(f"- [레딧 {a['source']}] {a['title']}")
        lines.append("")
    return "\n".join(lines)


def _build_prompt(config: dict, clusters: list[dict], issue_date: str) -> str:
    return (
        f"발행일: {issue_date}\n"
        f"아래 후보 중 {config['stories_per_issue']}개를 골라 이번 호 원고를 작성하세요. "
        "화제성이 높은 순서로 배치하세요.\n\n"
        + _format_candidates(clusters)
    )


def _write_with_claude_code(config: dict, prompt: str) -> dict:
    """Claude 구독 계정으로 Claude Code를 실행해요 (추가 비용 없음, 구독 사용 한도 사용)."""
    cmd = [
        os.environ.get("CLAUDE_BIN", "claude"), "-p",
        "--model", config["claude_code_model"],
        "--system-prompt", SYSTEM_PROMPT,
        "--json-schema", json.dumps(SCHEMA, ensure_ascii=False),
        "--output-format", "json",
        "--tools", "",
        "--no-session-persistence",
    ]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=1200)
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude Code 실행 실패 (exit {proc.returncode}):\n{proc.stderr[-2000:]}\n{proc.stdout[-2000:]}")
    if result.get("is_error") or not result.get("structured_output"):
        raise RuntimeError(f"Claude Code가 원고를 만들지 못했어요: {result.get('subtype')} {str(result.get('result'))[:1000]}")
    return result["structured_output"]


def _write_with_api(config: dict, prompt: str) -> dict:
    """Claude API 키로 호출해요 (쓴 만큼 별도 결제)."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=config["api_model"],
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude가 작성을 거절했어요: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 길이 제한에 걸려 잘렸어요. max_tokens를 늘려주세요.")
    print(f"  토큰 사용량: 입력 {response.usage.input_tokens}, 출력 {response.usage.output_tokens}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def write_issue(config: dict, clusters: list[dict], issue_date: str) -> dict:
    prompt = _build_prompt(config, clusters, issue_date)
    if config["engine"] == "api":
        content = _write_with_api(config, prompt)
    else:
        content = _write_with_claude_code(config, prompt)

    # 출처는 모델이 쓰지 않고, 실제 수집한 기사에서 붙여요 (링크 오류 방지)
    by_id = {c["id"]: c for c in clusters}
    for story in content["stories"]:
        cluster = by_id.get(story["cluster_id"])
        if not cluster:
            raise RuntimeError(f"존재하지 않는 후보 id: {story['cluster_id']}")
        sources = {}
        for a in cluster["articles"]:
            if a["kind"] == "news" and a["source"] not in sources:
                sources[a["source"]] = {"name": a["source"], "url": a["url"]}
        story["sources"] = list(sources.values())
    content["issue_date"] = issue_date
    return content
