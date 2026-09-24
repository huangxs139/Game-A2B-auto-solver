# 入门指南

[English](Getting-Started.md) | 简体中文

本指南从 README 结束的位置开始：你已有本地检出目录，并希望运行工具。以下命令均假定 Shell 位于包含 `a2bautosolver.py` 的仓库根目录。

## 1. 准备环境

已知经过测试的环境是 Linux，尤其是使用 Miniconda3 的 WSL2，运行 Python 3.14。项目不声明最低 Python 版本；其他版本可能可用，但未经完整运行验证。若要匹配文档环境，请使用 Python 3.14。项目仅有一个第三方依赖，在 `requirements.txt` 中固定为 PyYAML 6.0.3。本地求解和验证不需要 GPU、外部服务、API 密钥或安装 A=B 游戏。

检查 `python` 所选解释器：

```bash
python --version
```

建议使用隔离环境。例如使用标准库 `venv`：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

若使用 Conda，请先激活 Python 3.14 环境，再运行相同的 `python -m pip install -r requirements.txt`。

仓库直接从检出目录运行，不包含软件包安装器或控制台脚本入口。确认 CLI 可正常导入并查看已实现选项：

```bash
python a2bautosolver.py --help
python a2bautosolver.py solve --help
```

安装依赖后，可运行完整自动化测试套件来验证检出目录。它比轻量安装检查覆盖更广，耗时也可能更长：

```bash
python -m unittest discover -s tests -v
```

## 2. 首次调用

运行常规工作流：

```bash
python a2bautosolver.py solve all
```

仓库为每道谜题附带一个 `.solve` 文件，当前全部为 `status: accepted`。因此，未修改的检出目录会发现 47 道谜题，报告没有谜题需要 Solver 工作，跳过全部 47 道并成功退出。这是预期行为：它确认 Manager 能发现输入并读取持久化状态，但不会重新运行 Solver。

最终输出会区分本地工作流完成与原版游戏接受。进程退出和本地验证都不会创建或暗示真实游戏接受。

## 3. 真正求解谜题

### 求解一道谜题而不改变已保存状态

使用完整谜题标识符，即 `.a2b` 文件名去掉扩展名：

```bash
python a2bautosolver.py solve c1_1_atob
```

标识符区分大小写。需要时列出可用名称：

```bash
find test_data -maxdepth 1 -name '*.a2b' -printf '%f\n' | sort
```

定向运行有两个重要性质：

- 即使已保存状态通常会导致跳过，它也会强制运行指定谜题。
- 它始终启用详细 Debug 收集，且绝不会写入或替换该谜题的 `.solve` 文件。

因此，在现有检出目录中练习 Solver 或调查谜题时，定向执行最安全。它仍会在报告 `Validation PASS` 前执行完整数据集验证，并在 `reports/` 下写入 Debug 产物。

`--max-concurrency` 对单一目标没有实际影响，因为只有一个章节活跃。也无需为目标显式提供 `--debug`，因为定向执行已经启用它。

### 重新运行完整集合

常规 `solve all` 仅在 `.solve` 不存在、没有候选或 `status: re-solve` 时调度谜题。已提交状态表达上游项目所有者的决定，因此未修改的检出目录会跳过整个集合。删除它们即可让全部谜题以未求解状态开始你自己的运行；此后生成的替代状态属于你的本地审核工作流。

若希望方便地保留一份上游结果，可先备份：

```bash
cp -a test_output /tmp/a2b-test-output-accepted
rm -- test_output/*.solve
python a2bautosolver.py solve all
```

删除仅影响工作副本中的受跟踪文件。若要丢弃自己生成的状态并恢复上游版本：

```bash
git restore test_output
```

完整运行期间，每章内部的谜题保持有序。Manager 启动章节 Solver 进程、接收候选，通过 Executor 针对每个给定输入/输出用例独立验证提交的程序，并将成功结果以 `status: pending` 写入 `test_output/<problem_id>.solve`。

### 使用章节并发

默认同时只有一个活跃章节 Solver。可增加：

```bash
python a2bautosolver.py solve all --max-concurrency 3
```

该值必须为正整数，限制的是同时活跃的章节 Solver，而非操作系统进程总数；验证还会在独立工作进程中运行。最多六章能提供有效的章节级并行。更高并发可缩短耗时，但会增加同时使用的 CPU 和内存。

### 启用完整运行诊断

诊断式 `solve all`：

```bash
python a2bautosolver.py solve all --debug
```

Debug 模式记录搜索反馈、每次带 Debug 的 Executor 试运行和完整验证观察。单个谜题可能有数千个用例，因此 JSON 报告可能非常大。调查一道谜题时优先使用定向运行。

## 4. 理解相关文件

CLI 没有用户配置文件或环境变量配置；运行时位置由代码相对仓库固定：

| 路径 | 作用 | 运行时处理 |
| --- | --- | --- |
| `test_data/*.a2b` | 47 份权威谜题定义和穷尽式输入/输出用例 | 只读；不要为影响结果而编辑 |
| `src/rules/a2b_rules.yaml` | 机器可读的 A=B 语法、章节能力、语义和限制 | 只读的规范性运行时输入 |
| `test_output/*.solve` | 每道谜题的候选程序、本地验证事实和所有者决定 | 常规运行读取；完整本地通过后原子写入 |
| `reports/*.report.json` | 原始搜索、验证、错误或中断诊断 | 非权威诊断产物；不决定资格 |

谜题名遵循 `c<chapter>_<number>_<short-name>`，如 `c1_1_atob`。每个 `.a2b` 都是 JSON；运行时相关字段包括 `id`、`chapter`、`min_lines`、`input` 和 `output`。

生成的 `.solve` 也是 JSON，关键字段包括：

- `candidate`：原生序列化 A=B 程序；
- `local_validation`：是否在本地通过，以及用例数和行数；
- `status`：工作流状态，由 Manager 初始化为 `pending`，之后仅由所有者改为 `accepted`、`rejected` 或 `re-solve`；
- `reason`：`rejected` 或 `re-solve` 可选的所有者元数据。

四种有效状态：

| 状态 | 含义 | `solve all` 会调度？ |
| --- | --- | --- |
| `pending` | 本地有效候选等待所有者手工审核 | 否 |
| `accepted` | 所有者已在真实 A=B 游戏中接受 | 否 |
| `rejected` | 所有者拒绝，且未请求自动重求 | 否 |
| `re-solve` | 所有者明确请求替代候选 | 是 |

若替代候选通过完整本地验证，Manager 会替换旧候选，将状态改为 `pending` 并移除旧 `reason`。在此之前，旧候选和决定仍保留在状态文件中。与当前 `re-solve` 候选完全相同的替代项会被 Manager 拒绝，并作为反馈返回活跃 Solver。

## 5. 审核候选并记录真实游戏结果

启动逐行交互审核工具：

```bash
python tools/review_candidates.py
```

默认读取仓库的 `test_output/`。若要审核单独复制的状态，使用其唯一选项：

```bash
python tools/review_candidates.py --state-directory /path/to/copied-states
```

工具直接显示状态摘要和谜题坐标提示。按 Enter 选择所示默认值，输入如 `1-5` 的坐标（也支持下划线），或输入 `q` 退出。默认值是第一个 pending 候选；没有 pending 时则是第一个 accepted 候选。因此可直接查看已提交检出目录中的全部 47 个 accepted 程序。

选中谜题后，工具会显示当前状态、已有原因和可复制的原生 A=B 程序。在结果提示处按 Enter 保持当前状态；在原版游戏中测试后，也可记录：

- `accepted`——真实游戏测试成功；
- `rejected`——失败并应继续跳过；
- `re-solve`——失败并应在下次 `solve all` 时重新求解。

对于 `rejected` 和 `re-solve`，工具可选记录原因。它仅更新所有者控制的决定字段并原子写入，然后返回摘要和坐标提示。

不要仅因本地验证通过就将候选标为 `accepted`。本地验证只表示该确切候选遵守已实现限制，并通过本项目 Executor 为全部给定用例产生预期输出。只有在原版游戏中成功手工输入才足以判定 `accepted`。

## 6. 阅读进度、结果和报告

Release 输出有意保持简短。典型消息会宣布候选提交和 `Validation PASS`/`Validation FAIL`，随后给出摘要：

- 发现、合格和跳过的谜题数；
- 本次运行中本地验证通过的候选数；
- 返回 Solver 的完整验证失败数；
- `solve all` 中持久化的 pending、accepted 和 rejected 数；
- 运行是完成、中断还是失败。

验证失败不一定致命：失败用例反馈会返回仍在运行的 Solver，使其尝试其他候选。Rules 格式错误、谜题/状态 JSON 损坏、Executor 错误或未处理的 Solver 失败等基础设施问题会快速失败，因为后续结果将不再可信。

报告文件名包含谜题标识符、类似时间戳的纳秒值和短随机后缀。同一次 Manager 调用的报告在 JSON 内共享 `run_id`。根据事件和模式，`event` 可表示搜索诊断、验证通过/失败/错误、Solver/进程错误或中断。

成功的非 Debug 运行不会写常规通过报告。失败和错误会在可用时记录；Debug 运行还会持久化详细的成功搜索与验证数据。报告仅用于诊断：删除或保留报告不会改变 Manager 调度哪些谜题。

## 7. 安全停止与继续

按 `Ctrl-C` 请求优雅停止；CLI 也以同样方式处理 `SIGTERM`。Manager 会在下一个安全循环点停止活跃工作，清理 Solver 和验证进程，尽可能为活跃谜题写入中断报告，打印最终摘要，并以状态 130 退出。

停止前已完成完整验证的候选会因 `.solve` 原子写入而安全保留。再次运行同一命令即可继续总体工作流；`solve all` 会跳过已持久化候选，从仍合格的谜题重新开始。

Solver 不检查点保存内部搜索。中断的谜题会从头开始搜索；定向运行有意不写候选状态，因此无法从持久化状态恢复。

## 8. 常见运行问题

### `ModuleNotFoundError: No module named 'yaml'`

当前解释器没有固定依赖。激活预期环境并运行：

```bash
python -m pip install -r requirements.txt
```

使用 `python -m pip` 可确保安装目标与启动求解器的解释器一致。

### `solve all` 表示没有谜题需要工作

这是第 2 节描述的预期首次调用行为。可用定向命令进行不持久化重跑，按“重新运行完整集合”开始干净的本地运行，或在审核后将选定本地候选标为 `re-solve`。

### 目标被拒绝或找不到

请传入 `test_data/` 中区分大小写的确切文件名主干，而非 `1-1` 这样的坐标、路径或带 `.a2b` 的文件名。例如第 3 章第 1 题是含大写 `R` 的 `c3_1_Remove`。

### 运行在读取 `.solve` 时失败

常规执行会严格结构检查持久化状态，并在 JSON 损坏、标识符不匹配、状态/原因组合无效、本地验证数据缺失或元数据类型/值无效时停止。加载状态不会重新执行候选，也不会将保存的用例数和行数与谜题比较。请从版本控制或可靠备份恢复格式错误的文件；正常状态变更请使用审核工具，而非手工编辑 JSON。

### Debug 报告占用大量磁盘

Debug 会捕获全部试运行用例的逐步执行观察。尽可能使用定向执行，并归档或删除 `reports/` 下不再需要的文件；它们不是权威状态。当前仓库不会在 Git 中忽略 `reports/`，提交前请检查 `git status`。

### Solver 看起来卡住

项目没有性能期限，有效搜索可能长时间运行。用定向运行重试同一谜题以收集诊断；必要时优雅中断，未解决谜题会重新开始而非恢复内部搜索。

### 退出状态含义

- `0`：请求的本地工作流正常结束，即使没有谜题需要工作；
- `1`：发生致命 Manager/运行时错误；
- `130`：运行被优雅中断；
- `2`：命令行解析拒绝调用。

这些状态都不表示原版游戏接受了候选。
