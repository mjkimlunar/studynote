"""발행 도구.

승인된 초안을 GitHub Pages 블로그 저장소에 '초안(draft: true)' 상태로 커밋한다.
권한: 쓰기 가능하지만 draft 상태로만 생성 — 실제 공개(publish)는 사람이 저장소에서
draft: false로 바꿔야 한다 (PRD §5 최소 권한 원칙).
"""

import base64
import os
import re
from datetime import datetime, timezone

import requests

GITHUB_API = "https://api.github.com"


class PublishError(Exception):
    pass


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug or "untitled"


def publish_draft(title: str, body_markdown: str, max_retries: int = 2) -> str:
    """블로그 저장소에 초안을 커밋하고, 생성된 파일의 GitHub URL을 반환한다.

    실패 처리 규칙(PRD §5): 최대 2회 재시도 후에도 실패하면 PublishError를 던진다 —
    호출부(app.py)에서 이를 잡아 로컬 파일로 저장 + 사용자에게 알린다.
    """
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_BLOG_REPO"]
    branch = os.environ.get("GITHUB_BLOG_BRANCH", "main")

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    path = f"_drafts/{date_str}-{slug}.md"

    front_matter = (
        f"---\n"
        f'title: "{title}"\n'
        f"date: {date_str}\n"
        f"draft: true\n"
        f"---\n\n"
    )
    content = front_matter + body_markdown
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "message": f"StudyNote 초안: {title}",
        "content": content_b64,
        "branch": branch,
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.put(url, headers=headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                return resp.json()["content"]["html_url"]
            last_error = f"{resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            last_error = str(e)

    raise PublishError(f"발행 실패 ({max_retries + 1}회 시도): {last_error}")


def save_local_fallback(title: str, body_markdown: str, out_dir: str = "output") -> str:
    """발행 도구가 최종 실패했을 때의 대체 경로 — 로컬 파일로 저장."""
    os.makedirs(out_dir, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(title)
    path = os.path.join(out_dir, f"{date_str}-{slug}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{body_markdown}")
    return path