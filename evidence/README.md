# 证据包（Evidence Bundle）

> 三个可泛化抽象之 ③。目录约定与学科无关 —— 换一门课，这个结构不变。

## 每章的结构

```
evidence/ch01/
├── notes.md            学习笔记（私有性质，允许并鼓励写"我不懂"）
├── report.md           实验报告（数字必须能在 summary.json 定位到）
├── article.md          逐章公开文章（唯一对外发布的产出）
├── quiz.md             章节测试作答（四部分 25/30/25/20）
├── defense.md          个性化答辩记录（防 AI 代写的核心机制）
├── lab/
│   ├── src/            书中默认实验的**快照** —— 所有改动只写这里
│   ├── provenance.json 快照来源（书中原始目录是只读基线，不回写）
│   ├── reproduce.json  复现契约：argv / cwd / 环境 / 预期结果
│   ├── results/
│   │   └── summary.json   机器可读结果 ← 整套证据体系钉在这个文件上
│   └── tests/          回归测试
└── .attest/
    └── state.json      状态 / 自评 / Judge 评分 / 校准误差 / 复习排期
```

## 核心规则

1. **书中原始实验目录是只读基线。** `attest snapshot N` 把它复制到 `lab/src/`，
   所有消融、深改、测试都在快照里进行，`lab/provenance.json` 记录来源。
   这样既不污染书中基线，也让复现命令不依赖仓库外的隐式路径。

2. **`summary.json` 是证据体系的锚点。** 报告和文章里出现的每个数字，
   都必须能在它里面定位到。`attest check` 会交叉验证，对不上直接判 `needs_work`。
   没有这条，整套证据是自我声明的。

3. **证据索引用 `claim / path / location` 三列。** `location` 必须能唯一定位：
   Markdown 标题 + 出现序号、JSON Pointer 或行锚点。裸文件路径和"见仓库"不合格。

4. **失败轨迹和成功轨迹一样重要。** 只有成功案例的实验报告不通过。

5. **`notes.md` 是私有的。** 只有 `article.md` 会通过 `attest publish` 对外。
   笔记里的诚实度决定这套方法的全部价值 —— 不要因为怕公开而美化自己的理解。

## 状态

| 状态 | 含义 |
| --- | --- |
| `draft` | 起草中。`attest check` 会大量报错，这是**预期的** —— 失败清单就是你的待办清单 |
| `needs_work` | 确定性检查失败 / 答辩未完成 / 分数不达标 |
| `done` | 三道门全过：确定性检查全绿 + 答辩完成 + 总分 ≥80 且每维 ≥60% |

## 常用命令

```bash
make start CH=1        # 实例化第 1 章 + 打印本章目标/必答问题/实验要求
make snapshot CH=1     # 把 chapter1/context 快照到 lab/src/
make check CH=1        # 随时跑：<2 秒，零成本
make status            # 全书总览
```

## 十章一览

| 章 | 标题 | 正文字数 | 阅读 | 默认实验 | Attest |
| ---: | --- | ---: | ---: | --- | --- |
| 1 | AI Agent 基础 | 18,911 | 1.5h | `chapter1/context` ✅ | v0 |
| 2 | 上下文工程 | 33,978 | 2.5h | `chapter2/context-compression` ⚠️ | v0.5 |
| 3 | 用户记忆和知识库 | 27,936 | 2.0h | `chapter3/retrieval-pipeline` ✅ | v1 |
| 4 | 工具 | 27,814 | 2.0h | `chapter4/active-tool-discovery` ✅ | v1.5 |
| 5 | Coding Agent | 29,640 | 2.0h | `chapter5/coding-agent` ✅ | v2 |
| 6 | Agent 的评估 | 26,513 | 2.0h | `public-health-reporting-eval` 🔧 修正 B | **v2.5 ★** |
| 7 | 模型后训练 | **37,344** | 3.0h | 🔧 **修正 A：按算力三选一** | v2.8 |
| 8 | 持续进化 | 15,735 | 1.5h | `chapter8/trajectory-verifier` ✅ | **v3** |
| 9 | 多模态与实时交互 | 23,445 | 1.8h | `streaming-speech` 🔧 修正 C | v3+voice |
| 10 | 多 Agent 协作 | 30,261 | 2.2h | `parallel-web-research` ✅ | v3+panel |

> 🔧 = 该章默认实验与原方案要求存在事实冲突，已修正。
> 修正内容已直接写进对应的 `report.md`，学习时不会踩坑。
