"""검색/RAG 도구.

노트 주제와 관련된 공개 자료를 찾아 (제목, URL, 요약)으로 반환한다.
citecheck(MisMatch) 프로젝트와 같은 원칙: 실재하는지만 확인하고, 진위는 판정하지 않는다.
"""

from dataclasses import dataclass

import requests
from duckduckgo_search import DDGS


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    verified: bool  # URL이 실제로 응답하는지 (존재 확인)


def _verify_url(url: str, timeout: float = 5.0) -> bool:
    """citecheck와 같은 원칙 — 실재성만 확인, 내용의 진위는 판정하지 않는다."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=timeout, stream=True)
        return resp.status_code < 400
    except requests.RequestException:
        return False


def search(query: str, max_results: int = 5) -> list[SearchResult]:
    """쿼리로 공개 웹 검색을 수행하고, 각 결과의 실재성을 확인한다.

    실패 처리 규칙(PRD §5): 검색 실패/결과 없음이면 빈 리스트를 반환한다 —
    호출부에서 이를 "보강 없이 진행"의 신호로 쓴다.
    """
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []

    verified_results = []
    for r in raw_results:
        url = r.get("href", "")
        verified_results.append(
            SearchResult(
                title=r.get("title", ""),
                url=url,
                snippet=r.get("body", ""),
                verified=_verify_url(url),
            )
        )
    return verified_results