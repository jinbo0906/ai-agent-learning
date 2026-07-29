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
    body = re.sub(r"<!--.*", "", body, flags=re.S)  # 被分界线截断的半截注释
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


# 模板里这行以下的内容全部是可选的，check 不管
OPTIONAL_MARKER = "attest:optional-below"


def _template_h2(name: str) -> list[str]:
    """必填 H2 取自模板中 optional 分界线**以上**的部分。

    模板改了检查自动跟着改，不会漂移；把一节移到分界线以下即可让它变成可选。
    """
    raw = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    raw = raw.split(OPTIONAL_MARKER, 1)[0]
    raw = re.sub(r"\{\{[A-Z_]+\}\}", "", raw)
    return [h.strip() for h in H2.findall(raw)]


# ---------------------------------------------------------------- 各项检查


def check_artifacts(d: Path, unit: dict) -> Result:
    missing = [f for f in REQUIRED_ARTIFACTS if not (d / f).exists()]
    if missing:
        return Result("六类产出齐套", FAIL, f"缺少 {len(missing)} 个", missing)
    return Result("六类产出齐套", PASS, f"{len(REQUIRED_ARTIFACTS)} 个产出均存在")


def check_sections(d: Path, unit: dict) -> Result:
    missing = []
    for name in REQUIRED_ARTIFACTS:
        path = d / name
        if not path.exists():
            continue
        have = {h.strip() for h in H2.findall(path.read_text(encoding="utf-8"))}
        for need in _template_h2(name):
            if need not in have:
                missing.append(f"{name} 缺少「{need}」")
    if missing:
        return Result("必填小节存在", FAIL, f"{len(missing)} 处缺失", missing[:12])
    return Result("必填小节存在", PASS)


def check_placeholders(d: Path, unit: dict) -> Result:
    """只检查**必填**小节是否还空着。

    可选小节（模板 optional 分界线以下、或你自己加的）一律不管 ——
    模板是笔记本，不是必须填满的表格。
    """
    todo = []
    for name in REQUIRED_ARTIFACTS:
        path = d / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        required = set(_template_h2(name))
        # optional 分界线以下的内容整体跳过
        head = text.split(OPTIONAL_MARKER, 1)[0]
        for m in PLACEHOLDER.finditer(HTML_COMMENT.sub("", head)):
            line = text[: m.start()].count("\n") + 1
            todo.append(f"{name}:{line} 占位符 {m.group(0)!r}")
        for title, body in _sections(head).items():
            if title in required and _is_blank(body):
                todo.append(f"{name} · {title}")
    if todo:
        return Result("必填项已完成", FAIL, f"还差 {len(todo)} 项", todo[:15])
    return Result("必填项已完成", PASS)


H3 = re.compile(r"^### +(.+?)\s*$", re.M)


def check_must_answer(d: Path, unit: dict) -> Result:
    """必答问题逐题作答 —— 这是全章最核心的检验点，不能只有标题没有答案。

    答不出来写"我不确定，因为……"也算数（那是真实的学习状态，是有用的数据），
    但不能整段空着。
    """
    questions = unit.get("must_answer") or []
    if not questions:
        return Result("必答问题已作答", PASS, "本章无必答问题")

    path = d / "notes.md"
    if not path.exists():
        return Result("必答问题已作答", FAIL, "notes.md 不存在")

    body = _sections(path.read_text(encoding="utf-8")).get("必答问题", "")
    parts = H3.split(body)
    answered, unanswered = 0, []
    for i in range(1, len(parts), 2):
        title, ans = parts[i].strip(), parts[i + 1]
        if _is_blank(ans):
            unanswered.append(f"notes.md · {title[:46]}")
        else:
            answered += 1

    total = len(questions)
    if unanswered:
        return Result(
            "必答问题已作答", FAIL, f"{answered}/{total} 题已答", unanswered
        )
    return Result("必答问题已作答", PASS, f"{answered}/{total} 题")


def check_lab_results(d: Path, unit: dict) -> Result:
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


def check_secrets(d: Path, unit: dict) -> Result:
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


def check_numbers_grounded(d: Path, unit: dict) -> Result:
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
    check_must_answer,
    check_placeholders,
    check_lab_results,
    check_secrets,
    check_numbers_grounded,
]
# check_evidence_index 已移除：证据索引改为可选。
# 真正防"只跑通不分析"的是 check_numbers_grounded（数字必须能追溯到 summary.json），
# 那是机制性的；证据索引表是审计产物，对个人学习是纯负担。


# ---------------------------------------------------------------- 入口


# 五步循环（方案 §3）—— 每步对应哪些产出，以及这一步该做什么
STAGES = [
    ("① 读书", ("notes.md",), "读正文，把 notes.md 的几块填上"),
    ("② 实验", ("report.md", "summary.json", "lab"), "跑基线、改一个变量、记录结果"),
    ("③ 表达", ("article.md",), "把实验里最意外的那个数据写成一个主张"),
    ("④ 验收", ("quiz.md", "defense.md"), "自测 + 答辩"),
]


def _stage_of(item: str) -> int:
    for i, (_, keys, _) in enumerate(STAGES):
        if any(k in item for k in keys):
            return i
    return len(STAGES) - 1


def run(unit_id: str, verbose: bool = True, all_stages: bool = False) -> tuple[bool, list[Result]]:
    unit = find_unit(unit_id)
    d = unit_dir(unit)
    if not d.exists():
        print(f"❌ evidence/{unit['id']}/ 不存在，先跑：make start CH={unit['num']}")
        return False, []

    results = [fn(d, unit) for fn in CHECKS]
    ok = all(r.status != FAIL for r in results)

    if not verbose:
        return ok, results

    # 待办按五步循环分组，只展开当前这一步 —— 一次看到全部会变成负担
    todo: list[list[str]] = [[] for _ in STAGES]
    blockers: list[Result] = []
    for r in results:
        if r.status != FAIL:
            continue
        if r.items:
            for item in r.items:
                todo[_stage_of(item)].append(item)
        else:
            (todo[_stage_of(r.detail or r.check)] if r.detail else blockers).append(
                r.detail or r.check
            )

    current = next((i for i, t in enumerate(todo) if t), None)

    print(f"\n  第 {unit['num']} 章 · {unit['title']}")
    print("  " + "─" * 60)
    for i, (name, _, hint) in enumerate(STAGES):
        n = len(todo[i])
        if n == 0:
            print(f"  {name}   ✅ 完成")
            continue
        if i == current:
            print(f"  {name}   ◐ 进行中 —— 还差 {n} 项")
            for item in todo[i][:10]:
                print(f"           · {item}")
            if n > 10:
                print(f"           · …还有 {n - 10} 项")
        else:
            print(f"  {name}   ○ 未开始（{n} 项）" + ("" if all_stages else "  ⟵ 先别管"))
            if all_stages:
                for item in todo[i][:10]:
                    print(f"           · {item}")

    sec = next((r for r in results if r.check == "无密钥泄漏"), None)
    if sec and sec.status == FAIL:
        print(f"\n  ❌ 安全：{sec.detail}")
        for item in sec.items:
            print(f"       · {item}")
    for b in blockers:
        print(f"\n  ❌ {b}")

    print("  " + "─" * 60)
    if ok:
        print("  ✅ 全部完成 —— 可以进入 attest grade\n")
    elif current is not None:
        print(f"  → 现在做：{STAGES[current][2]}")
        print("     后面几步先别管，做到那一步 check 会告诉你。")
        print("     （想看全部：attest check %s --all）\n" % unit["num"])
    else:
        print("  ❌ 见上方阻塞项\n")
    return ok, results
