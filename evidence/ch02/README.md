# 第 2 章：上下文工程

这一章回答一个工程问题：**Agent 每轮究竟应该看到什么，以及怎样在质量、长度和缓存成本之间取舍？** 章节内容涵盖 API 消息、Chat Template、KV/Prompt Cache、提示工程、Skills、状态栏和压缩。

## 从哪里读起

1. [一页学习笔记](./notes.md)：五个核心问题与当前判断，适合先建立全貌。
2. [完整阅读整理](./reading-notes.md)：按主题梳理原书内容，末尾有九道思考题的展开讨论。篇幅较长，需要查机制时再跳转。
3. [原书第 2 章](https://github.com/bojieli/ai-agent-book/blob/main/book/chapter2.md)：核对概念、实验条件和原始论述。

阅读整理基于原书；九题讨论与一页笔记含 AI 辅助提炼。笔记中转述的实验数字属于书稿或配套项目，**不是本学习仓库的独立复测数据**。

## 目前有哪些证据

| 内容 | 当前状态 | 入口 |
| --- | --- | --- |
| 阅读整理、配图 | 已归档 | [reading-notes.md](./reading-notes.md)、[image/](./image/) |
| 九道思考题讨论 | 已归档；待用实验复核 | [思考题](./reading-notes.md#思考题) |
| 一页总结、五个核心问题 | 已整理；阅读前理解未记录 | [notes.md](./notes.md) |
| 本人运行的实验代码和结果 | 尚未归档；`lab/results/summary.json` 不存在 | [lab/](./lab/) |
| 实验报告、文章、自测、答辩 | 尚为模板，未完成 | [report.md](./report.md)、[article.md](./article.md)、[quiz.md](./quiz.md)、[defense.md](./defense.md) |

因此，这里展示的是**学习中的理解和待验证判断**，还不能把第 2 章标记为“实验已复现”或“通过评估”。`python -m attest check 2 --all` 可以查看当前缺项。

## 下一步怎样形成可复现成果

先从[实验 2-3：KV Cache 错误模式](https://github.com/bojieli/ai-agent-book/tree/main/chapter2/kv-cache)或[上下文压缩策略对比](https://github.com/bojieli/ai-agent-book/tree/main/chapter2/context-compression)选一个。固定模型、任务与采样设置，保存基线及至少一个变量的原始输出；记录任务结果、token、缓存命中或信息保留情况，再写到 `lab/results/summary.json` 和 [实验报告](./report.md)。特别要保留一个失败或丢失早期细节的案例，否则很难判断压缩的代价。

若要归档本地演示脚本，先将凭据改为环境变量，并检查代码、日志和截图中没有密钥。随后再补自测和个人文章；有自己的实验数据后，文章里的数字才能指向可复现证据。
