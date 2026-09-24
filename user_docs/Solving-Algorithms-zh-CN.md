# A2B 自动求解器：已实现的求解算法

[English](Solving-Algorithms.md) | 简体中文

本文解释 `src/solver.py` 中实际合成 A=B 程序的算法：Solver 如何从谜题数据识别可能的变换、把假设编译为原生 A=B 指令、枚举哪些备选、Executor 失败怎样控制下一次试运行，以及生成的改写系统为何有效。

Solver 是面向所含六章谜题集合、确定性的模板式程序合成器，不是神经模型、统计学习器或对所有合法 A=B 程序的无限制枚举。它结合两类计算：

1. Python 识别器分析完整 I/O 表，识别字符映射、长度取模、回文判断、二进制加法等变换族。
2. A=B 模板把变换族编译为一个或多个具体程序；真正的 Executor 执行每个程序，判定其操作行为是否匹配全部用例。

识别样例“做什么”与合成 A=B“怎样做到”之间的区别，是实现核心。

## 1. 实际搜索循环

共同生命周期由 `CandidateSynthesisAlgorithm` 和 `SolverFramework` 实现。

### 1.1 惰性候选、有序生成

`CandidateSynthesisAlgorithm` 持有 `_generate_candidates(puzzle)` 返回的迭代器，并恰好分派一个章节生成器：

```text
第 1 章 -> _basic_replacement_candidates
第 2 章 -> _return_keyword_candidates
第 3 章 -> _boundary_keyword_candidates
第 4 章 -> _once_keyword_candidates
第 5 章 -> _numeric_candidates
第 6 章 -> _no_keyword_candidates
```

候选解不会被集中收集或全局排序；Python `yield` 顺序就是优先级。最先产生者最先试，找到通过程序后不再继续。

候选解进入 Executor 前，`_generate_candidates()` 删除重复序列化文本，并拒绝 `len(code.splitlines()) > puzzle.min_lines` 的程序。剩余对象都是完整可执行 A=B 候选解，不是待补全 AST 或片段。

### 1.2 试运行始终使用完整数据集

框架协议允许策略请求选定用例索引，但已实现章节算法从不这样做；每次提议都在全部 I/O 对上运行。

`_trial_candidate()` 为每个用例记录输入、预期输出、Executor 结果和精确匹配标志。只有全部执行正常结束或 `(return)`、全部输出匹配且无框架失败原因，提议才通过。程序格式错误、检测到循环、工作字符串过长和输出错误属于普通候选解失败；Executor 基础设施错误则中止搜索。

### 1.3 “失败后调整”的真实含义

当前 Solver **不会**分析失败用例、计算错误分数、编辑失败程序或从轨迹学习新改写规则；具体算法只读取 `feedback.passed`：

```python
for code in ordered_candidate_generator(puzzle):
    feedback = execute_on_every_case(code)
    if feedback.passed:
        execute_on_every_case(code, submit=True)
        return code
raise CandidateSynthesisError
```

失败只让惰性生成器前进到下一候选解。所谓“调整”来自生成器预先组织的参数循环，例如尝试下一种字母表次序或增加标记数，而非分析失败详情。

这是带语义反馈的搜索：生成器给出有计划的假设序列，Executor 充当接受/拒绝判定器；它不是反馈引导的程序修复。若 Manager 后续独立验证拒绝提交，仍保留同一 `SolverSession` 和迭代器，`propose()` 继续下一候选解而不回到第一个。

### 1.4 识别测试不是 Executor 试运行

许多生成器循环先用 Python 验证语义假设：

```python
if all(expected == hypothesized_transform(value)
       for value, expected in puzzle_cases):
    yield compile_hypothesis_to_a2b_program(...)
```

失败假设只是 Python 比较，不成为 A=B 试运行。另一些循环有意产生尚未确定的备选：第 1 章为每种字母次序生成改写系统；第 4 章 `cut2` 生成递增标记数，由 Executor 解决操作性选择。

## 2. 模板如何实现逻辑

仅识别 `output == reverse(input)` 并不等于解出 A=B；关系必须编译为遵循 A=B 控制流的有序改写规则：自顶向下扫描，执行第一条可用指令，从首行重启，直到无行可用或执行 `(return)`。

规则次序就是控制流。过早清理可能破坏后续状态；空左侧规则若无 `(once)` 防护可能循环；局部替换可能重新启用自身。每个模板都是小型字符串改写机，常带显式中间表示。

反复出现的四类技术：

- **规范化：**排序符号或映射到共同标记，将全局性质变为局部连续模式。
- **抵消：**删除相反 token，使残留类型或长度代表比较结果。
- **新符号状态：**用 I/O 中没有的字符表示游标、阶段、边界、计数器、进位/借位或编码。
- **搬移：**用右侧 `(start)`/`(end)` 把局部改写变成扫描，用 `(once)` 精确初始化一次。

Rules 定义指令语义和章节可用性，不包含 Solver 模板或启发式。Solver 选候选解，Executor 对序列化程序应用 Rules。

## 3. 第 1 章——普通改写系统

`_basic_replacement_candidates()` 固定顺序：位置字符映射；折叠全部相邻连续段；对每个非空符号子集删除重复段；枚举字母表全排列的排序系统；枚举有序符号对的双符号频率比较。

### 3.1 直接映射

`_infer_character_mapping()` 要求输入/输出等长，并从全部对应位置建立一致 `source -> target` 函数；同一源对应两个目标则拒绝。只输出发生变化的映射：

```text
a=A
b=B
c=C
```

它解决 `c1_1_atob`、`c1_2_uppercase`。仍需 Executor，因为顺序替换会在目标同时也是源时相互作用。

### 3.2 连续段算法

下一个无条件候选解为每个符号加入 `xx=x`，反复应用把每个最长连续段折叠为一个字符，解决 `c1_3_singleton`。

随后 `combinations(symbols, count)` 按子集大小递增枚举；每个选中符号 `x` 使用：

```text
xxx=xx
xx=
```

第一条把长段缩至两个，第二条删除成对字符，单字符保留。仅选择 `a` 可解 `c1_4_singleton2`。

### 3.3 枚举全序进行排序

对输入字母表每个排列，为每个逆序对产生交换：

```python
for ordering in permutations(symbols):
    for left in ordering:
        for right in ordering:
            if rank[left] > rank[right]:
                emit(f"{left}{right}={right}{left}")
```

每次改写都降低该次序下的逆序数，最终终止于排序字符串。对于 `a < b < c`：

```text
ba=ab
ca=ac
cb=bc
```

Python 不推断目标次序；Executor 拒绝错误排列并接受匹配全部输出者。`c1_5_sort` 实际先试全部符号折叠、三个符合行数预算的单符号删除器，丢弃超预算的大子集，再以第五个 Executor 候选解 `a < b < c` 通过。

### 3.4 以抵消比较计数

每个有序符号对产生异类抵消和同类折叠：

```text
ab=
ba=
aa=a
bb=b
```

删除会让原本分开的异类靠拢并继续抵消，最终只剩多数符号，再折叠为一个。`c1_6_compare` 是早期通用/排序候选解失败后的第七个实际候选解；没有编辑失败程序，只是生成器到达下一构造。

## 4. 第 2 章——谓词与立即返回

`_return_keyword_candidates()` 先规范化输入直到出现决定性模式，再用 `(return)`。发现顺序：常量输出；对每个 `(true_output, false_output)` 有序对尝试符号计数阈值、确切长度、全计数奇数（枚举字母次序）、恰有一个单字符连续段、严格三符号频率次序；随后长度模数；最后三符号的 `most`/`least` 次序。大多数循环因 `_matches_boolean()` 要求假设正确标注全部用例而不产生候选解。

### 4.1 常量、阈值与确切长度

常量表编译为 `=(return)<output>`。对于 `value.count(x) >= n`，删除其他符号，`n` 个 `x` 返回真，空左侧兜底返回假；从 1 到最大输入长度检查，解决 `c2_2_aaa`。

确切长度 `n` 将每个符号映射为一个标记；`n+1` 个标记先返回假，`n` 个返回真，更短者落入假兜底。优先级编码上界保护，解决 `c2_3_exactly`。

### 4.2 奇数计数

识别器判断每个符号计数为零或奇数。对每种字母次序，候选解将同类排在一起，用 `xxx=x` 保留奇偶性；任何 `xx` 返回假，否则返回真，解决 `c2_5_odd`。

### 4.3 恰有一个单字符连续段

关注最长相邻连续段，而非全局频率。每个 `x`：

```text
xxx=xx       # 缩短长段
xx=R         # 编码非单字符段
x=S          # 编码单字符段
```

擦除新 `R`，`SS` 返回假，一个 `S` 返回真，无 `S` 返回假，解决 `c2_6_only`。

### 4.4 严格频率次序

每个 `(lower, middle, upper)` 排列由 Python 检查：

```text
count(upper) > count(middle) > count(lower)
```

候选解按此次序排序，抵消把 `middle` 相对 `lower` 的盈余暴露为新标记；标记后仍有 `upper` 证明第二个严格不等式。只有该配置返回真，解决 `c2_7_ascend`。

### 4.5 对推断除数取长度模

依次尝试除数 `2..max_length`；只有每个余数对应唯一输出且所有余数都出现才可用。程序把所有符号映射为一个标记，反复将 `d+1` 个替换为一个，再按 `d, d-1, ..., 1` 映射残余长度。长度 `d` 表示余数零；较长模式先行防止被短模式抢走。解决 `c2_4_remainder`。

### 4.6 Most 与 least

`most` 要求输出是最高频符号。程序排序连续段，在长度 `max_length // 2 + 1` 时返回；若没有段初始达到阈值，空左侧规则为每个符号各加一个，相等增量保持原领先者并让它先跨阈值，解决给定表中的 `c2_8_most`。

`least` 使用最小 `value.count`。每个有序候选解排序三个符号，再用紧凑的特化残余模式决策表；Executor 选择能解 `c2_9_least` 的次序，它不是通用 arg-min 编译器。

这些策略依次解决第 2 章 `hello`、`aaa`、`exactly`、`remainder`、`odd`、`only`、`ascend`、`most`、`least`。

## 5. 第 3 章——边界算法

搜索顺序：每个符号的边界剥除和旋转至首次出现；每个源/目标对的边界段替换；每个首/尾符号对的边界段互换；每个输出标签次序的同首尾/回文谓词；每个三符号角色次序的最高频连续段输出。各族先对完整表检查，族内排列由 Executor 决定。

### 5.1 剥除与旋转

若输出等于 `value.strip(symbol)`，程序删除两端该符号并通过重启删除整段，解决 `c3_1_Remove`。

旋转要求目标出现在每个输入中，输出为旋转至其首次出现。把其他开头符号移到 `(end)`，目标到首位时无规则可用。以 `a` 为目标解决 `c3_2_spin`。

### 5.2 替换或交换边界段

`_replace_boundary_runs()` 模拟将开头/结尾最长 `source` 段换为 `target`；匹配假设编译为使用两个新标记搬移并恢复两端的四行机器，解决 `c3_3_atob2`。

`_swap_boundary_runs()` 识别开头一种符号段和结尾另一种符号段的交换。候选解用标记把尾符号移到开头，再把匹配的首符号移到结尾并擦除标记，解决 `c3_4_swap`。

### 5.3 比较两端

对每种可能首符号，候选解删除它并在末尾放对应标记；高优先规则识别末符号与标记相符并返回真，否则兜底假，解决 `c3_5_match`。

### 5.4 从外向内判断回文

边界规则把首符号编码成开标记、该符号和末尾闭标记；`x OPEN x CLOSE=` 删除相等的首尾，重复处理内部。不匹配标记返回假，完全抵消落入真，解决 `c3_7_palindrome`。

### 5.5 保留胜者重复数

`c3_6_most2` 要求输出为最高频符号重复其计数。每种三符号角色排列产生十行特化机器，结合抵消、交换、边界搬移和扩展；与第 2 章 `most` 不同，它必须去掉败者并保留或重建胜者完整段。Executor 决定可行角色。

## 6. 第 4 章——已初始化转换器

`(once)` 可播种有限状态。多数程序初始化标记、让其穿过数据、在边界输出变换数据，再擦除标记。

源码检查顺序：前置常量；从左右删除 `n` 次符号；删除定长前缀；交换首尾；反转；游标逐点映射；保留 `value[1::2]`；复制输入；两个条件映射编译器；选中心；有界固定位置删除；追加前缀副本；删除中心；按一基位置扩展；交错等长两半。多数分支先验证变换等式，源码靠前不一定产生 Executor 试运行。

### 6.1 前缀与出现次数删除

常量前缀为一行 `(once)=(start)<prefix>`，解决 `c4_1_hello2`。删除前 `n` 个 `x` 使用 `n` 行独立 `(once)x=`，解决 `c4_2_remove2`。从右删除则追加 `n` 个标记，让标记越过非目标向左移动，删除 `x MARKER` 并清理，逆转默认最左偏好，解决 `c4_4_remove3`。

### 6.2 前缀切割、首尾交换和反转

切前缀在开头播种 `n` 个标记，`MARKER x=` 每次消费一个标记和字符，解决 `c4_3_cut`。

首尾交换识别 `value[-1] + value[1:-1] + value[0]`。扫描标记把首符号送到末尾，边界标记再把旧末符号送到开头，解决实际执行首尾交换而非全反转的 `c4_5_reverse`。

全反转播种 `max_length` 个标记；`MARKER x=(start)x` 从左到右消费原字符并把结果前置，多余标记擦除。这个按数据集尺寸构造的程序解决 `c4_6_reverse2`。

### 6.3 游标映射与交替选择

逐点映射在开头插入游标，反复执行 `CURSOR source=target CURSOR`；生成目标留在游标后，不会级联进入后续映射。清理后解决 `c4_9_atob3`。

`value[1::2]` 用两个初始标记编码交替阶段：一次丢弃字符，下一次保留并在其后恢复标记对；清理留下索引 1、3、5……，解决 `c4_10_odd2`。

### 6.4 整串复制

末尾追加边界标记。原符号到达边界时留下边界、追加两个副本并创建扫描标记；扫描标记穿过剩余原输入，把副本送到末尾。清理留下两份完整字符串，解决 `c4_11_clone2`。

### 6.5 条件映射：一个假设、两个编译器

`_infer_conditional_mapping()` 枚举 `(condition, source, present_target, absent_target)`，直到全部用例满足：

```python
expected == value.replace(
    source,
    present_target if condition in value else absent_target,
)
```

第一个编译器标记一次 condition，向开头搬移状态，恢复 condition，并向右扫描映射 source；无 condition 时普通末规则产生 absent 目标。第二个构造局部 source/标记/condition 排列，穿过中间符号，在证明 condition 存在后映射 source，再执行缺席兜底。`c4_12_tob` 中第一个失败、第二个通过；第二个不是从失败中学习，而是下一个预定 `yield`。

### 6.6 以模旋转选择中心

对奇数长度、输出为中心的输入，`_find_rotation_count()` 从 `r=0` 向上搜索，使每个已观察长度满足：

```text
r mod length = floor(length / 2)
```

程序播种 `r` 个标记，每个把一个首符号移到末尾，使所有支持长度的中心到首位，再由 start-return 选择。解决 `c4_13_center`。整数搜索无界且无通用不一致检查，但对所含长度集合终止。

### 6.7 有界搜索删除固定位置

Python 先确认删除某个固定零基位置产生全部输出；位置只启用策略，并不直接编译：

```python
for ordering in permutations(symbols):
    low, middle, high = ordering
    for marker_count in range(1, 100):
        yield six_line_marker_machine(low, middle, high, marker_count)
```

机器变换标记段和符号角色，直到擦除一个位置；Executor 找到有效参数。`c4_7_cut2` 第一种次序正确，计数 1–11 失败，12 通过；100 以上永不尝试。

### 6.8 前缀复制

每个前缀长度检查 `expected == input + input[:n]`。前向标记消费前缀，将每符号两个副本和恢复状态追加；恢复标记把一个副本送回开头，另一个留在末尾，解决 `c4_8_clone`。

### 6.9 删除中心

要求奇数长度并精确删除 `len(input)//2`。候选解播种计数、转移和阶段标记；规则增长计数块、搬移重复符号、在开头重置阶段，并擦除遍历阶段相遇位置的符号，解决 `c4_14_center2`。对称外部最终保留一份数据，唯一中心失去最后副本，再清理脚手架。

### 6.10 位置扩展

识别：

```python
expected == "".join(character * position
                    for position, character in enumerate(value, 1))
```

且要求三个输入符号。计数/分隔触发块带状态将各字符送到末尾；符号特定规则识别三符号排列并重置计数，后续按所表示倍数扩展，解决 `c4_15_expansion`。

### 6.11 交错两半

寻找共有非字母数字分隔符，要求恰出现一次、两半等长且输出为逐对交错。程序把分隔符变为扩展的分隔符/标记结构，暴露交替字符并把选中字符送到末尾，最后擦除终止模式，解决 `c4_16_merge`。

## 7. 第 5 章——编译后的二进制算术

`_numeric_candidates()` 先识别数学关系，不枚举任意算术程序。候选解顺序为二进制转一元、加一、一个识别出的双操作数运算。

双操作数 `_infer_binary_operation()` 要求一个非二进制分隔符，解析两侧，并依次检查 `add`、`subtract`、`multiply`、`divide`。除法输出二进制商和余数，以逗号分隔。

### 7.1 二进制到一元折叠

输出符号为 `a` 时：

```text
a1=1aa
a0=1a
1=a
```

`a` 段是在未处理二进制后缀旁的一元累加器；`1` 将其翻倍加一，`0` 翻倍，反复实现 `accumulator = 2*accumulator + bit`，解决 `c5_1_count`。

### 7.2 波纹进位加一

```text
(once)=(end)CARRY
1CARRY=CARRY0
0CARRY=1
CARRY=1
```

进位越过尾部 1 向左移动并把它们变成 0，在首个 0 处将其变为 1 后消失，或成为新的前导 1，解决 `c5_2_plus`。

### 7.3 以重复加一实现加法

右操作数折叠为一元工作 token；每个 token 对左侧执行同一二进制加一转换，守卫分开转换和算术。中间表示是“二进制左操作数加一元右操作数”，消费全部 token 解 `c5_3_plus2`。

### 7.4 以重复减一实现减法

减数折叠为一元 token，每个变为借位标记：越过 0 向左并把 0 变 1，在首个 1 处变 0（或删除不需要的前导 1）。重复计算 `c5_4_minus` 的非负差。

### 7.5 以一元笛卡尔积实现乘法

七个新角色编码左右守卫/一元 token、乘积 token、边界和进位。两操作数转为一元段；两类 token 相互穿越，每一对产生一个乘积 token，因此计数等于笛卡尔积大小。每个乘积 token 再对初始二进制零加一，清理解 `c5_5_multiply`。

### 7.6 以重复一元分组实现除法

十二个新角色编码被除数、除数、扫描、已标记除数单位、商单位、边界、进位和失败。机器将两数转为不同一元段；从剩余被除数匹配一个除数大小的组；每个完整组产生商单位；未匹配者为余数；用重复进位把商和逗号后的余数转回二进制；清理全部状态。解决 `c5_6_div`。所有算术候选解仍受 255 字符中间字符串限制，必须由 Executor 验证每个状态。

## 8. 第 6 章——无关键字状态

`_no_keyword_candidates()` 依次尝试常量收敛、特化回文机和有限距离条件映射。

### 8.1 常量收敛

所有输入符号映射为排序首符号，双字符折叠，最后标记映射为常量：

```text
b=a
c=a
aa=a
a=helloworld
```

先规范化再最终扩展，不用 `(return)` 解 `c6_1_hello3`。

### 8.2 自定界编码判断回文

Python 按 `value == value[::-1]` 分组，要求三个符号且每类标签一致。一个符号作 base，另外两个编码为 base 两侧宽度一或二的对称编码：

```text
first  -> E base E
second -> EE base EE
```

每个原符号成为由 `base`、`E` 构成的回文码字；原符号相等即码宽相等。

通过 `E=E@` 或 base-pair 规则在左侧附近插入新游标 `@`，交换规则将其移到首位。下一编码单元选择期望：

```text
@ base = @ BASE_EXPECTED
@ E    = @ E_EXPECTED
```

期望标记向右越过编码数据，末端匹配规则删除相等终单元。错误单元令期望无法匹配，转为失败标记，向左删除剩余编码，`@ FAILURE=false` 结束。成功后游标留在左侧，对缩短内部重复；无内容时 `@=true`。这个 22 行程序仅以普通替换从外向内判断相等：游标移动替代边界关键字，收敛为 `true`/`false` 替代 `(return)`，解决 `c6_2_palindrome2`。

### 8.3 以有限距离实现条件映射

`_infer_conditional_mapping()` 找到 condition、source、present target、absent target，剩余字母表符号作为 bridge。对 0 到 `max_input_length - 2` 的每个桥长产生两种方向：

```text
condition bridge... source = condition bridge... present_target
source bridge... condition = present_target bridge... condition
```

短间隔先行。所有存在 condition 的模式停止匹配后，`source=absent_target` 处理残余 source。有限展开解决 `c6_3_tob2`，不是任意字母表的通用存在测试。

## 9. 六种搜索组织对比

| 章节 | 假设发现 | 备选循环 | 编译后的机器 |
|---:|---|---|---|
| 1 | 映射加通用候选解 | 子集、字母次序、有序对 | 收敛局部改写 |
| 2 | 对全部标签的布尔谓词 | 标签角色、阈值、除数、次序 | 规范化、暴露模式、返回 |
| 3 | 边界等式和谓词 | 源/目标及角色排列 | 搬移和从外向内缩减 |
| 4 | 显式字符串等式 | 替代编译器、模计数、有界角色/计数搜索 | `(once)` 初始化转换器 |
| 5 | 精确算术求值 | 固定顺序测试操作 | 一元工作形式加二进制进/借位 |
| 6 | 精确语义谓词 | base 选择和有界间隔展开 | 自定界普通改写机 |

总体组织：

```text
从穷尽式表推断狭窄语义族
    -> 枚举未决离散参数
    -> 把每种选择编译为完整 A=B 文本
    -> 拒绝重复和超预算程序
    -> 由 Executor 接受或拒绝操作行为
    -> 失败后前进到下一预排序候选解
    -> 提交第一个完整通过者
```

## 10. 已实现搜索的限制

- 没有后备语法搜索；模板耗尽抛 `CandidateSynthesisError`。
- 失败详情不指导后续候选解，只消费通过/失败。
- 优先级由源码顺序决定，不由学习适应度或代价决定。
- 首次通过即胜出，不再找更短或更快解。
- 每个候选解运行全部用例，没有早期不匹配中止或渐进子集计划。
- 通过程序先试运行一次，以 `submit=True` 再运行一次，再由 Manager 独立验证第三次。
- 排列是阶乘复杂度，子集枚举是指数复杂度，但所含字母表很小。
- 中心旋转搜索无界；`cut2` 标记数止于 99。
- 若干模板按最大给定输入长度定尺寸。
- 新工作符号来自有限偏好列表。

这些是实现的核心权衡：强语义识别和精心设计的 A=B 编译器取代巨大无限制程序搜索。

## 11. 提交边界

1.2、1.3 节描述试通过、`submit=True` 重跑和 Manager 反馈循环。最终边界很简单：只有 Manager 的独立完整验证通过才能以 `pending` 持久化；只有所有者在原版游戏中测试后才能把候选解标为 `accepted`。
