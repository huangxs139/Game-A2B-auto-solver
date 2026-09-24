# A=B 自动求解器

[English](README.md) | [简体中文](README.zh-CN.md)

本仓库是 [**A=B**](#致谢) 游戏全部六章、47 道谜题的自动求解器。它会为每道谜题生成真正的 A=B 程序；随仓库提供的 47 个解答均已通过穷尽式本地验证和原版游戏验证。

## 为什么会有这个项目？

我这颗上了年纪的脑袋还够用么？看来是不太够。

四年过去了，我居然还没打通整个游戏？实在忍不了。

作为程序员我能怎么做？当然是做一个完全合法的~~作弊器~~**解题机**。

而且现在都 2026 年了，你懂的？我甚至不用自己写求解算法。

伟大的Codex。现在这是你的活儿了。

## 你想要什么？

### “我只想看答案”

没问题，懒是优点，不懒不会有本项目。

请直接查看 [`user_docs/ANSWERS.zh-CN.txt`](user_docs/ANSWERS.zh-CN.txt)。你可以轻松找到每一题的答案，均已验证过。（留心5-5可能需要跑15分钟，喝杯咖啡吧，别打断它）

### “我想亲自让 Solver 受一遍折磨”

很好。你可以清除随仓库提供的解答状态，让它重新求解全部 47 道谜题。先阅读[想自己运行？](#想自己运行)，再参阅完整指南 [`user_docs/GETTING_STARTED.zh-CN.md`](user_docs/GETTING_STARTED.zh-CN.md)。

### “我想知道它是怎样解题的”

与这份 README 不同，[`user_docs/SOLVING_ALGORITHMS.zh-CN.md`](user_docs/SOLVING_ALGORITHMS.zh-CN.md) 会认真讲解：从 A=B 背后的搜索问题开始，随着六个章节逐渐复杂，介绍 Solver 的工具箱，逐步分析代表性谜题，并将全部 47 道谜题对应到求解它们的策略。阅读它可以理解的不只是产生了哪些答案，还能学会那些~~精妙~~能用的算法。

### “我想阅读代码”

如果你准备修改、扩展、审计或借鉴实现，请阅读 [`user_docs/CODEBASE_GUIDE.zh-CN.md`](user_docs/CODEBASE_GUIDE.zh-CN.md)。它是开发者的代码指南：各项职责位于何处，一条命令如何流经 Manager、Solver 和 Executor，进程与数据如何通信，Rules 和持久化状态如何参与其中，以及测试套件如何组织。

### “我发现了 Bug”

请[提交 Issue](../../issues)。最好附上可复现的证据；通灵式调试暂不属于当前功能集。

### “我还有别的话想说”

欢迎通过[联系方式](#联系方式)联系我！

## 正经的说，本项目在做什么？

这不是一张硬编码答案表。

对于每道谜题，Solver 会检查给定的输入/输出对，识别其中的变换类型，再用分章节策略和模板构造候选 A=B 程序。每个候选都会依据同一份机器可读游戏规则执行，并且必须为全部给定用例生成预期输出。最终候选在保存前还必须由 Manager 独立验证。

简单地说，工作流如下：

1. 看看谜题。
2. 尝试一个 A=B 程序。
3. 让 Executor 说“不行”。
4. 换个更好的。
5. 重复，直到所有用例通过。
6. 保存程序，并在真实游戏中测试。

最终结果是原生 A=B 代码，而不是用 Python 冒充答案。

Solver 是专门为游戏中已知六章、47 道谜题这一封闭集合构建的。它是数据驱动、基于模板的合成器，而不是适用于任意未来 A=B 谜题的通用求解器。

## 想自己运行？

本项目以 Python 3.14 的 Linux 命令行应用形式开发和测试。Windows 用户可以通过 WSL2 或 Linux 虚拟机获得同类环境。

仓库中已提交的 `.solve` 文件是我本人运行和测试后的结果，因此 Manager 会正确跳过它们。若要从零开始独立求解，需要先手动删除这些文件，使每道题回到未求解状态。此后生成的新 `.solve` 文件将成为你的本地解，你可自行审核。

在本地检出目录中运行：

```bash
cd <path-to-your-cloned-repository-root>/   # 进入仓库根目录；目录名本身并不重要。
python -m pip install -r requirements.txt
rm -- test_output/*.solve                   # 删除已有接受状态，否则 Solver 会跳过这些谜题。

# 自动求解完整的六章、47 道谜题。
python a2bautosolver.py solve all

# 以定向 Debug 模式求解一道谜题，在 'solve' 后传入完整标识符。
# 可在 test_data/ 中查找标识符，其格式为 c{chapter_id}_{puzzle_id}_{puzzle_name}。
python a2bautosolver.py solve c1_1_atob     # 以不持久化的定向模式强制运行 c1_1_atob。
```

并发、Debug 行为、报告大小、测试、输入/输出格式和所有者审核流程详见 [`user_docs/GETTING_STARTED.zh-CN.md`](user_docs/GETTING_STARTED.zh-CN.md)。

## 它怎样求解 A=B？

简短答案：并不存在一个神奇的万能算法。

Solver 使用不断扩展的变换识别器和 A=B 程序模板工具箱。早期章节通常可用直接替换、映射、排序改写或计数模式处理；后续章节则需要标记符、类似有限状态转换器的多趟处理、辅助符号、有界搜索、借助中间表示完成的二进制算术，以及针对特定题目的构造。

候选解由题目数据生成，经过重复消除和行数限制筛选，在完整数据集上执行，并在持久化前接受独立验证。

更详细也更专业的算法解释请见 [`user_docs/SOLVING_ALGORITHMS.zh-CN.md`](user_docs/SOLVING_ALGORITHMS.zh-CN.md)。

## 有意使用 AI 构建

这个项目还隐藏着第二项实验：它同时检验了一套从需求到最终审核的 AI 辅助软件工程工作流。

- **我**拥有项目，作出需求和架构决策，审核每项 Feature，在真实 A=B 游戏中测试候选，并作出全部最终接受决定。
- **ChatGPT**协助讨论和完善需求、架构、开发计划及文档。
- **Codex**实现 Rules、Executor、Solver、Manager、测试与修复，执行第一层测试和审核，并向所有者报告审核证据。

重点不只是让 AI 交付一堆代码。项目从头到尾使用了书面需求、受保护规范、Feature 边界、测试、审核和由所有者控制的接受流程。

用于指导 Codex 的同一套需求、架构、路线图、Feature 规范、项目指令和机器可读 Rules 都包含在仓库内。如果你希望 Solver 采用不同的行为、支持自己的实验，或只是想看看这套流程能否经受新想法的考验，可以派生本项目并从这些文件继续，而不是从空白提示词开始。修改和再分发须遵守 [MIT License](LICENSE) 的适用范围。

## 项目状态

**已完成所含问题集。**

- 6 个章节
- 47 道题
- 47 份已提交的解答状态
- 47 个经真实游戏验证、由我确认过的解答
- 最终完整本地复验通过 126,626 个给定输入/输出用例
- 文档基线下 48 项自动化测试通过

谜题输入位于 [`test_data/`](test_data/)。便于复制的已接受程序位于 [`user_docs/ANSWERS.zh-CH.txt`](user_docs/ANSWERS.zh-CH.txt)；对应的 Solver 持久化状态和验证元数据仍位于 [`test_output/`](test_output/)。

本地验证和真实游戏接受有意保持分离：程序能够证明候选符合全部给定用例，但只有人可以确认解能否成功通过原版游戏。

## Issue

若遇到可复现 Bug、错误行为或文档问题，请[提交 Issue](../../issues)。

## 联系方式

- **个人邮箱：** [huangxs139@gmail.com](mailto:huangxs139@gmail.com)
- **工作邮箱：** [stevenwong.work.275@gmail.com](mailto:stevenwong.work.275@gmail.com)
- **商务联系：** [business-contact@megazero.cn](mailto:business-contact@megazero.cn)

## 致谢

**A=B** 是 Artless Games 制作的编程解谜游戏，唯一指令是 `A=B`，意为“将 A 替换为 B”。这个极简的语言必须解决从字母大写转换到二进制乘法的问题，而且最好使用尽可能少的行数。

原版游戏可在其[官方 Steam 商店页面](https://store.steampowered.com/app/1720850/AB/)找到。

这是一个独立实验项目。A=B 及其原始游戏材料归各自的创作者或权利人所有。

## 许可证

本项目原创的源代码和文档采用 [MIT License](LICENSE)。该许可证不授予对 A=B，或 Artless Games 及其他相关权利人拥有的游戏衍生材料的任何权利。
