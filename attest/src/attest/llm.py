"""LLM 客户端 —— 纯管道，零依赖。

这一层刻意做得很薄：它只负责"把消息发出去、把结果拿回来、记账、卡预算"。
**没有任何评分逻辑** —— Judge 怎么设计（prompt、rubric 应用、证据引用、
追问生成）是第 1/2/6 章的学习内容，由你自己实现在 grade.py / defend.py 里。

给你这一层，是因为写一个 OpenAI 兼容的 HTTP 客户端没有学习价值，
不该占用你的 7.5 小时。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .spec import PROGRESS_DIR, REPO_ROOT

USAGE_LOG = PROGRESS_DIR / "llm-usage.jsonl"


class LLMError(RuntimeError):
    """基础设施错误 —— 方案 §5.5：不写分数，只记 last_error，保留上次有效结果。"""


class BudgetExceeded(LLMError):
    pass


# ---------------------------------------------------------------- 配置


def load_dotenv(path: Path | None = None) -> None:
    """极简 .env 加载，不覆盖已存在的环境变量。"""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip("'\""))


@dataclass
class Config:
    api_key: str
    base_url: str
    model: str
    price_in: float       # 元 / 百万 token
    price_out: float
    budget_cny: float

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        key = os.environ.get("LLM_API_KEY", "").strip()
        if not key:
            raise LLMError("LLM_API_KEY 未设置。复制 .env.example 为 .env 并填入。")
        return cls(
            api_key=key,
            base_url=os.environ.get("LLM_BASE_URL", "").rstrip("/"),
            model=os.environ.get("LLM_MODEL", ""),
            price_in=float(os.environ.get("LLM_PRICE_IN_CNY_PER_M", 2.0)),
            price_out=float(os.environ.get("LLM_PRICE_OUT_CNY_PER_M", 8.0)),
            budget_cny=float(os.environ.get("ATTEST_BUDGET_CNY", 60)),
        )


# ---------------------------------------------------------------- 记账


def spent_cny() -> float:
    if not USAGE_LOG.exists():
        return 0.0
    total = 0.0
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                total += json.loads(line).get("cost_cny", 0.0)
            except json.JSONDecodeError:
                continue
    return total


def _record(entry: dict) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- 调用


@dataclass
class Response:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_cny: float
    latency_s: float
    model: str

    def json(self) -> dict:
        """把返回解析成 JSON —— Judge 必须输出结构化结果（方案 §5.2）。"""
        raw = self.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Judge 输出不是合法 JSON：{exc}\n原文前 200 字：{raw[:200]}") from exc


def chat(
    messages: list[dict],
    *,
    tag: str = "",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    json_mode: bool = False,
    retries: int = 2,
    timeout: int = 120,
    cfg: Config | None = None,
) -> Response:
    """一次 chat completion。

    tag        记账用的标签，如 "grade:ch01" —— 看板按它统计每章成本
    json_mode  要求返回 JSON object（服务端支持时）
    retries    仅对超时/5xx 重试；4xx 不重试（方案 §5.5：基础设施错误 vs 学习结果）
    """
    cfg = cfg or Config.from_env()

    already = spent_cny()
    if already >= cfg.budget_cny:
        raise BudgetExceeded(
            f"累计花费 {already:.2f} 元已达预算上限 {cfg.budget_cny:.2f} 元。"
            f"调高 .env 的 ATTEST_BUDGET_CNY，或检查 progress/llm-usage.jsonl。"
        )

    payload = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg.base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if 400 <= exc.code < 500 and exc.code != 429:
                raise LLMError(f"HTTP {exc.code}（不重试）：{detail}") from exc
            last_exc = LLMError(f"HTTP {exc.code}：{detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = LLMError(f"{type(exc).__name__}: {exc}")
        if attempt < retries:
            time.sleep(2 ** attempt)
    else:
        raise last_exc or LLMError("未知失败")

    latency = time.time() - started
    usage = data.get("usage") or {}
    p_tok = int(usage.get("prompt_tokens", 0))
    c_tok = int(usage.get("completion_tokens", 0))
    cost = p_tok / 1e6 * cfg.price_in + c_tok / 1e6 * cfg.price_out

    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as exc:
        raise LLMError(f"返回结构异常：{json.dumps(data)[:300]}") from exc

    _record({
        "tag": tag,
        "model": cfg.model,
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "cost_cny": round(cost, 6),
        "latency_s": round(latency, 2),
    })

    return Response(text, p_tok, c_tok, cost, latency, cfg.model)


# ---------------------------------------------------------------- 自检


def ping() -> None:
    """attest ping —— 验证端点、密钥、模型是否可用，并报告成本与延迟。"""
    cfg = Config.from_env()
    print(f"\n  端点   {cfg.base_url}")
    print(f"  模型   {cfg.model}")
    print(f"  密钥   {cfg.api_key[:6]}…{cfg.api_key[-4:]}（{len(cfg.api_key)} 字符）")
    print(f"  预算   已花 {spent_cny():.4f} / {cfg.budget_cny:.2f} 元\n")
    try:
        r = chat(
            [{"role": "user", "content": "只回复两个字：可用"}],
            tag="ping", max_tokens=16, cfg=cfg,
        )
    except LLMError as exc:
        print(f"  ❌ 调用失败：{exc}\n")
        raise SystemExit(1)
    print(f"  ✅ 返回「{r.text.strip()}」")
    print(f"     {r.prompt_tokens} in / {r.completion_tokens} out"
          f" · {r.latency_s:.2f}s · {r.cost_cny:.6f} 元")
    per_chapter = r.cost_cny  # 仅占位提示，真实值由 grade/defend 产生
    print(f"     记账已写入 progress/llm-usage.jsonl\n"
          f"     （单次 ping 成本 {per_chapter:.6f} 元；全书目标 <60 元）\n")
