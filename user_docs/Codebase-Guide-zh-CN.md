# A2B 自动求解器代码库指南

[English](Codebase-Guide.md) | 简体中文

本指南是当前代码实现的导航地图，面向希望追踪一次运行、诊断故障或在不越过项目所有权边界的前提下修改实现的 Python 开发者。

面向用户的用途和命令请先阅读 [`README.zh-CN.md`](../README.zh-CN.md)；环境配置、CLI 操作、状态管理和常见故障见 [`Getting-Started-zh-CN.md`](Getting-Started-zh-CN.md)；候选合成和分章节策略详见 [`Solving-Algorithms-zh-CN.md`](Solving-Algorithms-zh-CN.md)。本指南关注代码组织、运行时控制流、组件边界和安全扩展点。规范行为与架构约束仍以 [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) 和 [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) 为准。

## 从这里开始

最短有效阅读顺序：

1. [`a2bautosolver.py`](../a2bautosolver.py)——很小的可执行入口。
2. [`src/manager.py`](../src/manager.py)——CLI、发现、调度、验证、持久化、诊断和进程生命周期。
3. [`src/solver_framework.py`](../src/solver_framework.py)——谜题加载，以及求解算法共享的提议/反馈循环。
4. [`src/solver.py`](../src/solver.py)——覆盖六章的数据驱动候选合成器。
5. [`src/executor.py`](../src/executor.py)——依据 [`src/rules/a2b_rules.yaml`](../src/rules/a2b_rules.yaml) 解析并执行原生 A=B 程序。
6. [`tests/`](../tests/)——各边界和集成工作流的可执行示例。

核心依赖方向：

```text
CLI
  -> Manager
       -> SolverFramework -> 具体 SolvingAlgorithm
       -> 验证工作进程
  -> SolverFramework 和验证工作进程都使用 Executor
       -> Executor 加载 a2b_rules.yaml
```

关键区别是 Manager 和 Solver 都会**调用** Executor，但都不重新实现 A=B 执行。搜索期试运行帮助算法决定提交什么；只有 Manager 拥有的完整验证才允许持久化。

## 仓库地图

### 运行时与源码

- [`a2bautosolver.py`](../a2bautosolver.py) 导入并调用 `src.manager.main`。应从仓库根目录运行，使 `src` 导入自然解析。
- [`src/manager.py`](../src/manager.py) 是集成应用，拥有命令解析器、Manager、工作进程入口、验证、状态存储、报告和运行摘要。
- [`src/solver_framework.py`](../src/solver_framework.py) 包含不可变谜题/反馈模型、`PuzzleRepository`、`SolvingAlgorithm` 协议、`SolverSession` 和 `SolverFramework`。
- [`src/solver.py`](../src/solver.py) 包含 `CandidateSynthesisAlgorithm`、工厂，以及六章所用的候选生成器和推断辅助函数。
- [`src/executor.py`](../src/executor.py) 包含唯一的 A=B 解析和执行引擎：`Executor`、`ExecutionResult`、`ExecutionObservation` 和 `TerminationKind`。
- [`src/rules/a2b_rules.yaml`](../src/rules/a2b_rules.yaml) 是受保护的机器可读运行时 Rules；`DEFAULT_RULES_PATH` 指向这里。

项目没有安装式包布局、服务层、数据库或独立 Validator 子系统；它是一个从仓库根目录运行、以 `src.*` 导入模块的小型 CLI。

### 权威数据与持久化数据

主要数据位置为 [`test_data/`](../test_data/)、[`test_output/`](../test_output/)、[`reports/`](../reports/) 和 [`rules/`](../rules/) 下保留的自然语言来源。其结构、运行时处理和所有权边界统一见[文件与产物流](#文件与产物流)。

### 测试、工具、配置和项目文档

- [`tests/test_executor.py`](../tests/test_executor.py)、[`tests/test_solver.py`](../tests/test_solver.py)、[`tests/test_manager.py`](../tests/test_manager.py) 和 [`tests/test_review_candidates.py`](../tests/test_review_candidates.py) 构成 `unittest` 套件。
- [`tools/review_candidates.py`](../tools/review_candidates.py) 是面向所有者的候选审核 TUI，是改变 `.solve` 中所有者控制的 `status` 和可选 `reason` 的正常途径。
- [`tools/clean_test_data.py`](../tools/clean_test_data.py) 是破坏性维护工具，会删除 `test_data/` 中名称不匹配其模式的文件。它不属于正常求解/验证流程，仅在目录被增量污染时使用。
- [`requirements.txt`](../requirements.txt) 当前固定唯一运行时第三方依赖 PyYAML；并发与 IPC 全部使用 Python 标准库。
- [`AGENTS.md`](../AGENTS.md) 定义仓库级贡献和权限规则；[`docs/`](../docs/) 保存规范性需求、架构、路线图和已接受 Feature 规范。它们是治理和设计来源，不是运行时配置。
- [`user_docs/`](.) 保存用户/开发者文档，而非规范性运行时规范。

生成的 `__pycache__/` 目录只是解释器产物，没有架构作用。

## 组件与所有权边界

### Manager：编排和权威本地验证

具体 Manager 是 `src.manager.Manager`，公开入口为：

- `discover_puzzles()`：验证文件名、解析全部 `.a2b`、拒绝重复章节/题号，并按数字顺序返回；
- `solve_all(debug=False)`：加载持久化状态、选择合格谜题并执行持久化工作流；
- `solve_target(problem_id)`：以 Debug 强制运行一道谜题，不持久化替代候选；
- `request_stop()`：设置由调度循环检查的线程 `Event`。

`Manager._run()` 是编排核心：按章分组、在 `max_concurrency` 内启动章节 Solver、轮询 Solver/验证管道、把验证失败返回正确的活动会话、通过后推进章节并产生 `RunSummary`。

权威完整本地验证由 `src.manager.validate_candidate()` 实现。它检查原始候选行数，并用 Executor 对每个输入运行完全相同的序列化候选。`ValidationResult` 区分：

- `PASS`：全部用例正常结束、输出正确且满足行数限制；
- `FAIL`：候选无效、不终止、过长、超过 `min_lines` 或输出错误，但基础设施仍可信；
- `ERROR`：Rules、Executor 或验证基础设施失败，Manager 必须停止整个运行。

`PuzzleStateRepository` 严格加载 `.solve` 并原子持久化候选；`DiagnosticReporter` 生成唯一报告名，并用每次运行共享的 UUID 关联事件。这些辅助类放在 `manager.py`，因为状态和报告所有权属于 Manager 编排，而非 A=B 语义。

Manager 不得获得谜题特定搜索逻辑或指令行为。“应尝试哪个程序？”属于 Solver；“这条指令做什么？”属于 Executor，并可能还需经所有者批准修改 Rules。

### Solver：候选合成与搜索期反馈

Solver 有意拆分为：

- `src/solver_framework.py`：与具体策略无关的稳定生命周期；
- `src/solver.py`：封闭 47 题集合的当前策略。

`SolverFramework.start()` 解析谜题、构造 `SolverContext`、让 `AlgorithmFactory` 创建 `SolvingAlgorithm`、创建按章节绑定的 Executor，并返回有状态 `SolverSession`。`SolverFramework.solve()` 是启动会话并运行至一次提交的便捷形式。

`SolverSession.run_until_submission()` 反复：

1. 调用 `SolvingAlgorithm.propose(feedback)`；
2. 验证 `CandidateProposal` 结构；
3. 通过 `_trial_candidate()` 执行所请求用例；
4. 将 `CandidateFeedback` 返回同一算法；
5. 仅在算法令 `submit=True` 时停止。

会话在 Manager 完整验证失败后保留算法实例和反馈历史，因此同一搜索可以继续，而不必从头重启。

当前工厂 `create_solver_algorithm()` 为任意受支持章节创建一个 `CandidateSynthesisAlgorithm`。算法遍历 `_generate_candidates()` 的惰性流，先提出候选进行搜索期执行；通过后再以 `submit=True` 提出相同代码。流耗尽时抛出 `CandidateSynthesisError`，在 Manager 侧成为快速失败的 Solver 故障。

生成器按章分派：

- 第 1 章：`_basic_replacement_candidates()`；
- 第 2 章：`_return_keyword_candidates()`；
- 第 3 章：`_boundary_keyword_candidates()`；
- 第 4 章：`_once_keyword_candidates()`；
- 第 5 章：`_numeric_candidates()`；
- 第 6 章：`_no_keyword_candidates()`。

`_generate_candidates()` 去除序列化重复程序，并丢弃 `splitlines()` 数超过 `min_lines` 的程序。各章生成器从穷尽式 I/O 数据识别变换并产生原生 A=B 文本；`_infer_character_mapping()`、`_infer_binary_operation()`、`_matches_boolean()`、`_sorting_lines()`、`_fresh_symbols()` 等辅助函数支持这一过程。不存在“谜题 ID 到答案”的表，也没有动态算法注册表；策略解释见 [`Solving-Algorithms-zh-CN.md`](Solving-Algorithms-zh-CN.md)。

搜索期成功只是建议性的。当前具体提议默认使用全部用例，但只有后续 Manager 验证通过才可写入 `test_output/`。

### Executor：唯一 A=B 执行语义

`src.executor.Executor` 在 `__init__()` 中绑定章节和 Rules 文件：通过 `_load_rules()` 加载 YAML，以 `_load_limits()` 验证限制结构，检查章节可用操作，并将 Rules 操作 ID `replace_leftmost_occurrence` 映射到 `_apply_instruction()`。

`Executor.execute(input_text, code_snippet, debug=False)`：

1. 用 `_parse_program()` 解析原始行，执行序列化行长、注释、ASCII、等号、保留字符、关键字位置和章节可用性规则；
2. 检查初始工作字符串限制；
3. 从第一行扫描并执行第一条可执行指令；
4. 每次成功执行后重新从第一行扫描；
5. 将已消费 `(once)` 行纳入执行状态；
6. 完整扫描无可执行指令时正常结束，或因 `(return)` 立即结束；
7. 拒绝重复状态，并以 `max_steps` 限制增长型循环；
8. 每次成功指令后检查工作字符串限制。

结果由 `ExecutionResult` 和 `TerminationKind` 表示：`NORMAL`、`RETURN`、`NONTERMINATION`、`INVALID_PROGRAM` 或 `EXECUTOR_ERROR`；仅 `NORMAL` 和 `RETURN` 的 `terminated_normally` 为真。

`debug=True` 时，成功步骤还产生不可变 `ExecutionObservation`。`Executor.dump_observations()` 写入调用者拥有的流；Executor 自身不选择报告路径或写谜题状态。

不要在 Solver 启发式、Manager 验证器或工具中实现近似解释器。所有候选执行结论都必须经过该 Executor。

## 重要数据模型与协议

层间传递的主要对象都是小型冻结 dataclass：

- `Puzzle`：`problem_id`、`chapter`、`min_lines`、`inputs`、`expected_outputs`；
- `SolverContext`：`Puzzle` 加共享 `rules_path`；
- `CandidateProposal`：序列化 `code`、可选 `case_indices`、`submit`；`None` 表示全部用例；
- `TrialResult`：一项输入、预期输出、`ExecutionResult` 和比较标志；
- `CandidateFeedback`：提议、试运行和非用例失败原因；`passed` 要求无原因、全部输出正确且正常结束；
- `SolverRunResult`：已提交代码和累计搜索反馈；
- `PuzzleState`：解析后的持久状态及 `requires_solver` 资格规则；
- `ValidationResult`：Manager 验证结果、候选元数据、可选反馈/错误和 Debug 试运行；
- `RunSummary`：计数、中断/致命状态、观察到的最大章节并发和退出码策略。

`SolvingAlgorithm` 是只有一个方法的 typing `Protocol`：

```python
def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal: ...
```

这是替代或实验性 Solver 的主要扩展缝。`AlgorithmFactory` 接收 `SolverContext`；Manager 构造函数可接收工厂，集成测试也借此注入受控虚拟算法。

## 端到端执行流

### CLI 选择与发现

`a2bautosolver.py` 调用 `src.manager.main()`。`build_argument_parser()` 定义：

```text
solve all [--max-concurrency N] [--debug]
solve cX_Y_name [--max-concurrency N] [--debug]
```

`main()` 安装调用 `Manager.request_stop()` 的 SIGINT/SIGTERM 处理器。目标为 `all` 时调用 `solve_all(debug=args.debug)`；其他有效标识符调用 `solve_target()`。当前实现的定向执行始终为 Debug 且不持久化，无论是否显式传 `--debug`。

`solve all` 中，`discover_puzzles()` 扫描 `test_data/*.a2b`，验证 `c{chapter}_{number}_{name}` 形状和章节范围，通过 `PuzzleRepository` 解析并按数字 `(chapter, puzzle number)` 排序，不信任词法文件名顺序。

`PuzzleStateRepository.load()` 决定资格：状态缺失或无候选则求解；`re-solve` 则求解；`pending`、`accepted`、`rejected` 跳过。可选 `reason` 不控制资格。

### 章节工作进程与搜索循环

`Manager._run()` 按章分组合格 ID。有空闲并发槽时，`_start_chapter_worker()` 创建双工 `multiprocessing.Pipe` 和运行 `_solver_worker()` 的章节进程，Manager 发送 `_StartPuzzle(problem_id)`。

工作进程创建 `SolverFramework` 和新 `SolverSession`，调用 `run_until_submission()`。具体合成算法生成文本，框架用自己的章节 Executor 执行搜索试运行并反馈，直到可以提交。工作进程向 Manager 发送 `_CandidateSubmitted`；Debug 模式还携带完整搜索反馈历史。

### 独立完整验证

Manager 保持章节工作进程存活并调用 `_start_validation()`，为确切 `Puzzle` 和候选创建单向管道及短生命周期 `_validation_worker()` 进程，因此大型完整验证不会阻塞 Manager 轮询或其他章节。

持久化 `re-solve` 运行在启动验证前，通过 `_duplicate_replacement_result()` 拒绝与当前权威候选相同的提交，并把失败直接返回同一会话。

验证进程调用 `validate_candidate()`，创建自己的 Executor 并处理每个 I/O 对。普通失败反馈只保留失败试运行；Debug 还保留全部试运行及观察。

`FAIL` 时记录 `validation_fail` 并发 `_ValidationFailed(feedback)`，现有算法实例继续下个候选。`ERROR` 时记录诊断、设置致命摘要并清理全部进程，不在结果不可信后继续其他章节。

### 持久化与推进

`PASS` 时，常规 `solve all` 调用 `persist_valid_candidate()`：写临时文件、flush、`fsync`，再以 `os.replace()` 原子替换。状态包含候选、本地用例数/行数和 `status: pending`；旧 `re-solve` 原因随替换消失。

定向运行使用 `persist=False`，可调试已接受谜题而不改变 `.solve`。Manager 发送 `_ValidationPassed` 清除会话，再开始同章下个谜题；队列空后停止章节进程。最后重载状态、打印 `RunSummary`，明确区分本地完成与真实游戏接受。

## 进程、并发与 IPC 模型

`--max-concurrency 2` 的拓扑示例：

```text
主 Manager 进程
├── 第 1 章 Solver 进程 ── 临时配对 c1_* 验证进程
└── 第 2 章 Solver 进程 ── 临时配对 c2_* 验证进程
```

要点：

- `max_concurrency` 限制活跃**章节 Solver 进程**，不是 OS 进程总数；每章还可能临时有验证进程。
- 每章最多一个活跃谜题和一个验证；章内串行有序，章节间可并发。
- 默认 `max_concurrency=1`。
- Manager 默认使用 `multiprocessing.get_context()`，即 OS/默认启动方式；测试显式用 `spawn` 验证可 pickle 的边界。
- IPC 使用 `multiprocessing.Pipe`，绝不用文件轮询。Solver 管道双工；验证管道为单向结果通道。
- 私有消息 dataclass：`_StartPuzzle`、`_ValidationPassed`、`_ValidationFailed`、`_StopWorker`、`_CandidateSubmitted`、`_SolverFailure`、`_WorkerStopped`。
- `_ChapterRuntime` 和 `_ValidationRuntime` 只是 Manager 侧进程/连接账簿。
- 无消息推进时调度循环仅休眠 10 ms。
- 正常关闭先请求停止并短暂 join，不合作则 terminate；致命/中断清理会终止剩余验证进程，尽量防止孤儿。

`request_stop()` 的 `threading.Event` 只属于 Manager 进程；工作进程通过管道协调，必要时使用 `Process.terminate()`。

## 文件与产物流

### Rules

两个 `DEFAULT_RULES_PATH` 均指向 `src/rules/a2b_rules.yaml`。YAML 描述语法、章节关键字可用性、限制、控制流、`(once)`、循环检测和操作标识符；Executor 提供操作的 Python 实现。

Rules 是规范且受所有者保护。开发者可以检查和报告疑似不匹配，但不能把“修复”当作普通代码变更。`rules/` 下自然语言文件是参考材料，不是后备运行时 Rules。

### 谜题输入（`.a2b`）

JSON 包含标题、本地化描述、示例和穷尽式 `input`/`output`。`PuzzleRepository.resolve()` 只提取 `id`、`chapter`、`min_lines`、`input`、`output`，验证类型、文件名/ID 一致性及用例数，并返回不可变 tuple。自然语言字段不参与合成或验证；文件权威且只读，测试用临时目录创建自定义谜题。

### 谜题状态（`.solve`）

常规状态：

```json
{
  "problem_id": "c1_1_atob",
  "candidate": "a=b",
  "local_validation": {
    "passed": true,
    "case_count": 3279,
    "line_count": 1
  },
  "status": "accepted"
}
```

Manager 在通过后持久化 `candidate` 和 `local_validation`，并对新候选及验证通过的替代候选设置 `status: pending`。所有者控制之后的 `accepted`、`rejected`、`re-solve` 决定，以及仅允许用于后两者的可选 `reason`。`update_owner_decision()` 只原子修改这些所有者字段。

不要从测试通过、本地验证、已提交文件或退出码 0 推断接受；只有所有者操作能创建 `accepted`。

### 报告

`start_run()` 创建同一次运行各报告共享的 UUID。`write()` 使用：

```text
{problem_id}_{time_ns}_{short_uuid}.report.json
```

事件包括 `search_diagnostics`、`validation_pass`、`validation_fail`、`validation_error`、`solver_error`、`solver_process_error`、`interrupted`。Release 持久化失败和错误；Debug 还保存成功搜索与验证轨迹。报告可能包含候选、用例、终止、错误、耗时和逐指令观察，因数据穷尽可能很大。它们可丢弃，常规工作流不读取。

### 运行时配置

CLI 配置仅有：目标 `all` 或完整 ID；正整数活跃章节上限 `--max-concurrency`（默认 1）；为 `solve all` 提供丰富诊断的 `--debug`。默认路径是相对检出目录的模块常量；测试和嵌入代码可用构造函数覆盖。`Executor.max_steps` 默认 100,000，可在构造函数配置但不作为 CLI 标志。没有环境变量或应用配置加载器。

## 测试与验证代码

安装依赖后运行标准库 `unittest`：

```bash
python -m unittest discover -s tests -v
```

- `test_executor.py`：匹配/替换、从首行重启、空侧、关键字及章节限制、注释/空白、无效程序、长度限制、重复/增长型不终止和 Debug 等价性。
- `test_solver.py`：先用虚拟算法验证解析、提议/反馈、选定用例、错误传播和 Debug；六个章节测试再为 `test_data/` 每题合成候选并检查提交生命周期和 `min_lines`。
- `test_manager.py`：用临时目录和可 pickle 算法覆盖资格/持久化、失败后同一 Solver 重试、替换、章节并发、快速失败、优雅停止、定向不持久化、Debug 报告、损坏状态、验证结果、真实 Solver 和 CLI。
- `test_review_candidates.py`：审核 TUI、原子决定更新、可选原因、摘要/顺序、导航及机器字段保留。

章节合成测试是主要领域回归检查，通过真实框架和 Executor 运行真实语料。已提交 `.solve` 是有用产物，但不能替代实现变更后重跑测试。

## 调试指南

### 追踪单题端到端流程

```bash
python a2bautosolver.py solve c1_1_atob
```

它始终为 Debug 且不持久化。从 `manager.main()` 跟进 `solve_target()`、`_run()`，再检查 `reports/` 中由共享 `run_id` 关联的 `search_diagnostics` 与 `validation_pass`/`validation_fail`。

变换错误看搜索反馈及 `src/solver.py` 对应生成器；指令结果/终止异常可缩减为直接 `Executor.execute()` 并看 observations；资格/持久化异常先看 `PuzzleStateRepository.load()` 和 `.solve` 状态。

### 有用断点与插桩点

- `Manager._run()`：调度、消息、分类、推进；
- `_solver_worker()` / `_validation_worker()`：进程边界和 pickle；
- `validate_candidate()`：行数和权威逐用例决定；
- `SolverSession.run_until_submission()`：提议/反馈与会话复用；
- `_trial_candidate()`：选定用例和基础设施升级；
- `propose()` / `_generate_candidates()`：顺序、耗尽、去重、`min_lines`；
- `_parse_program()`：语法和行长；
- `execute()` / `_apply_instruction()`：控制流、状态、关键字、不终止；
- `DiagnosticReporter.write()`、`_record_search()`、`_record_validation()`：报告内容和体量。

Debug 观察必须保持观察性：可以收集更多数据和额外检查，但不得改变候选选择或执行语义。

## 安全扩展点

### 添加或替换求解策略

实现 `SolvingAlgorithm` 和 `AlgorithmFactory`。实验可向 `Manager(algorithm_factory=...)` 注入，或直接调用 `SolverFramework.solve()`；永久变更则更新 `create_solver_algorithm()` 和/或 `_generate_candidates()` 章节分派，同时保持序列化候选与 Executor 反馈边界。

新生成器应惰性、由 `Puzzle` 数据推导而非复制外部解、遵守 `min_lines` 并安全使用新辅助符号。新增可复用推断辅助函数时加入聚焦回归，再运行受影响章节完整合成测试。

### 改变搜索期用例选择

将 `CandidateProposal.case_indices` 设为唯一、非空、有效的零基索引 tuple；框架会验证。这样可降低搜索成本，但提交候选仍接受 Manager 完整验证，不得削弱或绕过。

### 添加诊断

在产生层扩展不可变观察/结果数据，并由 Manager 序列化。每个事件只有一个持久化所有者，避免工作进程和 Manager 重复报告同一信息。

### 改变持久化或审核

机器候选状态属于 `PuzzleStateRepository`；所有者决定属于 `tools/review_candidates.py`。保持原子写入与严格加载。结构变更影响已提交状态，可能越过规范边界，应先确认权限。

### 改变 A=B 执行行为

这是最高风险扩展。先比较机器 Rules、自然语言来源、Executor 测试和真实游戏行为。语义修正可能需所有者先批准受保护 Rules 变更。全部语义留在 Executor，并添加聚焦规则/限制/控制流测试。任何新 Python 第三方依赖都需所有者明确批准。

## 未来贡献者必须保持的不变量

前文已定义常规职责边界，以下是不太直观但值得集中列出的护栏：

1. `test_data/*.a2b` 是不可变权威输入。
2. `src/rules/a2b_rules.yaml` 是规范性受保护内容，不能当普通清理编辑。
3. 自动代码可在 Manager 验证后创建 `pending`，但不得推断或创建所有者的 `accepted`、`rejected`、`re-solve`。
4. 定向 Debug 不得覆盖权威 `.solve`。
5. 报告仅用于诊断，其去留不得改变谜题行为或状态。
6. 候选有效性针对确切序列化程序：原始行数/行长、每个中间字符串长度、终止和全部穷尽式 I/O 都重要。
7. 候选失败是可恢复反馈；基础设施失败快速失败并使继续结果无效。
8. 本地测试或验证通过绝不能替代所有者真实游戏接受。

若变更会改变需求、受保护 Rules、架构、状态所有权或接受语义，请停止并取得所有者决定。只有在这些边界不变时，普通内部重构才安全。
