"""学习进度检查应区分真实待填项和正文中的术语。"""

from attest.check import FAIL, PASS, check_placeholders


UNIT = {"id": "ch02", "num": 2}


def test_todo_discussion_and_code_are_not_placeholders(tmp_path):
    (tmp_path / "notes.md").write_text(
        "# 笔记\n\n## 读之前我怎么想\n"
        "TODO 列表是状态栏的一种，能帮助 Agent 记住目标。\n\n"
        "## 一句话核心主张\n结构化状态比滑动窗口更可靠。\n\n"
        "## 我还不懂的\n待验证：多长的轨迹才需要压缩？\n\n"
        "```text\n- TODO: [1] Cancel plan\n```\n",
        encoding="utf-8",
    )

    assert check_placeholders(tmp_path, UNIT).status == PASS


def test_standalone_todo_is_still_reported(tmp_path):
    (tmp_path / "notes.md").write_text(
        "## 读之前我怎么想\nTODO\n", encoding="utf-8"
    )

    result = check_placeholders(tmp_path, UNIT)
    assert result.status == FAIL
    assert any("TODO" in item for item in result.items)


def test_later_stage_items_are_not_dropped_after_many_earlier_items(tmp_path):
    (tmp_path / "notes.md").write_text(
        "## 读之前我怎么想\n" + "TODO\n" * 20,
        encoding="utf-8",
    )
    (tmp_path / "quiz.md").write_text(
        "# 自测\n\n## Part B · 场景与代码（30）\n"
        "<!-- 留给学习者作答 -->\n",
        encoding="utf-8",
    )

    result = check_placeholders(tmp_path, UNIT)
    assert result.status == FAIL
    assert any("quiz.md · Part B" in item for item in result.items)


def test_unanswered_subquestions_do_not_complete_quiz_part_a(tmp_path):
    (tmp_path / "quiz.md").write_text(
        "## Part A · 概念（25）\n\n"
        "### A1. KV Cache 与 Prompt Cache 有何区别？\n\n答案：\n\n"
        "### A2. 滑动窗口为什么会重复调用？\n\n答案：\n",
        encoding="utf-8",
    )

    result = check_placeholders(tmp_path, UNIT)
    assert result.status == FAIL
    assert any("quiz.md · Part A" in item for item in result.items)
