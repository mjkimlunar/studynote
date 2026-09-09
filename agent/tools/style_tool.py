"""스타일 변환 도구.

data/style_examples/*.txt 를 few-shot 예시로 읽어들여, 노트를 본인 문체의
블로그 초안으로 재작성한다. (패턴3: 스타일 전이 — 오늘 스터디에서 배운 것 그대로)
"""

import os
from pathlib import Path

from openai import OpenAI

STYLE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "style_examples"

# 모드1: 일기체(반말) — 본인이 실제로 쓴 순수 글(few-shot)을 그대로 흉내낸다.
CASUAL_SYSTEM_PROMPT = """당신은 사용자의 공부 노트를 블로그 초안으로 재작성하는 도우미입니다.

아래에 사용자가 실제로 쓴 글 예시가 주어집니다. 그 예시들의 말투를 최대한 반영해서
재작성하세요. 구체적으로 지켜야 할 것:

- **문장 종결어미를 예시와 똑같이 맞추세요.** 예시가 반말체("-다", "-았다", "-네", "-지"
  등으로 끝남)라면, 노트 원문이 존댓말이어도 **반드시 반말체로만** 쓰세요.
  "-습니다", "-요", "-입니다" 같은 존댓말 어미는 절대 쓰지 마세요.
- 짧고 끊어지는 문장, 말줄임표(..)로 끝맺는 습관을 유지하세요.
- ㅋㅋ·ㅎㅎ·ㅠㅠ 같은 감정표현을 자연스러운 자리에 넣으세요.
- 정보 사이사이에 본인의 짧은 반응·감상을 끼워넣으세요 (순수 정보나열 금지).

**노트 원문의 격식 수준은 무시하세요 — 위 예시의 격식 수준(반말체)이 항상 우선입니다.**

절대 하지 말 것:
- 노트에 없는 사실을 지어내지 마세요.
- 예시 글의 구체적인 내용(장소·인물 등)을 새 글에 섞지 마세요 — 문체만 가져오세요.
"""

# 모드2: 정보전달체(존댓말) — few-shot 예시 없이 명시적 규칙만으로 작성.
# (본인 존댓말 글은 AI 협업본이라 예시로 쓰지 않는다 — PRD §3.2)
FORMAL_SYSTEM_PROMPT = """당신은 사용자의 공부 노트를 블로그 초안으로 재작성하는 도우미입니다.
이번엔 정보전달형 존댓말 톤으로 작성합니다. 지켜야 할 것:

- 존댓말체("-습니다", "-요")로 일관되게 작성하세요.
- 정보를 명확하고 읽기 쉽게 구조화하세요 (필요하면 소제목·목록 사용).
- **다만 순수 정보 나열은 피하세요** — 문단 사이사이에 "~한 점이 흥미로웠다" 류의
  짧은 개인 의견·소감을 자연스럽게 끼워넣어서, AI가 그냥 정리한 느낌이 안 나게 하세요.
- 과도한 홍보문구·감탄사("정말 대박이에요!" 류)는 피하고, 담백하게 쓰세요.

절대 하지 말 것:
- 노트에 없는 사실을 지어내지 마세요.
"""

STYLE_PROMPTS = {"casual": CASUAL_SYSTEM_PROMPT, "formal": FORMAL_SYSTEM_PROMPT}


def load_style_examples() -> list[str]:
    if not STYLE_DIR.exists():
        return []
    examples = []
    for f in sorted(STYLE_DIR.glob("*.txt")):
        text = f.read_text(encoding="utf-8").strip()
        if text:
            examples.append(text)
    return examples


def rewrite_to_blog_draft(
    note_text: str,
    references: list[str] | None = None,
    model: str = "gpt-4o-mini",
    style_mode: str = "casual",
) -> str:
    """노트 + (선택) 참고자료를 받아 지정된 스타일 모드의 블로그 초안을 생성한다.

    style_mode: "casual"(일기체·반말, few-shot 사용) 또는 "formal"(정보전달체·존댓말,
    명시적 규칙만 사용 — AI협업 오염 우려로 few-shot 예시는 안 씀).
    """
    system_prompt = STYLE_PROMPTS.get(style_mode, CASUAL_SYSTEM_PROMPT)
    prompt_parts = []

    if style_mode == "casual":
        examples = load_style_examples()
        if examples:
            prompt_parts.append("## 문체 예시 (이 사람이 실제로 쓴 글들)\n")
            for i, ex in enumerate(examples, 1):
                prompt_parts.append(f"### 예시 {i}\n{ex}\n")
        else:
            prompt_parts.append(
                "## 문체 예시 없음 — data/style_examples/ 에 .txt 파일을 추가하면 "
                "본인 문체를 더 정확히 반영합니다. 지금은 담백한 기본 톤으로 작성합니다.\n"
            )

    if references:
        prompt_parts.append("## 참고 자료\n")
        for ref in references:
            prompt_parts.append(f"- {ref}\n")

    prompt_parts.append(f"## 재작성할 노트\n{note_text}\n")
    prompt_parts.append("\n위 노트를 블로그 초안(제목 + 본문)으로 재작성해 주세요.")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(prompt_parts)},
        ],
    )
    return response.choices[0].message.content