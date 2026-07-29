"""attest check —— 第 1 层：确定性检查。

方案 §5.2：本地、<2 秒、零成本、随时可跑。
写作过程中反复用它，而不是写完才发现结构不对。

判定顺序第 1 条（方案 §5.5）：这一层失败就直接 needs_work，**不调用 LLM**。
既明确又省钱。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .spec import REQUIRED_ARTIFACTS, TEMPLATE_DIR, find_unit, unit_dir

# ---------------------------------------------------------------- 结果模型

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Result:
    check: str
    status: str
    detail: str = ""
    items: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 工具

H2 = re.compile(r"^## +(.+?)\s*$", re.M)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|待填写|待补充|占位")
EMPTY_ROW = re.compile(r"^\|(?:\s*\|)+\s*$")

SECRET_PATTERNS = [
    (r"\bsk-[A-Za-z0-9]{20,}", "OpenAI 风格密钥"),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key"),
    (r"\b[a-f0-9]{32}\.[A-Za-z0-9_-]{16,}", "疑似 API key"),
    (r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\s]{16,}['\"]", "硬编码凭据"),
]


def _sections(text: str) -> dict[str, str]:
    """把 Markdown 按 H2 切成 {标题: 正文}。"""
    out, parts = {}, H2.split(text)
    for i in range(1, len(parts), 2):
        out[parts[i].strip()] = parts[i + 1]
    return out


def _is_blank(body: str) -> bool:
    """去掉 HTML 注释、空表格行、Markdown 骨架后是否为空。"""
    body = HTML_COMMENT.sub("", body)
    kept = []
    for line in body.splitlines():
        s = line.strip()
        if not s or EMPTY_ROW.match(s):
            continue
        if set(s) <= set("|-: "):          # 表头分隔线
            continue
        if re.fullmatch(r"(?:[-*+]|\d+\.)\s*", s):   # 空列表项
            continue
        if re.fullmatch(r"[^:：]{0,40}[:：]", s):     # "- 模型：" 这种未填字段
            continue
        if s.startswith("```"):
            continue
        kept.append(s)
    return not kept


def _template_h2(name: str) -> list[str]:
    """必需 H2 直接取自模板 —— 模板改了检查自动跟着改，不会漂移。"""
    raw = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    raw = raw.replace("{{MUST_ANSWER_BLOCK}}", "").replace("{{FIX_BLOCK}}", "")
    raw = re.sub(r"\{\{[A-Z_]+\}\}", "", raw)
    return [h.strip() for h in H2.findall(raw)]


# ---------------------------------------------------------------- 各项检查


def check_artifacts(d: Path) -> Result:
    missing = [f for f in REQUIRED_ARTIFACTS if not (d / f).exists()]
    if missing:
        return Result("六类产出齐套", FAIL, f"缺少 {len(missing)} 个", missing)
    return Result("六类产出齐套", PASS, f"{len(REQUIRED_ARTIFACTS)} 个产出均存在")


def check_sections(d: Path) -> Result:
    missing = []
    for name in REQUIRED_ARTIFACTS:
        path = d / name
        if not path.exists():
            continue
        have = {h.strip() for h in H2.findall(path.read_text(encoding="utf-8"))}
        for need in _template_h2(name):
            if need not in have:
                missing.append(f"{name} 缺少 H2「{need}」")
    if missing:
        return Result("必需小节存在", FAIL, f"{len(missing)} 处缺失", missing[:12])
    return Result("必需小节存在", PASS)


def check_placeholders(d: Path) -> Result:
    """占位符与空白必填段落。draft 阶段会大量命中，这是预期的。"""
    hits = []
    for name in REQUIRED_ARTIFACTS:
        path = d / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in PLACEHOLDER.finditer(HTML_COMMENT.sub("", text)):
            line = text[: m.start()].count("\n") + 1
            hits.append(f"{name}:{line} 占位符 {m.group(0)!r}")
        for title, body in _sections(text).items():
            if _is_blank(body):
                hits.append(f"{name} 小节「{title}」为空")
    if hits:
        return Result("无占位符 / 无空白必填", FAIL, f"{len(hits)} 处待填", hits[:15])
    return Result("无占位符 / 无空白必填", PASS)


def check_lab_results(d: Path) -> Result:
    summary = d / "lab" / "results" / "summary.json"
    if not summary.exists():
        return Result("机器可读结果", FAIL, "缺少 lab/results/summary.json")
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return Result("机器可读结果", FAIL, f"summary.json 不是合法 JSON：{exc}")
    if not data:
        return Result("机器可读结果", FAIL, "summary.json 为空")
    return Result("机器可读结果", PASS, f"{len(json.dumps(data))} 字节")


def check_evidence_index(d: Path) -> Result:
    """证据索引必须有真实行，且 path 指向的文件存在。"""
    problems = []
    for name in ("notes.md", "report.md", "article.md", "quiz.md"):
        path = d / name
        if not path.exists():
            continue
        secs = _sections(path.read_text(encoding="utf-8"))
        body = secs.get("证据索引")
        if body is None:
            problems.append(f"{name} 无证据索引")
            continue
        rows = [
            r for r in body.splitlines()
            if r.strip().startswith("|") and not EMPTY_ROW.match(r.strip())
            and set(r.strip()) - set("|-: ")
        ]
        rows = [r for r in rows if "claim" not in r]
        if not rows:
            problems.append(f"{name} 证据索引无真实行")
            continue
        for row in rows:
            cells = [c.strip().strip("`") for c in row.strip("|").split("|")]
            if len(cells) < 3 or not cells[2]:
                problems.append(f"{name} 证据行缺少 location：{row.strip()[:50]}")
            elif cells[1] and not (d / cells[1]).exists() and not Path(cells[1]).exists():
                problems.append(f"{name} 证据 path 不存在：{cells[1]}")
    if problems:
        return Result("证据索引可定位", FAIL, f"{len(problems)} 处", problems[:10])
    return Result("证据索引可定位", PASS)


def check_secrets(d: Path) -> Result:
    """唯一一个真正有安全价值的检查：防止 API Key 进仓库（方案 §5.1）。"""
    hits = []
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv", "results"}
    for path in d.rglob("*"):
        if not path.is_file() or set(path.parts) & skip:
            continue
        if path.suffix.lower() in {".png", ".jpg", ".wav", ".mp3", ".bin", ".pt", ".safetensors"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            for m in re.finditer(pattern, text):
                line = text[: m.start()].count("\n") + 1
                hits.append(f"{path.relative_to(d)}:{line} {label}")
    if hits:
        return Result("无密钥泄漏", FAIL, f"{len(hits)} 处 —— 必须先清理再提交", hits[:10])
    return Result("无密钥泄漏", PASS)


def check_numbers_grounded(d: Path) -> Result:
    """report.md / article.md 里出现的每个数字，必须能在 summary.json 中定位到。

    ┌─────────────────────────────────────────────────────────────┐
    │  这是 Day 3 的任务（学习方案 §9）—— 故意留给你实现。          │
    │                                                             │
    │  它防的是 T2「实验只跑通不分析」，是全套确定性检查里          │
    │  最有价值的一条：它让"报告里的数字"和"真实运行结果"          │
    │  不可能脱节。                                                │
    │                                                             │
    │  实现提示（这几个设计决定比代码本身更重要）：                 │
    │   1. 哪些数字要查？纯序号（第 1 章、Q3）、年份、             │
    │      Markdown 表格分隔线里的数字应排除                       │
    │   2. 容差多少？12.3% vs 0.123 vs 12.30 应视为同一个数        │
    │   3. summary.json 是嵌套的，要递归收集所有叶子数值           │
    │   4. 找不到时报告哪一行、哪个数字，而不是只说"失败"          │
    │                                                             │
    │  已经给你写好测试：attest/tests/test_numbers_grounded.py     │
    │  跑 `make test` 让它变绿即可。                               │
    └─────────────────────────────────────────────────────────────┘
    """
    return Result(
        "报告数字有据可查",
        WARN,
        "未实现 —— 见 check.py::check_numbers_grounded（Day 3 任务）",
    )


CHECKS = [
    check_artifacts,
    check_sections,
    check_placeholders,
    check_lab_results,
    check_evidence_index,
    check_secrets,
    check_numbers_grounded,
]


# ---------------------------------------------------------------- 入口


def run(unit_id: str, verbose: bool = True) -> tuple[bool, list[Result]]:
    unit = find_unit(unit_id)
    d = unit_dir(unit)
    if not d.exists():
        print(f"❌ evidence/{unit['id']}/ 不存在，先跑：make start CH={unit['num']}")
        return False, []

    results = [fn(d) for fn in CHECKS]
    ok = all(r.status != FAIL for r in results)

    if verbose:
        icon = {PASS: "✅", WARN: "⚠️ ", FAIL: "❌"}
        print(f"\n  attest check · 第 {unit['num']} 章 {unit['title']}")
        print("  " + "─" * 62)
        for r in results:
            print(f"  {icon[r.status]} {r.check}" + (f" —— {r.detail}" if r.detail else ""))
            for item in r.items:
                print(f"       · {item}")
            if r.items and len(r.items) >= 10:
                print("       · …（只显示前若干条）")
        print("  " + "─" * 62)
        n_fail = sum(1 for r in results if r.status == FAIL)
        if ok:
            print("  ✅ 确定性检查通过 —— 可以进入 attest grade\n")
        else:
            print(f"  ❌ {n_fail} 项未通过 -> needs_work（不会调用 LLM，先修这些）\n")
    return ok, results
