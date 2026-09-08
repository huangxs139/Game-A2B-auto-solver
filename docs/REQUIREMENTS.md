# A2B Auto Solver — Requirements

## 1. Purpose and Scope

This project develops Python command-line tools that automatically produce valid programs for the programming game **A=B**.

It is also an experimental software-engineering project for practicing a complete workflow covering requirements, architecture, planning, implementation, testing, review, and delivery.

Primary runtime environment:

* WSL2
* Miniconda3
* Python 3.14

Cross-platform support is not required.

The problem set is closed and authoritative:

* exactly 6 known chapters;
* approximately 10 puzzles per chapter;
* approximately 60 puzzles total.

Support for future chapters, unknown instructions, newly added puzzles, external problem sets, or hypothetical future game changes is not required.

---

## 2. Puzzle Data

Each puzzle provides structured data containing at least:

* puzzle identifier/number;
* title;
* natural-language description;
* chapter number;
* `min_lines`;
* complete input list;
* complete expected-output list.

A puzzle may contain thousands of input/output pairs.

The supplied pairs are trusted, complete, and exhaustive for local correctness evaluation.

Original puzzle data is authoritative and immutable. Solver, Executor, and supporting tools must not modify it.

Natural-language descriptions are not required as runtime Solver input and are not part of formal correctness.

Interpretation of natural-language game documentation when constructing formal Rules is a development-time activity. Runtime natural-language understanding or an LLM is not required.

---

## 3. Formal Problem Definition

Conceptually:

```text id="g9h7jt"
Problem = (ChapterRules, InputOutputPairs, min_lines)
```

A locally valid candidate must:

1. contain no more than `min_lines` instruction lines;
2. when executed as its final serialized A=B program through the Executor, produce the expected output for every supplied input.

The Solver need not find the shortest possible program. Once an acceptable candidate is found, it must stop searching for alternative or shorter solutions for that puzzle.

No correctness requirement exists outside the supplied exhaustive data. A solution highly specialized to that data is acceptable.

---

## 4. A=B Rules

One machine-readable representation of the known A=B rules must serve as the authoritative runtime source of chapter semantics.

It must represent the behavior needed for all six chapters, including:

* available instructions;
* instruction syntax;
* instruction semantics;
* execution-flow semantics;
* chapter-specific instruction availability.

Instruction semantics do not change between chapters; chapters may add or remove available instructions.

Solver and Executor must use the same authoritative Rules.

Rules describe the A=B problem, not Solver search knowledge. Solver-specific heuristics, templates, candidate-generation constraints, learned parameters, or strategies must not become authoritative Rules.

Rules are development-maintained runtime inputs and must not be autonomously modified by Solver or Executor.

Rules need only support the six known chapters. A generic rule-description system for arbitrary future semantics is not required.

---

## 5. Executor

The project must provide an Executor capable of executing serialized A=B programs according to the authoritative Rules and faithfully enough to support local validation.

Programs may enter infinite execution cycles. Executor must detect nontermination caused by repeated execution states or otherwise prevent invalid looping programs from running indefinitely.

Correct A=B solutions are expected to terminate.

Historical chapter-specific simulators may be inspected, tested, refactored, replaced, or redesigned.

Their architecture and APIs are not compatibility requirements; behavioral correctness is.

---

## 6. Solver

Solver must automatically produce an acceptable candidate for every puzzle in the closed problem set. Partial or best-effort coverage is insufficient for final project completion.

Any suitable algorithmic approach is permitted, including:

* program synthesis;
* search;
* heuristics;
* constraint solving;
* machine learning;
* hybrid approaches.

No particular algorithm is required. Machine learning is neither required nor prohibited.

### Search Space

Legal programs must not be excluded merely because they introduce characters or intermediate strings absent from puzzle inputs or outputs.

Puzzle characters, short auxiliary strings, common templates, and similar observations may be used as heuristics or search priorities, but not incorrectly treated as A=B semantic rules.

Concrete search-space design is an implementation concern.

### Puzzle-Specific Strategies

Solver may use chapter-specific or puzzle-specific strategies. No requirement exists that a solving technique generalize to other puzzles.

How strategies are selected, learned, adapted, or reused is algorithm-dependent.

The user is not required to provide puzzle-specific solving hints.

### Nondeterminism

Solver need not be deterministic.

Repeated executions need not reproduce the same:

* search trajectory;
* intermediate state;
* candidate program.

### Performance

No numerical performance SLA is imposed, including mandatory:

* puzzle/chapter/total time limits;
* memory limits;
* candidate-count limits;
* CPU/GPU utilization targets.

GPU, CUDA, hardware acceleration, and multicore parallelism are not requirements.

An unusually long-running search may be manually interrupted and investigated as an algorithm-development issue.

---

## 7. Validation

### Search-Time Validation

Solver may validate candidates against individual cases, subsets, progressively expanding sets, the complete dataset, or another algorithm-dependent selection.

### Final Local Validation

Before a candidate becomes the current official candidate:

1. serialize it into final native A=B instruction text;
2. execute that exact representation through Executor;
3. pass every supplied input/output pair;
4. satisfy `min_lines`.

Only the final serialized A=B representation is authoritative. Solver-internal ASTs, tokens, objects, or other representations are implementation details.

### Real-Game Validation

Executor-based validation is local machine validation only.

Final puzzle acceptance occurs only when the owner manually enters the candidate into the real A=B game and confirms acceptance.

If a candidate passes complete local validation but fails in the real game, treat this as evidence of an implementation/formalization defect or mismatch, not an ordinary Solver search failure. Investigate and correct the root cause before re-solving as necessary.

---

## 8. Puzzle State

Per-puzzle solving state must be persisted and distinguish machine-generated facts from owner-controlled decisions.

Machine-managed information may include:

* current candidate;
* local validation result;
* relevant run/result information.

Owner-controlled state includes whether a candidate has been:

* accepted through real-game validation;
* rejected;
* explicitly returned for re-solving.

Only the owner may modify owner-acceptance decisions. Automated components must never mark real-game validation as successfully completed.

A superseded failed candidate may be replaced; separate candidate-history retention is not required.

No separate final-answer database or compiled answer collection is required.

Per-puzzle state may be committed to Git.

---

## 9. CLI Workflow

### `solve all`

The primary workflow must provide:

```text id="0zx1ny"
solve all
```

It processes the closed problem set by chapter and puzzle in original puzzle order.

Puzzles whose persisted state indicates that no further solving work is currently required are skipped.

When the first locally valid candidate is found:

1. persist it;
2. stop solving that puzzle;
3. continue with other applicable puzzles.

Owner validation may remain pending without blocking other puzzles.

`solve all` may terminate normally when no puzzle currently requires Solver work, including when all puzzles have local candidates but some await owner validation.

The final summary must distinguish this from complete project success.

A puzzle without a candidate is normally an active search problem. Search may continue until:

* a candidate is found;
* the owner requests graceful termination;
* a program-level failure occurs.

### Targeted Debug Execution

The CLI must support targeted execution of an individual puzzle.

Debug execution may force-run a puzzle that persisted state would normally skip, but must not silently overwrite authoritative candidate or owner-controlled state.

### Basic CLI Quality

The CLI must provide:

* discoverable help;
* understandable errors;
* meaningful process exit behavior.

No installer, setup wizard, GUI, sophisticated TUI, or support for arbitrary unfamiliar project-directory layouts is required.

---

## 10. Failure and Interruption

Program-level failures are fail-fast.

Examples include:

* invalid/corrupted Rules;
* Executor exceptions;
* unhandled Solver exceptions;
* corrupted persisted state;
* other conditions making continued results untrustworthy.

The program must not silently continue solving other puzzles after such failures merely to maximize throughput.

A valid but long-running search is not a program-level failure.

The owner must be able to gracefully stop long-running search at a safe point.

Graceful interruption must preserve useful diagnostics.

Resumable search checkpoints and exact restoration of prior internal search state are not required.

---

## 11. Diagnostics

The system must support Release and Debug operation.

Release operation should concisely report useful information such as:

* progress/current puzzle;
* candidate discovery;
* validation results;
* elapsed time where useful;
* errors;
* final run summary.

Debug operation must provide substantially richer diagnostics suitable for Solver investigation. Depending on the Solver, this may include:

* strategy selection;
* search-space expansion;
* pruning;
* candidate statistics;
* validation-failure distributions;
* important parameters.

Debug instrumentation may perform additional observation, validation, and diagnostic checks, but must not intentionally change Solver logic or manipulate Solver state merely to obtain different solving behavior.

Diagnostics required for post-run investigation must be persisted to files.

A Debug run should provide a human-readable summary and raw diagnostic data where needed, attributable to the same run.

Debug reports and raw data are temporary run artifacts by default, not authoritative project state.

---

## 12. Optional Learned State

If the selected Solver produces reusable learned or trained state, it may be persisted.

Learned state is separate from:

* authoritative Rules;
* original puzzle data;
* owner-controlled acceptance state.

Learning context is chapter-local by default.

If persistent pretrained state is implemented:

* state is maintained separately per chapter;
* new learned state is saved automatically when appropriate;
* new checkpoints must not overwrite existing checkpoints;
* successive checkpoints use advancing sub-identifiers or equivalent versioned identities;
* checkpoints may be committed to Git and the remote repository.

If `--pretrained` is provided, it may load persisted learned state and continue applicable unsolved work.

Without pretrained state, Solver begins from its defined initial learning state.

Internal representation, update, and reuse behavior are Solver-architecture decisions.

---

## 13. Dependencies

Third-party Python dependencies are permitted, including libraries for:

* search;
* SAT/SMT/constraint solving;
* scientific computation;
* machine learning.

The project is not restricted to the standard library.

Any new third-party dependency requires owner approval before introduction.

---

## 14. Completion

The following are distinct:

### Process Termination

A CLI process ending does not imply puzzle or project completion.

### Local Candidate Success

A puzzle has a locally valid candidate when its final serialized program satisfies `min_lines` and passes every supplied input/output pair through Executor.

This is not final acceptance.

### Final Puzzle Acceptance

A puzzle is finally accepted only after owner verification in the real A=B game.

### Project Completion

Solving is complete only when **every puzzle in the closed problem set has been accepted by the owner through real-game validation**.

Having locally valid candidates for all puzzles while owner validation remains pending is not project completion.

---

## 15. Verification and Acceptance Model

Project work follows the applicable global Codex verification model.

For this project:

* exhaustive exported I/O and Executor may provide much of the domain-level automated validation;
* a comprehensive conventional unit-test suite is not independently required merely for its own sake;
* applicable low-cost implementation and regression verification should still be performed;
* Codex self-review remains mandatory;
* final acceptance belongs exclusively to the owner.

No automated component may claim owner acceptance.

---

## 16. Non-Requirements

Unless explicitly superseded later, the project does not require:

* unknown or future puzzle support;
* future chapter/instruction support;
* unseen-input generalization;
* runtime natural-language understanding;
* an LLM API;
* machine learning;
* optimization below `min_lines`;
* deterministic solving;
* strict search reproducibility;
* numerical performance guarantees;
* GPU or CUDA support;
* cross-platform support;
* resumable Solver search checkpoints;
* permanent retention of superseded failed candidates;
* an independent final-answer collection;
* compatibility with historical Simulator APIs;
* comprehensive abstraction for hypothetical future A=B rule systems.
