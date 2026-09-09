"""에이전트 루프 — PRD §4 워크플로 설계를 그대로 구현.

파싱 -> 보강여부판단 -> (검색) -> 구조화 -> 스타일변환 -> [사람승인] -> 발행

각 단계는 dict 상태(state)를 받아 갱신하고, 실행 로그(log)에 자기 자신을 기록한다 —
이게 PRD §6 "실행 로그"·"단계별 상태 관리" 요구사항이다. 중간에 끊겨도 state를 다시
넘기면 이어서 진행할 수 있도록, 각 단계는 순수 함수(state -> state)로 만든다.
"""

import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

from agent.tools import publish_tool, search_tool, style_tool

MAX_STEPS = 10  # 종료 조건 — 무한 루프 방지 (PRD §"에이전트 루프" 요구사항)


@dataclass
class LogEntry:
    step: str
    detail: str
    duration_sec: float
    tokens: int = 0


@dataclass
class PipelineState:
    note_text: str
    style_mode: str = "casual"  # "casual"(일기체·반말) 또는 "formal"(정보전달체·존댓말)
    stage: str = "parsed"
    needs_enrichment: bool | None = None
    search_results: list = field(default_factory=list)
    draft: str = ""
    log: list[LogEntry] = field(default_factory=list)
    step_count: int = 0


def _log(state: PipelineState, step: str, detail: str, t0: float, tokens: int = 0):
    state.log.append(LogEntry(step=step, detail=detail, duration_sec=time.time() - t0, tokens=tokens))
    state.step_count += 1
    if state.step_count > MAX_STEPS:
        raise RuntimeError("최대 단계 수 초과 — 무한 루프 방지로 중단")


def judge_needs_enrichment(state: PipelineState) -> PipelineState:
    """단계2(에이전트 판단): 노트에 최신 정보 보강이 필요한 주장이 있는가?"""
    t0 = time.time()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": (
                "다음 노트에 최신 정보로 보강하면 좋을 구체적 사실 주장(날짜·수치·최신 동향 등)이 "
                f"있으면 YES, 없으면 NO만 답하세요.\n\n{state.note_text}"
            ),
        }],
    )
    answer = resp.choices[0].message.content.strip().upper()
    state.needs_enrichment = answer.startswith("Y")
    _log(state, "보강여부판단", f"판단: {answer}", t0, tokens=resp.usage.completion_tokens)
    return state


def enrich_with_search(state: PipelineState) -> PipelineState:
    """단계3(도구): 검색/RAG로 관련 최신 자료 보강."""
    t0 = time.time()
    if not state.needs_enrichment:
        _log(state, "검색", "보강 불필요 판단됨 — 스킵", t0)
        return state

    query = state.note_text[:100]
    results = search_tool.search(query, max_results=3)
    state.search_results = [r for r in results if r.verified]
    _log(
        state, "검색",
        f"쿼리='{query[:30]}...' 결과 {len(results)}건, 실재확인 {len(state.search_results)}건",
        t0,
    )
    return state


def generate_draft(state: PipelineState) -> PipelineState:
    """단계4+5(에이전트 판단 + LLM 호출): 구조화 + 스타일 변환을 한 번에 수행."""
    t0 = time.time()
    references = [f"{r.title} ({r.url})" for r in state.search_results]
    draft = style_tool.rewrite_to_blog_draft(
        state.note_text, references=references or None, style_mode=state.style_mode
    )
    state.draft = draft
    state.stage = "draft_ready"
    _log(state, "스타일변환", f"초안 생성 완료 ({len(draft)}자)", t0)
    return state


def run_until_review(note_text: str, style_mode: str = "casual") -> PipelineState:
    """단계1~5를 실행하고, 사람 승인이 필요한 지점(단계6)에서 멈춘다."""
    state = PipelineState(note_text=note_text, style_mode=style_mode)
    state = judge_needs_enrichment(state)
    state = enrich_with_search(state)
    state = generate_draft(state)
    return state


def publish(state: PipelineState, title: str) -> str:
    """단계7(도구, 승인 후에만 호출): 발행. 실패 시 로컬 저장으로 대체."""
    t0 = time.time()
    try:
        url = publish_tool.publish_draft(title, state.draft)
        _log(state, "발행", f"성공 — {url}", t0)
        return url
    except publish_tool.PublishError as e:
        local_path = publish_tool.save_local_fallback(title, state.draft)
        _log(state, "발행", f"실패({e}) — 로컬 저장: {local_path}", t0)
        return local_path