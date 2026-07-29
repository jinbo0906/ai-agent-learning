# Attest —— 常用命令入口
#
# Windows 没有 make 时，直接用等价的 python 命令（每条下面都标注了）。
# 前提：pip install -e ./attest

PY ?= python
CH ?= 1

.PHONY: help setup start start-all snapshot check status test lint clean

help:
	@echo ""
	@echo "  学习循环（方案 §3 五步）"
	@echo "    make start CH=1      ① 定标：实例化第 1 章证据包 + 打印本章要求"
	@echo "    make snapshot CH=1      快照书中默认实验到 evidence/ch01/lab/src/"
	@echo "    make check CH=1      ③ 随时跑：确定性检查（<2 秒，零成本）"
	@echo "    make status          全书进度与质量总览"
	@echo "    make test            跑测试（含 Day 3 任务的 TDD）"
	@echo ""
	@echo "  等价命令（无 make 时用）"
	@echo "    python -m attest start 1 / snapshot 1 / check 1 / status"
	@echo ""

setup:
	$(PY) -m pip install -e ./attest[dev]

start:
	$(PY) -m attest start $(CH)

start-all:
	$(PY) -m attest start all

snapshot:
	$(PY) -m attest snapshot $(CH)

check:
	$(PY) -m attest check $(CH)

status:
	$(PY) -m attest status

test:
	$(PY) -m pytest attest/tests -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
