# StudyNote

공부 노트(텍스트/사진)를 본인 문체가 반영된 블로그 초안으로 바꿔주는 에이전틱 워크플로.

- **기획 문서**: [PRD.md](PRD.md)
- **평가**: [eval/](eval/)

## 워크플로

```
노트 입력 → 보강여부판단(에이전트) → 검색/실재성확인(도구) → 스타일변환(도구+LLM)
   → [사람 승인] → 발행(도구, draft 상태로 GitHub 커밋)
```

## 실행 방법

```bash
pip install -r requirements.txt
cp .env.example .env   # 키 채우기
streamlit run app.py
```

**필요한 것**
- `OPENAI_API_KEY` — 스타일 변환에 사용 (`sk-proj-...` 형식)
- `GITHUB_TOKEN` + `GITHUB_BLOG_REPO` — 발행 도구용 (선택. 없으면 발행 시 로컬 파일로 저장됨)

## 도구

| 도구 | 파일 | 역할 |
| --- | --- | --- |
| 검색/RAG | `agent/tools/search_tool.py` | DuckDuckGo 검색 + URL 실재성 확인(citecheck 원칙 재사용) |
| 스타일 변환 | `agent/tools/style_tool.py` | `data/style_examples/*.txt`를 few-shot으로 활용한 문체 재작성 |
| 발행 | `agent/tools/publish_tool.py` | GitHub API로 draft 상태 커밋, 실패 시 로컬 저장 |

## 사람 개입 지점

발행 전 초안 검토·수정·재생성 — Streamlit 앱 화면3에서 승인 버튼을 눌러야만 발행이 실행됨.
승인 없이 발행되는 경로는 없음.

## 알려진 제한

- MVP 단계 — 검색은 DuckDuckGo 무료 검색만 사용(정교한 RAG 랭킹 없음)
- 스타일 예시가 비어 있으면(`data/style_examples/`) 기본 톤으로만 작성됨
- 이미지 노트 입력(OCR)은 아직 미구현 — 텍스트 입력만 지원