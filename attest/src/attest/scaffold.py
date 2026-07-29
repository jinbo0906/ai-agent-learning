"""attest start —— 从课程规格实例化一章的证据包。

这是方案 §3「标准五步」的第 ① 步：定标。
把课程规格里该章的目标、必答问题、实验要求、修正项和文章命题
直接写进证据文件，让你打开 notes.md 就知道要答什么，不用回来查规格。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .spec import (
    REQUIRED_LAB,
    TEMPLATE_DIR,
    book_repo,
    load_curriculum,
    find_unit,
    unit_dir,
    units,
)

# ---------------------------------------------------------------- 渲染块


def _must_answer_block(unit: dict) -> str:
    out = []
    for i, q in enumerate(unit.get("must_answer", []), 1):
        out.append(f"### Q{i}. {q}\n\n<!-- 答案要落到机制层面 -->\n")
    return "\n".join(out) if out else "<!-- 本章无必答问题 -->\n"


def _connects_block(unit: dict) -> str:
    conns = unit.get("connects_to") or []
    if not conns:
        return ""
    lines = ["## 与前置章节的连接\n", "<!-- 课程规格要求的跨章迁移点，必须在文章里回看一次 -->\n"]
    for c in conns:
        lines.append(f"- **{c['unit']}** · {c['topic']}：")
    return "\n".join(lines) + "\n"


def _connects_quiz_block(unit: dict) -> str:
    conns = unit.get("connects_to") or []
    if not conns:
        return "<!-- 本章是起点，无前置连接。请说明它为后续哪一章埋了伏笔。 -->"
    items = "\n".join(f"- 必须连接 **{c['unit']}** 的「{c['topic']}」：" for c in conns)
    return f"<!-- 课程规格要求的连接点，逐条作答 -->\n\n{items}"


def _lab_line(unit: dict, depth: int) -> str:
    lab = unit.get("default_lab") or {}
    path, status = lab.get("path"), lab.get("status", "ok")
    up = "../" * depth
    if not path:
        note = lab.get("note", "")
        return f"⚠️ **本章无固定默认实验** —— {note}\n>\n> 见下方「实验路径修正」，按你的算力条件三选一。"
    mark = {"ok": "✅", "warn": "⚠️", "fix": "🔧"}.get(status, "")
    note = f" —— {lab['note']}" if lab.get("note") else ""
    return f"[`{path}`]({up}{path}/) {mark}{note}"


def _lab_requirements_block(unit: dict) -> str:
    reqs = list(unit.get("lab_requirements") or [])
    # 第 7 章没有统一的 lab_requirements —— 三条算力路径共享同一组硬要求
    if not reqs:
        reqs = list((unit.get("fix") or {}).get("hard_requirements") or [])
    lines = [f"- [ ] {r}" for r in reqs]
    if unit.get("budget_note"):
        lines.append(f"\n> ⏱️ {unit['budget_note']}")
    return "\n".join(lines) if lines else "<!-- 无 -->"


def _fix_block(unit: dict) -> str:
    """第 6 / 7 / 9 章的实验可行性修正，直接写进报告，避免踩坑。"""
    fix = unit.get("fix")
    if not fix:
        return ""
    out = [f"## ⚠️ 实验路径修正（修正 {fix['id']}）\n", f"**问题**：{fix['problem']}\n"]

    if fix.get("resolution"):
        out.append(f"**处理**：{fix['resolution']}\n")
    for step in fix.get("steps", []):
        out.append(f"- [ ] {step}")
    if fix.get("bonus"):
        out.append(f"\n> 💡 {fix['bonus']}")

    if fix.get("hard_requirements"):
        out.append("\n**三条路径都必须满足的硬要求**：\n")
        out += [f"- [ ] {r}" for r in fix["hard_requirements"]]
    for p in fix.get("paths", []):
        out.append(f"\n### 路径 {p['id']}：{p['condition']}\n")
        if p.get("lab"):
            out.append(f"- 实验目录：`{p['lab']}`")
        out.append(f"- 做法：{p['how']}")
        if p.get("better"):
            out.append(f"- 💡 {p['better']}")

    for d in fix.get("decision_tree", []):
        out.append(f"\n- **{d['condition']}** → {d['action']}")

    out.append("\n**我选择的路径**：<!-- 填这里，并说明理由 -->\n")
    return "\n".join(out) + "\n"


def _article_must_include_block(unit: dict) -> str:
    items = (unit.get("article") or {}).get("must_include", [])
    return "\n".join(f"- [ ] {i}" for i in items) if items else "<!-- 无 -->"


def _quiz_anchors_block(unit: dict) -> str:
    out = []
    for i, q in enumerate(unit.get("quiz_anchors", []), 1):
        out.append(f"### A{i}. {q}\n\n答案：\n\n不确定项：\n")
    return "\n".join(out) if out else "<!-- 本章无锚点题 -->\n"


# ---------------------------------------------------------------- 渲染


def _vars(unit: dict, depth: int) -> dict[str, str]:
    week = unit.get("week", [])
    week_s = f"{week[0]}–{week[-1]}" if len(week) > 1 else (str(week[0]) if week else "?")
    return {
        "ID": unit["id"],
        "NO": str(unit["num"]),
        "TITLE": unit["title"],
        "SOURCE": unit["source"],
        "BOOK_REPO": "../" * depth + "..",
        "CJK": f"{unit.get('cjk_chars', 0):,}",
        "READ_HOURS": str(unit.get("read_hours", "?")),
        "LEVEL": unit.get("level", ""),
        "WEEK": week_s,
        "MUST_ANSWER_COUNT": str(len(unit.get("must_answer", []))),
        "MUST_ANSWER_BLOCK": _must_answer_block(unit),
        "CONNECTS_BLOCK": _connects_block(unit),
        "CONNECTS_QUIZ_BLOCK": _connects_quiz_block(unit),
        "LAB_LINE": _lab_line(unit, depth),
        "LAB_REQUIREMENTS_BLOCK": _lab_requirements_block(unit),
        "FIX_BLOCK": _fix_block(unit),
        "ARTICLE_TITLE": (unit.get("article") or {}).get("title", unit["title"]),
        "ARTICLE_MUST_INCLUDE_BLOCK": _article_must_include_block(unit),
        "QUIZ_ANCHORS_BLOCK": _quiz_anchors_block(unit),
    }


def render(template_name: str, unit: dict, depth: int = 2) -> str:
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    for key, value in _vars(unit, depth).items():
        text = text.replace("{{" + key + "}}", value)
    return text


# ---------------------------------------------------------------- 落盘


def _init_state(unit: dict) -> dict:
    return {
        "unit": unit["id"],
        "status": "draft",  # draft | needs_work | done
        "started_at": None,
        "done_at": None,
        "self_score": {"concepts": None, "scenario": None, "experiment": None, "teachback": None},
        "judge_score": {"concepts": None, "scenario": None, "experiment": None, "teachback": None},
        "total": None,
        "calibration_error": None,
        "article_score": None,
        "defense": {"rounds": 0, "completed": False},
        "attempts": 0,
        "gates": {"deterministic": None, "defense": None, "score": None},
        "review_due": [],
        "last_error": None,
        "attest_milestone": (unit.get("attest_milestone") or {}).get("version"),
    }


def start(unit_id: str, force: bool = False) -> Path:
    unit = find_unit(unit_id)
    target = unit_dir(unit)
    target.mkdir(parents=True, exist_ok=True)

    written, skipped = [], []
    for tmpl in ("notes.md", "report.md", "article.md", "quiz.md", "defense.md"):
        dest = target / tmpl
        if dest.exists() and not force:
            skipped.append(tmpl)
            continue
        dest.write_text(render(tmpl, unit), encoding="utf-8")
        written.append(tmpl)

    for sub in REQUIRED_LAB:
        d = target / sub
        d.mkdir(parents=True, exist_ok=True)
        keep = d / ".gitkeep"
        if not any(p for p in d.iterdir() if p.name != ".gitkeep"):
            keep.touch()

    # reproduce.json —— 复现契约，attest check v1 会真的执行它
    repro = target / "lab" / "reproduce.json"
    if not repro.exists() or force:
        repro.write_text(
            json.dumps(
                {
                    "argv": [],
                    "cwd": ".",
                    "env_file": "../../../.env",
                    "expect": {"results": "results/summary.json"},
                    "timeout_seconds": 1800,
                    "_note": "填 argv 后 attest check 会在沙箱里执行它并比对 results",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    state_dir = target / ".attest"
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "state.json"
    if not state_file.exists() or force:
        state_file.write_text(
            json.dumps(_init_state(unit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    _print_briefing(unit, written, skipped)
    return target


def snapshot_lab(unit_id: str) -> Path | None:
    """把课程规格里的 default_lab 快照到本章 lab/src/，并记录来源。

    书中原始实验目录是只读基线，所有改动都发生在这份快照里。
    """
    unit = find_unit(unit_id)
    lab = unit.get("default_lab") or {}
    rel = lab.get("path")
    if not rel:
        print(f"⚠️  {unit['id']} 没有固定默认实验（见 report.md 的实验路径修正），跳过快照")
        return None

    src = book_repo() / rel
    if not src.exists():
        print(f"❌ 源目录不存在：{src}")
        return None

    dst = unit_dir(unit) / "lab" / "src"
    if any(p.name != ".gitkeep" for p in dst.iterdir()) if dst.exists() else False:
        print(f"⚠️  {dst} 已有内容，跳过（要重来先手工清空）")
        return dst

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".git", ".venv", "venv", "node_modules", "*.egg-info"
    ))
    (unit_dir(unit) / "lab" / "provenance.json").write_text(
        json.dumps(
            {
                "source": rel,
                "source_repo": load_curriculum()["meta"]["book_repo"],  # 相对路径，便于他人复现
                "upstream": load_curriculum()["meta"].get("upstream"),
                "target": "lab/src",
                "mode": "snapshot",
                "_note": "书中原始目录是只读基线；所有学习改动只写这份快照",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"✅ 已快照 {rel} -> {dst.relative_to(dst.parents[3])}")
    return dst


def _print_briefing(unit: dict, written: list[str], skipped: list[str]) -> None:
    week = unit.get("week", [])
    week_s = f"{week[0]}–{week[-1]}" if len(week) > 1 else (str(week[0]) if week else "?")
    bar = "─" * 64
    print(f"\n{bar}\n  第 {unit["num"]} 章 · {unit['title']}\n{bar}")
    print(f"  正文 {unit.get('cjk_chars', 0):,} 字 · 建议阅读 {unit.get('read_hours')} h "
          f"· 难度 {unit.get('level')} · 第 {week_s} 周")
    if unit.get("note"):
        print(f"  📌 {unit['note']}")
    if unit.get("positioning"):
        print(f"\n  【本章定位】{unit['positioning']}")

    print("\n  学习目标：")
    for o in unit.get("objectives", []):
        print(f"    · {o}")

    print("\n  必答问题：")
    for i, q in enumerate(unit.get("must_answer", []), 1):
        print(f"    {i}. {q}")

    lab = unit.get("default_lab") or {}
    print("\n  默认实验：", end="")
    if lab.get("path"):
        mark = {"ok": "✅", "warn": "⚠️", "fix": "🔧"}.get(lab.get("status", "ok"), "")
        print(f"{lab['path']} {mark}")
        if lab.get("note"):
            print(f"    {lab['note']}")
    else:
        print(f"🔧 无固定默认实验 —— {lab.get('note', '')}")

    if unit.get("fix"):
        print(f"\n  ⚠️  本章有实验可行性修正（修正 {unit['fix']['id']}），详见 report.md")

    ms = unit.get("attest_milestone") or {}
    if ms:
        tag = " ★核心" if ms.get("critical") else (" (可选)" if ms.get("optional") else "")
        print(f"\n  装进 Attest：{ms['version']}{tag}\n    {ms['what']}")

    if unit.get("connects_to"):
        print("\n  必须连接的前置主题：")
        for c in unit["connects_to"]:
            print(f"    · {c['unit']} — {c['topic']}")

    print(f"\n{bar}")
    if written:
        print(f"  ✅ 已生成：{', '.join(written)}")
    if skipped:
        print(f"  ⏭️  已存在跳过：{', '.join(skipped)}（要覆盖用 --force）")
    print(f"  📁 evidence/{unit['id']}/\n{bar}\n")


def start_all(force: bool = False) -> None:
    for unit in units():
        start(unit["id"], force=force)
