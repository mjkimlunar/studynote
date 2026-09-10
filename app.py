"""StudyNote — 공부 노트 -> 블로그 초안 에이전트 (Streamlit 앱)

3개 화면(PRD §7)을 탭이 아니라 하나의 순차 흐름으로 구성:
입력 -> 실행 로그 -> 초안 검토/승인/발행
"""

import os

import streamlit as st
from dotenv import load_dotenv

from agent import pipeline

load_dotenv()

st.set_page_config(page_title="StudyNote", page_icon="📝")
st.title("📝 StudyNote — 공부 노트 → 블로그 초안")

with st.expander("ℹ️ 이 앱은 무엇을 하나요? (설계 배경 — 클릭해서 펼치기)", expanded=True):
    st.markdown(
        """
**공부 노트(텍스트)를 받아서, 본인 문체가 반영된 블로그 초안을 만들어주는 에이전트입니다.**

**동작 순서**: 노트 입력 → (필요시) 관련 자료 검색·실재성 확인 → 핵심 정리 →
스타일 변환(LLM) → **사람이 직접 검토·승인** → 발행(초안 상태로만)

- 검색 도구는 [citecheck] 프로젝트의
  원칙(실재성만 확인, 진위 판정은 안 함)을 재사용했습니다.
- 스타일은 두 모드(일기체/정보전달체)로 나뉘는데, 실제 테스트 중 일기체 예시로 학습한
  문체가 정보전달형 노트엔 안 맞는 걸 발견해서 분리했습니다 (자세한 실험 과정은 PRD 참고).
- 발행은 항상 "초안" 상태로만 생성되고, 실제 공개는 사람이 별도로 승인해야 합니다.

📄 **기획 배경 전체(PRD)**: [PRD.md](https://github.com/mjkimlunar/studynote/blob/main/PRD.md)
&nbsp;&nbsp;·&nbsp;&nbsp; 💻 **코드**: [GitHub 저장소](https://github.com/mjkimlunar/studynote)
"""
    )

if "state" not in st.session_state:
    st.session_state.state = None
if "published_url" not in st.session_state:
    st.session_state.published_url = None

# ── 화면1: 입력 ──────────────────────────────────────────────
st.header("1. 노트 입력")
note_text = st.text_area("공부 노트를 붙여넣으세요", height=200)
title = st.text_input("블로그 제목 (발행 시 사용)")

style_mode_label = st.radio(
    "스타일 선택",
    options=["🗣️ 일기체 (반말, 본인 글 스타일 반영)", "📋 정보전달체 (존댓말, 담백한 설명 톤)"],
    horizontal=True,
)
style_mode = "casual" if style_mode_label.startswith("🗣️") else "formal"

missing_keys = [
    k for k in ("OPENAI_API_KEY",) if not os.environ.get(k)
]
if missing_keys:
    st.warning(f"환경변수 미설정: {', '.join(missing_keys)} — .env 파일을 확인하세요 (.env.example 참고)")

if st.button("실행", disabled=not note_text or bool(missing_keys)):
    with st.spinner("에이전트 실행 중..."):
        st.session_state.state = pipeline.run_until_review(note_text, style_mode=style_mode)
        st.session_state.published_url = None

# ── 화면2: 실행 로그 ─────────────────────────────────────────
if st.session_state.state:
    st.header("2. 실행 로그")
    for entry in st.session_state.state.log:
        st.text(
            f"[{entry.step}] {entry.detail}  "
            f"({entry.duration_sec:.1f}초"
            + (f", {entry.tokens} 토큰" if entry.tokens else "")
            + ")"
        )

    # ── 화면3: 초안 검토 · 승인 · 발행 ─────────────────────────
    st.header("3. 초안 검토")
    edited_draft = st.text_area("초안 (직접 수정 가능)", st.session_state.state.draft, height=300)
    st.session_state.state.draft = edited_draft

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 재생성 (위 스타일 선택 반영)"):
            with st.spinner("재생성 중..."):
                st.session_state.state.style_mode = style_mode
                st.session_state.state = pipeline.generate_draft(st.session_state.state)
    with col2:
        if st.button("✅ 승인 및 발행 (draft 상태로 커밋)"):
            with st.spinner("발행 중..."):
                st.session_state.published_url = pipeline.publish(
                    st.session_state.state, title or "제목 없음"
                )

    if st.session_state.published_url:
        url = st.session_state.published_url
        if url.startswith("http"):
            st.success(f"발행 완료(초안 상태): {url}")
            st.caption("이 링크는 draft 상태입니다. 실제 공개는 블로그 저장소에서 직접 draft:false로 바꿔야 합니다.")
        else:
            st.warning(
                "GitHub 발행 설정(GITHUB_TOKEN/GITHUB_BLOG_REPO)이 없어서 "
                "서버 내부에만 저장됐습니다 — 아래 버튼으로 바로 다운로드하세요."
            )

    # GitHub 설정 여부와 무관하게, 항상 결과물을 직접 확인/다운로드할 수 있게 함
    st.download_button(
        "⬇️ 초안 다운로드 (.md)",
        data=st.session_state.state.draft,
        file_name=f"{(title or 'draft').strip()}.md",
        mime="text/markdown",
    )