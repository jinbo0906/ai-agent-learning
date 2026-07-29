"""课程规格与评分卡的加载层。

对应学习方案 §5.3 的三个抽象之 ①（Curriculum Spec）和 ②（Rubric Card）。
这一层刻意不认识"AI Agent Book"——换一本书只换 curriculum.yml。
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

# 仓库根目录：src/attest/spec.py -> attest/src/attest -> attest/src -> attest -> root
REPO_ROOT = Path(__file__).resolve().parents[3]
ATTEST_DIR = REPO_ROOT / "attest"
EVIDENCE_DIR = REPO_ROOT / "evidence"
PROGRESS_DIR = REPO_ROOT / "progress"
TEMPLATE_DIR = ATTEST_DIR / "templates"


class SpecError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def load_curriculum() -> dict:
    path = ATTEST_DIR / "curriculum.yml"
    if not path.exists():
        raise SpecError(f"课程规格不存在：{path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@functools.lru_cache(maxsize=4)
def load_rubric(rubric_id: str = "engineering-book") -> dict:
    path = ATTEST_DIR / "rubrics" / f"{rubric_id}.yml"
    if not path.exists():
        raise SpecError(f"评分卡不存在：{path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def units() -> list[dict]:
    return load_curriculum()["units"]


def find_unit(unit_id: str) -> dict:
    """支持 ch01 / ch1 / 1 三种写法。"""
    raw = str(unit_id).strip().lower()
    if raw.isdigit():
        raw = f"ch{int(raw):02d}"
    elif raw.startswith("ch") and raw[2:].isdigit():
        raw = f"ch{int(raw[2:]):02d}"
    for unit in units():
        if unit["id"] == raw:
            return unit
    known = ", ".join(u["id"] for u in units())
    raise SpecError(f"未知章节 {unit_id!r}；可用：{known}")


def unit_dir(unit: dict) -> Path:
    return EVIDENCE_DIR / unit["id"]


def book_repo() -> Path:
    """书稿与配套实验所在仓库的绝对路径。"""
    return (REPO_ROOT / load_curriculum()["meta"]["book_repo"]).resolve()


# 每章证据包必须存在的六类产出（方案 §2.3 / §5.2）
REQUIRED_ARTIFACTS = ["notes.md", "report.md", "article.md", "quiz.md", "defense.md"]
REQUIRED_LAB = ["lab/results", "lab/src", "lab/tests"]
