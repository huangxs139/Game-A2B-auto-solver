# A2B Auto Solver: Implemented Solving Algorithms

This document explains the algorithms that actually synthesize A=B programs
in `src/solver.py`. Its subject is the search itself: how the Solver recognizes
a possible transformation from puzzle data, how it turns that hypothesis into
native A=B instructions, which alternatives it enumerates, how Executor
failure controls the next trial, and why the generated rewrite systems work.

The Solver is a deterministic, template-based program synthesizer for the
included six-chapter puzzle set. It is not a neural model, a statistical
learner, or an unrestricted enumeration of all legal A=B programs. It combines
two kinds of computation:

1. Python recognizers analyze the complete input/output table and identify a
   transformation family, such as character mapping, length modulo a divisor,
   palindrome recognition, or binary addition.
2. A=B templates compile that family into one or more concrete programs. The
   real Executor runs each program and decides whether its operational behavior
   matches every supplied case.

That distinction—recognizing *what* the examples do and synthesizing *how A=B
can do it*—is the core of the implementation.

## 1. The actual search loop

The common lifecycle is implemented by `CandidateSynthesisAlgorithm` and
`SolverFramework`.

### 1.1 Candidate production is lazy and ordered

`CandidateSynthesisAlgorithm` owns an iterator returned by
`_generate_candidates(puzzle)`. The iterator dispatches to exactly one chapter
generator:

```text
chapter 1 -> _basic_replacement_candidates
chapter 2 -> _return_keyword_candidates
chapter 3 -> _boundary_keyword_candidates
chapter 4 -> _once_keyword_candidates
chapter 5 -> _numeric_candidates
chapter 6 -> _no_keyword_candidates
```

Candidates are not collected and globally ranked. Python `yield` order is the
priority order. The first candidate produced is tried first, and generation
continues only as far as needed to find a passing program.

Before a yielded program reaches Executor, `_generate_candidates()` removes an
exact duplicate if the same serialized text has already appeared and rejects
it if `len(code.splitlines()) > puzzle.min_lines`. The remaining program is a
complete, executable A=B candidate—not a partial AST or a fragment awaiting
completion.

### 1.2 A trial always uses the complete dataset

The framework protocol permits a strategy to request selected case indices,
but the implemented chapter algorithm never does so. Every proposal is run on
every input/output pair.

For each case, `SolverFramework._trial_candidate()` records the input,
expected output, Executor result, and exact-output-match flag. A proposal
passes only when every execution terminates normally or through `(return)`,
every output matches, and no framework failure reason exists.

Malformed programs, detected cycles, overlong operating strings, and wrong
outputs are normal candidate failures. An Executor infrastructure error aborts
search because the result cannot be trusted.

### 1.3 What “adjusting after failure” actually means

The current Solver does **not** inspect which cases failed, calculate an error
score, edit the failed program, or learn new rewrite rules from an execution
trace. The concrete algorithm reads only `feedback.passed`.

Its loop is equivalent to:

```python
for code in ordered_candidate_generator(puzzle):
    feedback = execute_on_every_case(code)
    if feedback.passed:
        execute_on_every_case(code, submit=True)
        return code
raise CandidateSynthesisError
```

A failure therefore causes one state change: the lazy generator advances to
its next candidate. Apparent “adjustments” come from the generator's organized
parameter loops—for example, trying the next alphabet ordering or increasing a
marker count—not from analysis of the failure details.

This is search with semantic feedback: the generator supplies a planned
sequence of hypotheses and Executor supplies the accept/reject oracle. It is
not feedback-guided program repair.

If Manager's later independent validation rejects a submitted candidate, the
same `SolverSession` and generator iterator are retained. The validation
failure is returned to `propose()`, which likewise advances to the next
candidate instead of restarting at candidate one.

### 1.4 Recognition tests are not Executor trials

Many generator loops test a semantic hypothesis directly in Python before
yielding anything:

```python
if all(expected == hypothesized_transform(value)
       for value, expected in puzzle_cases):
    yield compile_hypothesis_to_a2b_program(...)
```

Failed hypotheses are Python comparisons and never become A=B trials. Other
loops deliberately emit unresolved alternatives. Chapter 1 emits rewrite
systems for every alphabet order; Chapter 4 `cut2` emits successive marker
counts. Executor must resolve those operational alternatives.

## 2. How templates implement logic

Recognizing `output == reverse(input)` does not solve an A=B puzzle by itself.
The relation must be compiled into ordered rewrite rules under A=B control
flow: scan top to bottom, execute the first applicable instruction, restart at
line one, and stop when no line applies or `(return)` executes.

Rule order is therefore control flow. An early cleanup rule can destroy state
needed later; an empty-left-side rule can loop unless guarded by `(once)`; and
a local substitution can re-enable itself. Every template is a small
string-rewriting machine, often with an explicit intermediate representation.

Four techniques recur:

- **Canonicalization:** sort symbols or map them to a common marker so a
  global property becomes a local run pattern.
- **Cancellation:** delete opposing tokens so the residual type or length
  represents a comparison result.
- **Fresh-symbol state:** use characters absent from inputs and outputs as
  cursors, phases, boundaries, counters, carry/borrow flags, or encodings.
- **Relocation:** use right-side `(start)` and `(end)` to turn a local rewrite
  into a scan; use `(once)` to initialize its state exactly once.

The Rules define what these instructions mean and which chapters allow them.
They do not contain Solver templates or heuristics. Solver chooses a candidate;
Executor applies the Rules to the serialized program.

## 3. Chapter 1 — plain rewrite systems

`_basic_replacement_candidates()` has this fixed candidate order:

1. inferred position-wise character mapping;
2. collapse all adjacent runs;
3. remove repeated runs for every nonempty symbol subset;
4. sorting systems for every alphabet permutation; and
5. two-symbol frequency comparison for every ordered pair.

### 3.1 Direct mapping

`_infer_character_mapping()` requires equal input/output lengths and builds a
consistent `source -> target` function from all corresponding positions. A
source paired with two targets rejects the hypothesis. Only changed mappings
are emitted, such as:

```text
a=A
b=B
c=C
```

This solves `c1_1_atob` and `c1_2_uppercase`. Executor remains necessary
because sequential replacements can interact when a target is also a source.

### 3.2 Run algorithms

The next unconditional candidate contains `xx=x` for every symbol. Repeated
application collapses each maximal run to one character, solving
`c1_3_singleton`.

Then `combinations(symbols, count)` enumerates subsets in increasing size. For
every selected symbol `x`, the program contains:

```text
xxx=xx
xx=
```

The first rule reduces a long run toward length two; the second deletes the
pair. Singletons survive. Selecting only `a` solves `c1_4_singleton2`.

### 3.3 Sorting by enumerating total orders

For every permutation of the input alphabet, the generator emits a swap for
each inverted pair:

```python
for ordering in permutations(symbols):
    for left in ordering:
        for right in ordering:
            if rank[left] > rank[right]:
                emit(f"{left}{right}={right}{left}")
```

Every rewrite lowers the inversion count under the proposed order, so the
system terminates at a sorted string. For `a < b < c`:

```text
ba=ab
ca=ac
cb=bc
```

Python does not infer the desired order. Executor rejects incorrect
permutations and accepts the one matching every expected output.

For `c1_5_sort`, the actual sequence is: all-symbol run collapse; each
one-symbol repeated-run remover that fits the line budget; discard larger
over-budget subset programs; then try `a < b < c`, which passes as the fifth
Executor candidate.

### 3.4 Count comparison by cancellation

For every ordered symbol pair, the Solver emits unlike-pair cancellation and
same-symbol collapse:

```text
ab=
ba=
aa=a
bb=b
```

As deletion brings formerly separated symbols together, unlike pairs continue
to cancel. Only the majority symbol remains, and its run collapses to one.
`c1_6_compare` is the seventh actual candidate after earlier generic and sort
candidates fail. No failed candidate is edited; the generator reaches this
next construction.

## 4. Chapter 2 — predicates and immediate return

`_return_keyword_candidates()` compiles classifiers by normalizing the input
until a decisive pattern exists, then using `(return)`.

Its exact discovery order is:

1. constant output;
2. for every ordered `(true_output, false_output)` pair:
   1. every symbol-count threshold;
   2. every exact target length;
   3. the all-counts-odd predicate, with every alphabet order;
   4. exactly one singleton run;
   5. every strict three-symbol frequency ordering;
3. every possible length modulus;
4. every three-symbol ordering for `most` and `least`.

Most loop iterations yield nothing because `_matches_boolean()` first requires
the hypothesis to label every case correctly.

### 4.1 Constant, threshold, and exact length

A constant table compiles to `=(return)<output>`.

For `value.count(x) >= n`, other symbols are deleted. A run of `n` copies of
`x` returns true; the empty-left-side fallback returns false. Thresholds from 1
through the maximum input length are checked against the full table. This
solves `c2_2_aaa`.

For exact length `n`, every symbol maps to one marker. A run of `n+1` markers
returns false before a run of `n` can match; exactly `n` returns true; shorter
inputs fall through to false. Priority encodes the upper-bound guard and solves
`c2_3_exactly`.

### 4.2 Odd counts

The recognizer tests whether every symbol count is zero or odd. For each
alphabet order, the candidate sorts equal symbols together, reduces `xxx` to
`x` (preserving parity), returns false if any `xx` remains, and otherwise
returns true. This solves `c2_5_odd`.

### 4.3 Exactly one singleton run

This is about maximal adjacent runs, not global character frequency. For each
symbol `x`:

```text
xxx=xx       # reduce a long run
xx=R         # encode a nonsingleton run
x=S          # encode a singleton run
```

Fresh `R` markers are erased. `SS` returns false, one `S` returns true, and no
`S` returns false. This solves `c2_6_only`.

### 4.4 Strict frequency ordering

For each `(lower, middle, upper)` permutation, Python tests:

```text
count(upper) > count(middle) > count(lower)
```

The candidate sorts by this order. Cancellation exposes surplus `middle` over
`lower` in a fresh marker; a surviving `upper` beyond that marker proves the
second strict inequality. Only that configuration returns true. This solves
`c2_7_ascend`.

### 4.5 Length modulo an inferred divisor

Divisors `2..max_length` are tried in order. A divisor is usable only if every
remainder has one consistent output and all remainders occur. The program maps
all symbols to one marker, replaces `d+1` markers by one marker repeatedly, and
maps residual lengths `d, d-1, ..., 1` to outputs. Length `d` represents
remainder zero. Longest residuals come first so shorter patterns do not steal
their match. This solves `c2_4_remainder`.

### 4.6 Most and least

For `most`, the recognizer requires each output to be the most frequent symbol.
The program sorts runs and returns on a run of
`max_length // 2 + 1`. If no run is initially that long, an empty-left-side
rule inserts one of each symbol; equal increments preserve the original leader
until it crosses the threshold first. This solves `c2_8_most` for the supplied
table.

For `least`, the recognizer uses minimum `value.count`. Each ordered candidate
sorts the three symbols and applies a compact, specialized residual-pattern
decision table. Executor selects the ordering valid for `c2_9_least`; this is
not a general arg-min compiler.

Together these strategies solve the Chapter 2 sequence `hello`, `aaa`,
`exactly`, `remainder`, `odd`, `only`, `ascend`, `most`, and `least`.

## 5. Chapter 3 — boundary algorithms

`_boundary_keyword_candidates()` searches in this order:

1. for each symbol, boundary stripping and rotation to its first occurrence;
2. every source/target pair for boundary-run replacement;
3. every start/end-symbol pair for swapping boundary runs;
4. every output-label ordering for same-ends and palindrome predicates; and
5. every three-symbol role ordering for emitting the most frequent run.

Each family is checked against the full table before yielding. Permutations
inside a recognized family are resolved by Executor.

### 5.1 Strip and rotate

If every output equals `value.strip(symbol)`, the program deletes that symbol
at both boundaries. Restarts remove entire boundary runs. This solves
`c3_1_Remove`.

For rotation, a candidate target must occur in every input and the output must
be the input rotated to its first occurrence. Every other leading symbol is
moved to `(end)`. When the target reaches the front, no rule applies. This
solves `c3_2_spin` with `a` as target.

### 5.2 Replace or exchange boundary runs

`_replace_boundary_runs()` simulates replacing maximal leading and trailing
runs of `source` with `target`. A matching hypothesis compiles to a four-line
machine using two fresh markers to relocate and restore both runs. This solves
`c3_3_atob2`.

`_swap_boundary_runs()` recognizes exchange of a leading run of one symbol and
a trailing run of another. The candidate moves trailing symbols to the start
with a marker, then moves matched leading symbols to the end, and finally
erases the marker. This solves `c3_4_swap`.

### 5.3 Compare ends

For each possible first symbol, the candidate removes it and places a distinct
marker at the end. A higher-priority rule recognizes the corresponding last
symbol beside that marker and returns true; otherwise the fallback returns
false. This solves `c3_5_match`.

### 5.4 Palindrome by outside-in reduction

A boundary rule encodes the first symbol as an open marker, that symbol, and a
close marker at the end. A rule of the form `x OPEN x CLOSE=` removes this
encoded first symbol with an equal last symbol. The process repeats on the
interior. A mismatched marker arrangement returns false; complete cancellation
falls through to true. This solves `c3_7_palindrome`.

### 5.5 Preserve the winning multiplicity

For `c3_6_most2`, Python requires the output to be the most frequent symbol
repeated by its count. For every permutation of three symbol roles, a
specialized ten-line machine combines cancellation, swaps, boundary
relocation, and expansion. Unlike Chapter 2 `most`, it must eliminate losers
while preserving or reconstructing the winner's full run. Executor determines
the working role assignment.

## 6. Chapter 4 — initialized transducers

`(once)` allows a finite state seed. Most Chapter 4 programs initialize
markers, move them through data, emit transformed data at a boundary, and
erase the markers.

The generator checks, in source order:

1. prepend a constant;
2. remove `n` symbol occurrences from the left or right;
3. delete a fixed-length prefix;
4. swap first and last characters;
5. reverse the string;
6. perform a pointwise map with a cursor;
7. retain `value[1::2]`;
8. duplicate the input;
9. two conditional-map implementations;
10. select the center;
11. bounded fixed-position-deletion search;
12. append a prefix copy;
13. delete the center;
14. expand characters by one-based position; and
15. interleave equal halves.

Earlier source position does not necessarily mean an Executor trial: most
branches first prove their transformation equation against every case.

### 6.1 Prefixes and occurrence deletion

A constant prefix becomes one `(once)=(start)<prefix>` instruction, solving
`c4_1_hello2`.

To delete the first `n` occurrences of `x`, the program emits `n` separate
`(once)x=` lines. Each consumes one leftmost occurrence, solving
`c4_2_remove2`.

To delete from the right, it appends `n` markers, moves a marker left across
every non-target symbol, deletes `x MARKER`, and cleans unused markers. This
reverses the normal leftmost bias and solves `c4_4_remove3`.

### 6.2 Prefix cut, end swap, and reversal

Prefix cutting seeds `n` markers at the start; `MARKER x=` consumes one marker
and one character. This solves `c4_3_cut`.

The end-swap recognizer checks
`value[-1] + value[1:-1] + value[0]`. A scan marker transports the first symbol
to the end; a boundary marker then transports the old last symbol to the
start. This solves `c4_5_reverse`, which performs an end swap rather than full
reversal.

Full reversal seeds `max_length` markers. `MARKER x=(start)x` consumes original
characters left-to-right but prepends each result, reversing their order.
Extra markers are erased. This dataset-sized construction solves
`c4_6_reverse2`.

### 6.3 Cursor map and alternating selection

A pointwise map inserts a cursor at the start and repeatedly performs
`CURSOR source=target CURSOR`. Generated targets remain behind the cursor and
cannot cascade into later mappings. Cursor cleanup solves `c4_9_atob3`.

For `value[1::2]`, two initial markers encode alternating phase. One transition
discards a character; the next preserves a character and restores the marker
pair after it. Cleanup leaves indices 1, 3, 5, and so on, solving
`c4_10_odd2`.

### 6.4 Whole-string duplication

A boundary marker is appended. When an original symbol reaches it, a rule
leaves the boundary, appends two symbol copies, and creates a scan marker. The
scan marker moves through the remaining original input, sending copies to the
end. Cleanup leaves two complete strings and solves `c4_11_clone2`.

### 6.5 Conditional mapping: one hypothesis, two compilers

`_infer_conditional_mapping()` enumerates roles
`(condition, source, present_target, absent_target)` until every case satisfies:

```python
expected == value.replace(
    source,
    present_target if condition in value else absent_target,
)
```

The first compiler marks one condition occurrence, moves state to the start,
restores the condition, and scans right while mapping each source. If no
condition existed, a final plain rule produces `absent_target`.

The second constructs a local source/marker/condition arrangement, moves it
through intervening symbols, maps a source after proving condition presence,
then applies the absent-case fallback.

For `c4_12_tob`, the first compiled candidate fails and the second passes. The
second is not learned from the first failure; it is the next planned `yield`.

### 6.6 Center selection by modular rotation

For odd-length inputs whose output is the center, `_find_rotation_count()`
searches `r = 0, 1, 2, ...` until, for every observed length:

```text
r mod length = floor(length / 2)
```

The program seeds `r` markers. Each moves one leading symbol to the end, so the
net rotation places every supported length's center first. Start-return rules
select it. This solves `c4_13_center`. The integer search is unbounded and has
no general inconsistency check; it terminates for the included length set.

### 6.7 Fixed-position deletion by bounded search

Python first confirms that deleting some fixed zero-based position produces
every output. The position only enables the strategy; it is not compiled
directly. The actual search is:

```python
for ordering in permutations(symbols):
    low, middle, high = ordering
    for marker_count in range(1, 100):
        yield six_line_marker_machine(low, middle, high, marker_count)
```

The machine transforms marker runs and symbol roles until one position is
erased. Executor discovers which operational parameter pair works.

For `c4_7_cut2`, the first ordering is correct; counts 1 through 11 fail and
count 12 passes. This is the clearest iterative parameter search in the code.
A required count of 100 or more would never be tried.

### 6.8 Prefix copy

For each prefix length, Python checks `expected == input + input[:n]`. Forward
markers consume the prefix and append two copies of each symbol plus restore
state. Restore markers move one copy back to the start; the second remains
appended. This solves `c4_8_clone`.

### 6.9 Center deletion

The recognizer requires odd lengths and exact deletion of index
`len(input)//2`. The candidate seeds counter, transfer, and phase markers. Its
rules grow counter blocks, relocate duplicated symbols, reset a phase at the
start, and erase the symbol reached where traversal phases meet. This solves
`c4_14_center2`.

The counter population controls how often each duplicated segment is revisited
and cancelled. Symmetric outer positions eventually retain one data copy,
while the unique center loses its final copy. Cleanup then removes the marker
scaffolding.

### 6.10 Positional expansion

The recognizer checks:

```python
expected == "".join(character * position
                    for position, character in enumerate(value, 1))
```

and requires three input symbols. Counter/separator trigger blocks move each
character to the end with marker state. A symbol-specific rule recognizes the
three-symbol arrangement and resets counters; later transitions expand the
matched symbol by the represented multiplicity. Cleanup solves
`c4_15_expansion`.

### 6.11 Interleaving halves

The generator finds a shared non-alphanumeric delimiter and requires one
occurrence, equal-length halves, and pairwise interleaving output. The program
turns the delimiter into an expanding delimiter/marker structure that exposes
alternating characters and moves each selected character to the end. Terminal
patterns are erased. This solves `c4_16_merge`.

## 7. Chapter 5 — compiled binary arithmetic

`_numeric_candidates()` recognizes mathematics first; it does not enumerate
arbitrary arithmetic programs. Candidate order is binary-to-unary conversion,
increment, then one recognized two-operand operation.

For two operands, `_infer_binary_operation()` requires one non-binary
delimiter, parses both sides, and tests `add`, `subtract`, `multiply`, and
`divide` in that order against every output. Division formats binary quotient
and remainder separated by a comma.

### 7.1 Binary to unary fold

For output symbol `a`:

```text
a1=1aa
a0=1a
1=a
```

The `a` run is a unary accumulator beside the unprocessed binary suffix. A `1`
doubles it and adds one; a `0` doubles it. Repeated rewrites implement
`accumulator = 2*accumulator + bit`. This solves `c5_1_count`.

### 7.2 Ripple-carry increment

```text
(once)=(end)CARRY
1CARRY=CARRY0
0CARRY=1
CARRY=1
```

The carry moves left over trailing ones, changing them to zeros. It disappears
at the first zero after changing it to one, or becomes a new leading one. This
solves `c5_2_plus`.

### 7.3 Addition as repeated increment

The right operand is folded into unary work tokens. Each work token runs the
same binary increment transitions against the left operand. Guards separate
conversion from arithmetic. The intermediate representation is “left operand
in binary plus right operand in unary.” Consuming every token solves
`c5_3_plus2`.

### 7.4 Subtraction as repeated decrement

The subtrahend is folded into unary work tokens. Each becomes a borrow marker:
it moves left over zero while changing zero to one, and changes the first one
to zero (or removes an unnecessary leading one). Repetition computes the
nonnegative differences in `c5_4_minus`.

### 7.5 Multiplication by unary cross-product

Seven fresh roles encode left/right guards and unary tokens, a product token,
a boundary, and carry. Both operands become unary runs. Moving the token types
across one another emits one product token per pair, so token count is the
Cartesian-product size. Each product token then increments an initially seeded
binary zero. Cleanup yields `c5_5_multiply`.

### 7.6 Division by repeated unary grouping

Twelve fresh roles encode dividend, divisor, scans, marked divisor units,
quotient units, boundaries, carry, and failure. The machine:

1. converts both operands to distinct unary runs;
2. matches one divisor-sized group against remaining dividend units;
3. emits a quotient unit for each complete group;
4. leaves unmatched dividend units as remainder;
5. converts quotient units to binary by repeated carry;
6. converts remainder units similarly after a comma; and
7. removes all work state.

This repeated-grouping algorithm solves `c5_6_div`. All arithmetic candidates
remain subject to the 255-character intermediate-string limit, so recognizing
the operation is not enough: Executor must validate every state.

## 8. Chapter 6 — state without keywords

`_no_keyword_candidates()` tries constant convergence, a specialized
palindrome machine, then finite-distance conditional mapping.

### 8.1 Constant convergence

All input symbols map to the first sorted symbol, doubles collapse, and the
last marker maps to the constant:

```text
b=a
c=a
aa=a
a=helloworld
```

Normalization occurs before final expansion, solving `c6_1_hello3` without
`(return)`.

### 8.2 Palindrome by self-delimiting encoding

Python first partitions cases by `value == value[::-1]` and requires three
symbols plus one consistent label per class. One symbol is selected as a base;
the other two become symmetric encodings of width one or two around that base:

```text
first  -> E base E
second -> EE base EE
```

After this phase, every original symbol is a palindromic code word over `base`
and `E`; equality of original symbols is equality of code-word width.

A fresh cursor `@` is inserted near the left edge by `E=E@` or, when two base
symbols meet, by the corresponding base-pair rule. Commute rules move `@` left
until it becomes the first character. Schematically, the next encoded unit
selects an expectation:

```text
@ base = @ BASE_EXPECTED
@ E    = @ E_EXPECTED
```

`BASE_EXPECTED` or `E_EXPECTED` then moves right across all encoded data. At
the far end, `base BASE_EXPECTED=` or `E E_EXPECTED=` removes a matching final
unit. A wrong final unit leaves the expectation marker unmatched; it changes
to a failure marker, which moves left while deleting the remaining encoding,
and `@ FAILURE=false` terminates the reduction.

After a successful match, the cursor remains at the left and repeats the same
process on the shorter encoded interior. When nothing remains to compare,
`@=true`. Thus the 22-line program performs an outside-in equality test using
only ordinary replacements: cursor motion substitutes for `(start)`/`(end)`,
and convergence to literal `true` or `false` substitutes for `(return)`. This
solves `c6_2_palindrome2`.

### 8.3 Conditional mapping by finite distance

`_infer_conditional_mapping()` discovers condition, source, present target,
and absent target. The remaining alphabet symbol becomes a bridge. For every
bridge length from zero through `max_input_length - 2`, both orientations are
emitted:

```text
condition bridge... source = condition bridge... present_target
source bridge... condition = present_target bridge... condition
```

Shorter gaps appear first. After all condition-present patterns stop matching,
`source=absent_target` handles residual sources. This finite unrolling solves
`c6_3_tob2`; it is not a general presence test for arbitrary alphabets.

## 9. The six search organizations compared

| Chapter | Hypothesis discovery | Alternative loop | Compiled machine |
|---:|---|---|---|
| 1 | mapping plus generic candidates | subsets, alphabet orders, ordered pairs | convergent local rewrites |
| 2 | Boolean predicates over all labels | label roles, thresholds, divisors, orders | normalize, expose pattern, return |
| 3 | boundary equations and predicates | source/target and role permutations | relocation and outside-in reduction |
| 4 | explicit string equations | alternative compilers, modular count, bounded role/count search | once-initialized transducers |
| 5 | exact arithmetic evaluation | operations tested in fixed order | unary work forms plus binary carry/borrow |
| 6 | exact semantic predicates | base choice and bounded gap expansion | self-delimiting plain-rewrite machines |

The complete organization is:

```text
infer a narrow semantic family from the exhaustive table
    -> enumerate unresolved discrete parameters
    -> compile each choice into complete A=B text
    -> reject duplicates and over-budget programs
    -> let Executor accept or reject operational behavior
    -> advance to the next preordered candidate on failure
    -> submit the first complete pass
```

## 10. Limitations of the implemented search

- There is no fallback grammar search. Exhausting templates raises
  `CandidateSynthesisError`.
- Failure details do not guide later candidates; only pass/fail is consumed.
- Candidate priority is source order, not learned fitness or cost.
- The first pass wins; no shorter or faster solution is sought afterward.
- Every candidate runs on every case, without early mismatch cutoff or a
  progressive subset schedule.
- The passing program runs once tentatively, once with `submit=True`, and a
  third time in Manager's independent validation.
- Permutations are factorial and subset enumeration exponential, though the
  included alphabets are small.
- Center rotation is unbounded; `cut2` marker counts stop at 99.
- Several templates are sized to the maximum supplied input length.
- Fresh work symbols come from a finite preference list.

These are the defining tradeoffs of the implemented Solver. Strong semantic
recognition and engineered A=B compilers replace an enormous unrestricted
program search.

## 11. Submission boundary

Sections 1.2 and 1.3 describe the tentative pass, `submit=True` rerun, and
Manager feedback loop. The final boundary is simple: only Manager's independent
full-validation pass permits persistence as `pending`, and only the owner can
mark that candidate `accepted` after testing it in the original game.
