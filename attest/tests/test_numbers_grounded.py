"""Day 3 任务的测试（学习方案 §9）。

`check_numbers_grounded` 目前返回 WARN（未实现）。
你的任务：实现它，让这个文件全绿。

跑：  make test
或：  python -m pytest attest/tests -v

为什么这条检查最重要：它防的是 T2「实验只跑通不分析」——
让"报告里的数字"和"真实运行结果"不可能脱节。
没有它，整套证据体系是自我声明的；有了它，报告就被钉死在 summary.json 上。
"""

from __future__ import annotations

import json

import pytest

from attest.check import FAIL, PASS, check_numbers_grounded

REPORT_HEAD = "# 第 1 章 · 实验报告\n\n## 结果\n\n"


def _make(tmp_path, report_body: str, summary: dict):
    (tmp_path / "lab" / "results").mkdir(parents=True)
    (tmp_path / "lab" / "results" / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "report.md").write_text(REPORT_HEAD + report_body, encoding="utf-8")
    return tmp_path


def test_所有数字都有出处时通过(tmp_path):
    d = _make(
        tmp_path,
        "完整上下文成功率 0.82，移除工具结果后降到 0.54，平均步数 6.3。\n",
        {"full": {"success_rate": 0.82, "avg_steps": 6.3}, "no_tool_result": {"success_rate": 0.54}},
    )
    assert check_numbers_grounded(d).status == PASS


def test_编造的数字被拦截(tmp_path):
    d = _make(
        tmp_path,
        "成功率从 0.82 提升到 0.97。\n",  # 0.97 不在结果里
        {"full": {"success_rate": 0.82}},
    )
    r = check_numbers_grounded(d)
    assert r.status == FAIL
    assert "0.97" in (r.detail + " ".join(r.items))


def test_序号与年份不算指标(tmp_path):
    """第 1 章、Q3、2026 年这类数字不该触发失败。"""
    d = _make(
        tmp_path,
        "见第 1 章 Q3 的讨论（2026 年 7 月）。成功率 0.82。\n",
        {"success_rate": 0.82},
    )
    assert check_numbers_grounded(d).status == PASS


def test_百分号与小数视为同一个数(tmp_path):
    """12.3% 与 0.123 应能互相匹配，否则会有大量假失败。"""
    d = _make(tmp_path, "token 降幅 12.3%。\n", {"token_reduction": 0.123})
    assert check_numbers_grounded(d).status == PASS


def test_嵌套结果也能找到(tmp_path):
    d = _make(
        tmp_path,
        "第三组配置的延迟 1240 ms。\n",
        {"runs": [{"cfg": "a"}, {"cfg": "c", "metrics": {"latency_ms": 1240}}]},
    )
    assert check_numbers_grounded(d).status == PASS


def test_报错要指出是哪一行哪个数(tmp_path):
    d = _make(tmp_path, "第一行 0.82。\n\n第二行 9.99。\n", {"success_rate": 0.82})
    r = check_numbers_grounded(d)
    assert r.status == FAIL
    blob = r.detail + " ".join(r.items)
    assert "9.99" in blob, "必须指出具体是哪个数字对不上"


@pytest.mark.xfail(reason="进阶：容差策略。实现时自行决定 0.8200001 是否算命中", strict=False)
def test_浮点容差(tmp_path):
    d = _make(tmp_path, "成功率 0.82。\n", {"success_rate": 0.8200001})
    assert check_numbers_grounded(d).status == PASS
