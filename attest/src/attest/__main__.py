"""Attest CLI —— 证据驱动的学习监督系统。

用法：python -m attest <command> [args]

已实现（v0）：
  start [N|all]    实例化章节证据包，打印本章目标 / 必答问题 / 实验要求
  snapshot N       把书中默认实验快照到 evidence/chNN/lab/src/
  check N          第 1 层确定性检查（<2 秒，零成本，随时可跑）
  status           全书进度与质量总览
  ping             验证 LLM 端点、密钥、模型可用，并报告成本与延迟

待实现（跟着学习进度长出来，见 attest/README.md）：
  selfscore N      先自评四维分数（在 grade 之前）—— 校准误差的输入
  quiz N           生成本章测试
  grade N          第 2 层四维语义评分
  defend N         第 3 层交互式答辩（2 个追问）
  review           到期的 D+2 / D+7 / D+21 复习
  board            生成本地 HTML 看板
"""

from __future__ import annotations

import json
import sys

from .spec import find_unit, unit_dir, units

# Windows 控制台默认 GBK，输出 emoji / 制表符会 UnicodeEncodeError。
# 证据文件本身始终以 UTF-8 读写，这里只修终端输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # 非 TTY 或旧版本，忽略
        pass

_TODO = {
    "selfscore": ("v0", "先自评四维分数，写入 .attest/state.json 的 self_score"),
    "quiz": ("v0", "基于正文 + 你的笔记 + 你的实验 + 历史错题生成本章测试"),
    "grade": ("v0", "第 2 层四维评分，输出分数 + 理由 + 证据 + 校准误差"),
    "defend": ("v0", "第 3 层交互式答辩：2 个针对你本人提交的追问，终端作答，即时评分"),
    "review": ("v1", "到期的 D+2 / D+7 / D+21 复习题"),
    "board": ("v1", "生成本地 HTML 看板"),
    "publish": ("v2", "导出通过发布门的成果（脱敏）"),
}


def cmd_status() -> None:
    rows = []
    for unit in units():
        state_file = unit_dir(unit) / ".attest" / "state.json"
        if state_file.exists():
            s = json.loads(state_file.read_text(encoding="utf-8"))
        else:
            s = {"status": "-", "total": None, "calibration_error": None}
        rows.append((unit, s))

    icon = {"draft": "○", "needs_work": "◐", "done": "●", "-": " "}
    print(f"\n  Attest · 学习进度\n  {'─' * 74}")
    print(f"  {'章':<4}{'标题':<24}{'状态':<12}{'总分':>6}{'校准误差':>10}  Attest")
    print(f"  {'─' * 74}")
    done = 0
    totals = []
    for unit, s in rows:
        st = s.get("status", "-")
        if st == "done":
            done += 1
        if s.get("total"):
            totals.append(s["total"])
        title = unit["title"]
        pad = 24 - sum(2 if ord(c) > 0x2E80 else 1 for c in title)
        ms = (unit.get("attest_milestone") or {}).get("version", "")
        print(f"  {unit['num']:<4}{title}{' ' * max(pad, 1)}"
              f"{icon.get(st, '?')} {st:<10}"
              f"{s.get('total') or '-':>6}"
              f"{s.get('calibration_error') or '-':>10}  {ms}")
    print(f"  {'─' * 74}")
    avg = sum(totals) / len(totals) if totals else 0
    print(f"  完成 {done}/10 章" + (f" · 平均分 {avg:.1f}" if totals else ""))

    lv = "—"
    if done == 10 and avg >= 80:
        lv = "🥈 银"
    elif done >= 8 and avg >= 75:
        lv = "🥉 铜"
    print(f"  当前级别：{lv}   （铜 >=8章/75 · 银 10章/80 · 金 银+3旗舰+v3+总复盘）\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    cmd, args = argv[0], argv[1:]
    force = "--force" in args
    all_stages = "--all" in args
    args = [a for a in args if not a.startswith("-")]

    if cmd == "start":
        from .scaffold import start, start_all
        if args and args[0] == "all":
            start_all(force=force)
        elif args:
            start(args[0], force=force)
        else:
            print("用法：python -m attest start <N|all>")
            return 2
        return 0

    if cmd == "snapshot":
        from .scaffold import snapshot_lab
        if not args:
            print("用法：python -m attest snapshot <N>")
            return 2
        snapshot_lab(args[0])
        return 0

    if cmd == "check":
        from .check import run
        if not args:
            print("用法：python -m attest check <N>")
            return 2
        ok, _ = run(args[0], all_stages=all_stages)
        return 0 if ok else 1

    if cmd == "ping":
        from .llm import ping
        ping()
        return 0

    if cmd == "status":
        cmd_status()
        return 0

    if cmd in _TODO:
        ver, what = _TODO[cmd]
        unit_hint = f" {args[0]}" if args else ""
        print(f"\n  ⏳ `attest {cmd}{unit_hint}` 尚未实现（计划 Attest {ver}）")
        print(f"     {what}")
        print("     版本路线见 attest/README.md —— 它跟着你的学习进度长出来，")
        print("     不要提前实现：每一章学完才知道这一步该怎么建。\n")
        return 3

    print(f"未知命令 {cmd!r}\n")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
