# A2B Auto Solver Codebase Guide

[English](CODEBASE_GUIDE.md) | [简体中文](CODEBASE_GUIDE.zh-CN.md)

This guide is a navigation map for the current implementation. It is intended
for a Python developer who wants to trace a run, diagnose a failure, or change
the implementation without crossing the project's ownership boundaries.

For the user-facing purpose and commands, start with [`README.md`](../README.md).
For environment setup, CLI operation, state-management workflows, and common
troubleshooting, see [`GETTING_STARTED.md`](GETTING_STARTED.md). For a detailed
explanation of candidate synthesis and the chapter-specific strategies, see
[`SOLVING_ALGORITHMS.md`](SOLVING_ALGORITHMS.md). This guide instead focuses on
code organization, runtime control flow, component boundaries, and safe
extension points. The normative behavior and architectural constraints remain
in [`docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md) and
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Start here

The shortest useful reading order is:

1. [`a2bautosolver.py`](../a2bautosolver.py) — the tiny executable entry point.
2. [`src/manager.py`](../src/manager.py) — CLI handling, discovery, scheduling,
   validation, persistence, diagnostics, and process lifecycle.
3. [`src/solver_framework.py`](../src/solver_framework.py) — puzzle loading and
   the common proposal/feedback loop used by solving algorithms.
4. [`src/solver.py`](../src/solver.py) — the concrete data-driven candidate
   synthesizer for all six chapters.
5. [`src/executor.py`](../src/executor.py) — parsing and execution of native A=B
   programs according to [`src/rules/a2b_rules.yaml`](../src/rules/a2b_rules.yaml).
6. [`tests/`](../tests/) — executable examples of each boundary and of the
   integrated workflow.

The central dependency direction is:

```text
CLI
  -> Manager
       -> SolverFramework -> concrete SolvingAlgorithm
       -> validation worker
  -> both SolverFramework and validation worker use Executor
       -> Executor loads a2b_rules.yaml
```

The important distinction is that Manager and Solver both *call* Executor, but
neither reimplements A=B execution. Search-time trials help an algorithm decide
what to propose; only Manager-owned full validation authorizes persistence.

## Repository map

### Runtime and source

- [`a2bautosolver.py`](../a2bautosolver.py) imports and calls
  `src.manager.main`. Run it from the repository root so the `src` imports
  resolve naturally.
- [`src/manager.py`](../src/manager.py) is the integrated application. It owns
  the command parser, Manager, worker entry points, validation, state storage,
  reporting, and run summaries.
- [`src/solver_framework.py`](../src/solver_framework.py) contains immutable
  puzzle and feedback models, `PuzzleRepository`, the `SolvingAlgorithm`
  protocol, `SolverSession`, and `SolverFramework`.
- [`src/solver.py`](../src/solver.py) contains `CandidateSynthesisAlgorithm`,
  its factory, and the candidate generators and inference helpers used by the
  six implemented chapters.
- [`src/executor.py`](../src/executor.py) contains the sole A=B parser and
  execution engine: `Executor`, `ExecutionResult`, `ExecutionObservation`, and
  `TerminationKind`.
- [`src/rules/a2b_rules.yaml`](../src/rules/a2b_rules.yaml) is the protected,
  machine-readable runtime Rules definition. `DEFAULT_RULES_PATH` points here.

There is no installed-package layout, service layer, database, or independent
Validator subsystem. The application is a small repository-root CLI whose
modules are imported as `src.*`.

### Authoritative and persisted data

The principal data locations are [`test_data/`](../test_data/),
[`test_output/`](../test_output/), [`reports/`](../reports/), and the retained
natural-language source under [`rules/`](../rules/). Their schemas, runtime
treatment, and ownership boundaries are covered once in
[Files and artifact flows](#files-and-artifact-flows).

### Tests, tools, configuration, and project documents

- [`tests/test_executor.py`](../tests/test_executor.py),
  [`tests/test_solver.py`](../tests/test_solver.py),
  [`tests/test_manager.py`](../tests/test_manager.py), and
  [`tests/test_review_candidates.py`](../tests/test_review_candidates.py) form
  the `unittest` suite.
- [`tools/review_candidates.py`](../tools/review_candidates.py) is the
  owner-facing candidate review TUI. It is the normal code path for changing
  the owner-controlled `status` and optional `reason` fields in `.solve` files.
- [`tools/clean_test_data.py`](../tools/clean_test_data.py) is a destructive
  maintenance utility that deletes files in `test_data/` whose names do not
  match its pattern. It is not part of normal solving or validation and should
  not be used casually around authoritative inputs.
- [`requirements.txt`](../requirements.txt) currently pins the only runtime
  third-party dependency, PyYAML. All concurrency and IPC use the Python
  standard library.
- [`AGENTS.md`](../AGENTS.md) defines repository-specific contribution and
  authority rules. [`docs/`](../docs/) holds normative requirements,
  architecture, roadmap, and accepted feature specifications. They are project
  governance and design sources, not runtime configuration.
- [`user_docs/`](.) is for user/developer documentation, not normative runtime
  specifications.

Generated `__pycache__/` directories are interpreter artifacts and have no
architectural role.

## Components and ownership boundaries

### Manager: orchestration and authoritative local validation

The concrete Manager is `src.manager.Manager`. Its public entry methods are:

- `discover_puzzles()` — validates filenames, resolves all `.a2b` files, rejects
  duplicate chapter/puzzle positions, and returns numeric chapter/puzzle order;
- `solve_all(debug=False)` — loads persisted state, selects eligible puzzles,
  and runs the persistent workflow;
- `solve_target(problem_id)` — force-runs one puzzle in Debug mode without
  persisting a replacement candidate;
- `request_stop()` — sets a thread `Event` checked by the scheduling loop.

`Manager._run()` is the orchestration core. It groups selected puzzles by
chapter, starts chapter Solver processes up to `max_concurrency`, polls Solver
and validation pipes, routes validation failures back to the correct live
Solver session, advances a chapter after a pass, and produces `RunSummary`.

Authoritative full local validation is the function
`src.manager.validate_candidate()`. It checks the raw candidate line count and
runs the exact serialized candidate against every supplied input using
`Executor`. Its `ValidationResult` distinguishes:

- `ValidationOutcome.PASS` — all cases terminate normally with the expected
  output and the candidate satisfies the line limit;
- `ValidationOutcome.FAIL` — the candidate is invalid, nonterminating, too
  long, over `min_lines`, or produces a wrong output, while infrastructure is
  still trustworthy;
- `ValidationOutcome.ERROR` — Rules, Executor, or validation infrastructure
  failed, so Manager stops the whole run.

`PuzzleStateRepository` performs strict `.solve` loading and atomic candidate
persistence. `DiagnosticReporter` owns unique report filenames and associates
events with a shared per-run UUID. These helpers are inside `manager.py`
because state and report ownership are part of Manager orchestration, not A=B
semantics.

Manager must not acquire puzzle-specific search logic or instruction behavior.
If a change answers “which program should we try?”, it belongs in Solver. If it
answers “what does this instruction do?”, it belongs in Executor and may also
require an owner-approved Rules change.

### Solver: candidate synthesis and search-time feedback

Solver is split deliberately:

- `src/solver_framework.py` defines a stable lifecycle independent of any one
  strategy.
- `src/solver.py` implements the current strategies for the closed 47-puzzle
  problem set.

`SolverFramework.start()` resolves the puzzle, constructs `SolverContext`, asks
an `AlgorithmFactory` for a `SolvingAlgorithm`, and creates a chapter-bound
`Executor`. It returns a stateful `SolverSession`. `SolverFramework.solve()` is
the convenience form that starts a session and runs it to one submission.

`SolverSession.run_until_submission()` repeatedly:

1. calls `SolvingAlgorithm.propose(feedback)`;
2. validates the returned `CandidateProposal` structure;
3. executes the requested cases through `SolverFramework._trial_candidate()`;
4. returns the resulting `CandidateFeedback` to the same algorithm;
5. stops only when the algorithm marks a proposal `submit=True`.

The session retains the algorithm instance and feedback history across a
Manager full-validation failure. That retained identity is what allows the same
search to continue rather than restarting the puzzle.

The current factory is `src.solver.create_solver_algorithm()`. It creates one
`CandidateSynthesisAlgorithm` for any supported chapter. The algorithm iterates
the lazy stream from `_generate_candidates()`, proposes each candidate for
search-time execution, and—after a candidate passes—proposes the same code with
`submit=True`. If the stream is exhausted it raises
`CandidateSynthesisError`, which becomes a fail-fast Solver failure at Manager.

The concrete generator dispatch is chapter-based:

- chapter 1: `_basic_replacement_candidates()`;
- chapter 2: `_return_keyword_candidates()`;
- chapter 3: `_boundary_keyword_candidates()`;
- chapter 4: `_once_keyword_candidates()`;
- chapter 5: `_numeric_candidates()`;
- chapter 6: `_no_keyword_candidates()`.

`_generate_candidates()` deduplicates serialized programs and discards programs
whose `splitlines()` count exceeds the puzzle's `min_lines`. The chapter
generators recognize transformations from the exhaustive I/O data and emit
native A=B program text; helpers such as `_infer_character_mapping()`,
`_infer_binary_operation()`, `_matches_boolean()`, `_sorting_lines()`, and
`_fresh_symbols()` support that work. There is no puzzle-ID-to-answer table and
no dynamically loaded algorithm registry. See
[`SOLVING_ALGORITHMS.md`](SOLVING_ALGORITHMS.md) for the algorithmic explanation
rather than treating this navigation guide as a strategy reference.

Search-time success is advisory. Even though the current concrete proposals
default to all cases, only the later Manager-owned validation pass may write a
candidate to `test_output/`.

### Executor: the only A=B execution semantics

`src.executor.Executor` binds a chapter and a Rules file in `__init__()`. It
loads the YAML through `_load_rules()`, validates the limit schema through
`_load_limits()`, checks the chapter's available operation, and maps the Rules
operation ID `replace_leftmost_occurrence` to `_apply_instruction()`.

`Executor.execute(input_text, code_snippet, debug=False)` is the semantic entry
point. It:

1. parses raw lines with `_parse_program()`, enforcing serialized line length,
   comment, ASCII, equal-sign, reserved-character, keyword-side, and
   chapter-availability rules;
2. checks the initial operating-string limit;
3. scans instructions from the first line and applies the first executable
   instruction;
4. restarts the scan at line one after each successful instruction;
5. tracks consumed `(once)` lines as part of execution state;
6. terminates normally after a complete scan with no executable instruction,
   or immediately for a `(return)` replacement;
7. rejects repeated states and also enforces `max_steps` for growing cycles;
8. checks the operating-string limit after every successful instruction.

Outcomes are represented by `ExecutionResult` and `TerminationKind`: `NORMAL`,
`RETURN`, `NONTERMINATION`, `INVALID_PROGRAM`, or `EXECUTOR_ERROR`.
`terminated_normally` is true only for `NORMAL` and `RETURN`.

With `debug=True`, successful steps also produce immutable
`ExecutionObservation` records. `Executor.dump_observations()` serializes those
records to a caller-owned stream; Executor itself never chooses a report path
or writes puzzle state.

Do not implement an approximate interpreter in a Solver heuristic, Manager
validator, or tool. All claims about candidate execution must flow through
this Executor.

## Important data models and protocols

The main objects passed between layers are small frozen dataclasses:

- `Puzzle` (`solver_framework.py`) — runtime-relevant immutable data:
  `problem_id`, `chapter`, `min_lines`, `inputs`, and `expected_outputs`.
- `SolverContext` — the `Puzzle` plus the shared `rules_path`, given to an
  algorithm factory.
- `CandidateProposal` — serialized `code`, optional `case_indices`, and the
  `submit` flag. `case_indices=None` means all cases.
- `TrialResult` — one input, its expected output, the `ExecutionResult`, and a
  comparison flag.
- `CandidateFeedback` — a proposal, its trials, and non-case-specific failure
  reasons. Its `passed` property requires no reasons, correct outputs, and
  normal termination for every included trial.
- `SolverRunResult` — submitted code and accumulated search feedback.
- `PuzzleState` (`manager.py`) — parsed persistent state and the
  `requires_solver` eligibility rule.
- `ValidationResult` — Manager validation outcome, candidate metadata,
  optional failure feedback/error, and optional Debug trials.
- `RunSummary` — counts, interruption/fatal state, maximum observed chapter
  concurrency, and the process exit-code policy.

`SolvingAlgorithm` is a typing `Protocol` with one method:

```python
def propose(self, feedback: CandidateFeedback | None) -> CandidateProposal: ...
```

This is the primary extension seam for a replacement or experimental Solver.
An `AlgorithmFactory` receives `SolverContext`; Manager accepts a factory via
its constructor, which is also how integration tests inject controlled dummy
algorithms.

## End-to-end execution flow

### CLI selection and discovery

`a2bautosolver.py` calls `src.manager.main()`. `build_argument_parser()` defines
one command family:

```text
solve all [--max-concurrency N] [--debug]
solve cX_Y_name [--max-concurrency N] [--debug]
```

`main()` installs SIGINT/SIGTERM handlers that call `Manager.request_stop()`.
For `all`, it calls `Manager.solve_all(debug=args.debug)`. Any other valid
puzzle identifier calls `Manager.solve_target()`; targeted execution is always
Debug and non-persistent in the current implementation, regardless of whether
`--debug` is explicitly supplied.

For `solve all`, `discover_puzzles()` scans `test_data/*.a2b`, validates the
`c{chapter}_{number}_{name}` shape and chapter range, resolves each file through
`PuzzleRepository`, and sorts by numeric `(chapter, puzzle number)`. It does not
trust lexicographic filename ordering.

`PuzzleStateRepository.load()` then determines eligibility:

- missing state or a state with no candidate: solve;
- `status: re-solve`: solve;
- `pending`, `accepted`, or `rejected`: skip.

The optional `reason` never controls eligibility.

### Chapter worker and search loop

`Manager._run()` groups eligible puzzle IDs by chapter. When a concurrency slot
is free, `_start_chapter_worker()` creates a duplex `multiprocessing.Pipe` and
one `multiprocessing.Process` running `_solver_worker()` for that chapter. The
Manager sends `_StartPuzzle(problem_id)`.

The worker creates one `SolverFramework`, starts a new `SolverSession` for the
puzzle, and calls `run_until_submission()`. The concrete synthesis algorithm
generates candidate text. The framework executes search trials with its own
chapter-bound `Executor` and feeds results back until a submission is ready.
The worker sends `_CandidateSubmitted` to Manager. In Debug mode that message
also carries the complete search feedback history for reporting.

### Independent full validation

Manager keeps the chapter worker alive and calls `_start_validation()`. This
creates a separate one-way pipe and a short-lived process running
`_validation_worker()` for that exact `Puzzle` and candidate. Consequently, a
large full validation does not block Manager's polling loop or unrelated active
chapters.

Before starting the validation worker, persistent `re-solve` runs reject a
submission identical to the currently authoritative candidate through
`_duplicate_replacement_result()`. The failure goes straight back to the same
Solver session.

The validation worker calls `validate_candidate()`, which creates its own
Executor and processes every input/output pair. Only failed trials are retained
in ordinary failure feedback; Debug mode additionally retains all trials and
their execution observations for reports.

On `FAIL`, Manager records a `validation_fail` report and sends
`_ValidationFailed(feedback)` to the chapter worker. `_solver_worker()` passes it
to the existing session, so the same algorithm instance advances to another
candidate.

On `ERROR`, Manager records diagnostics, sets a fatal summary, and cleans up all
workers. It does not continue other chapters after results become untrustworthy.

### Persistence and advancement

On `PASS`, a normal `solve all` run calls
`PuzzleStateRepository.persist_valid_candidate()`. It writes a temporary file,
flushes and `fsync`s it, then uses `os.replace()` for atomic replacement. The
saved state contains the candidate, local case and line counts, and
`status: pending`. A prior `re-solve` reason disappears with the replaced state.

Targeted runs use `persist=False`, so they can debug a puzzle—even one already
accepted—without changing its `.solve` file.

Manager sends `_ValidationPassed` to clear the worker's session, then starts the
next eligible puzzle in that same chapter. Only after the chapter's queue is
empty does `_stop_chapter_worker()` stop it. Manager finally reloads persistent
states, prints `RunSummary`, and explicitly separates local workflow completion
from real-game acceptance.

## Process, concurrency, and IPC model

The actual process topology for `--max-concurrency 2` can look like:

```text
main Manager process
├── chapter 1 Solver process ── temporarily paired with c1_* validation process
└── chapter 2 Solver process ── temporarily paired with c2_* validation process
```

Important details:

- `max_concurrency` limits active **chapter Solver processes**, not total OS
  processes. Each chapter may temporarily have a validation process as well.
- There is at most one active puzzle and at most one validation for a chapter.
- Puzzles within one chapter remain ordered and serial. Different chapters may
  progress concurrently.
- The default is `max_concurrency=1`.
- Manager uses `multiprocessing.get_context()` by default, so the OS/default
  start method applies. Tests explicitly use the `spawn` context to exercise
  pickling-safe worker boundaries.
- IPC uses `multiprocessing.Pipe`, never filesystem polling. Solver pipes are
  duplex because Manager sends start/pass/fail/stop commands and workers return
  submissions/errors. Validation pipes are one-way result channels.
- IPC messages are private dataclasses in `manager.py`: `_StartPuzzle`,
  `_ValidationPassed`, `_ValidationFailed`, `_StopWorker`,
  `_CandidateSubmitted`, `_SolverFailure`, and `_WorkerStopped`.
- `_ChapterRuntime` and `_ValidationRuntime` are Manager-side process/connection
  bookkeeping records, not domain models.
- The scheduling loop polls all active connections and sleeps for 10 ms only
  when no message or result progressed.
- Normal shutdown asks chapter workers to stop, joins briefly, and terminates a
  process that does not cooperate. Fatal and interrupted cleanup terminates
  remaining validation processes and prevents practical orphaning.

The `threading.Event` used by `request_stop()` belongs only to the Manager
process. Worker termination is coordinated over pipes and, if necessary,
`Process.terminate()`.

## Files and artifact flows

### Rules

`src.executor.DEFAULT_RULES_PATH` and
`src.solver_framework.DEFAULT_RULES_PATH` resolve to
`src/rules/a2b_rules.yaml`. The YAML describes syntax, chapter keyword
availability, limits, control flow, `(once)` behavior, cycle detection, and the
operation identifier. Executor supplies the Python implementation of that
operation.

The Rules file is normative and owner-protected. A developer may inspect it and
report a suspected mismatch, but must not “fix” it as an ordinary code change.
The natural-language file under `rules/` is reference material, not a fallback
runtime Rules source.

### Puzzle input (`.a2b`)

The JSON files include titles, localized descriptions, examples, and exhaustive
`input`/`output` arrays. `PuzzleRepository.resolve()` intentionally extracts
only `id`, `chapter`, `min_lines`, `input`, and `output`. It validates their
types, filename/ID agreement, and equal case counts, returning immutable tuples.

Neither runtime natural-language understanding nor the localized description
fields participate in synthesis or validation. The files are authoritative and
read-only; tests that need custom puzzles create temporary directories.

### Puzzle state (`.solve`)

A normal state has this shape:

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

Manager owns `candidate` and `local_validation` persistence after a pass and
sets `status: pending` for both a new candidate and a validated replacement.
The owner controls the subsequent decision statuses `accepted`, `rejected`,
and `re-solve`, plus the optional `reason` allowed only for `rejected` and
`re-solve`. `tools.review_candidates.update_owner_decision()` changes only
those owner-controlled fields and writes atomically.

Do not infer acceptance from passing tests, local validation, a committed file,
or a zero process exit code. Only owner action may create `accepted`.

### Reports

`DiagnosticReporter.start_run()` creates a UUID shared in the payload of every
report from one Manager run. `write()` creates filenames of the form:

```text
{problem_id}_{time_ns}_{short_uuid}.report.json
```

Possible events include `search_diagnostics`, `validation_pass`,
`validation_fail`, `validation_error`, `solver_error`,
`solver_process_error`, and `interrupted`. Release runs persist failures and
errors; Debug runs also persist successful search and validation traces.

Reports may contain candidates, case data, terminations, errors, timing, and
per-instruction observations. They are potentially large because the puzzle
datasets are exhaustive. They are disposable diagnostics and are not read by
the normal solver workflow.

### Runtime configuration

The CLI-exposed configuration is intentionally narrow:

- target: `all` or one full puzzle ID;
- `--max-concurrency`: positive active-chapter limit, default `1`;
- `--debug`: richer diagnostics for `solve all`.

Default puzzle, state, report, and Rules paths are module constants rooted at
the checkout. Tests and embedding code can override them through constructors.
`Executor.max_steps` defaults to 100,000 and is constructor-configurable but is
not exposed as a CLI flag. There is no environment-variable or application
configuration file loader.

## Tests and verification code

The test suite uses standard-library `unittest` and can be run after installing
[`requirements.txt`](../requirements.txt):

```bash
python -m unittest discover -s tests -v
```

Coverage is organized by responsibility:

- `tests/test_executor.py` verifies instruction matching and replacement,
  restart-from-line-one control flow, empty sides, all keywords and chapter
  restrictions, comments/whitespace, invalid programs, both length limits,
  repeated and growing nontermination, and Debug observation equivalence.
- `tests/test_solver.py` first uses dummy algorithms to verify puzzle
  resolution, proposal/feedback exchange, selected-case trials, error
  propagation, and Debug observations. Its six chapter tests then synthesize a
  candidate for every puzzle in `test_data/`, check the submission lifecycle,
  and enforce `min_lines`.
- `tests/test_manager.py` uses temporary puzzle/state/report directories and
  picklable test algorithms. It covers eligibility and persistence, retrying
  the same Solver after validation failure, replacement semantics, chapter
  concurrency, fail-fast behavior, graceful stop, targeted non-persistence,
  Debug reports, malformed state, validation limits/outcomes, a real Solver
  through Manager, and CLI wiring.
- `tests/test_review_candidates.py` verifies the owner review TUI, atomic
  decision updates, optional reasons, status summaries/order, navigation, and
  preservation of machine-managed fields.

The chapter synthesis tests are the main domain-level regression check: they
exercise the real puzzle corpus through the real Solver framework and Executor.
The committed `.solve` files are useful accepted artifacts, but are not a
replacement for rerunning these tests after implementation changes.

## Debugging guide

### Trace a single puzzle end to end

Use a targeted run:

```bash
python a2bautosolver.py solve c1_1_atob
```

It is always Debug and non-persistent. Start at `manager.main()`, follow
`Manager.solve_target()` into `_run()`, then inspect the paired
`search_diagnostics` and `validation_pass`/`validation_fail` files in
`reports/`. Their shared `run_id` links the events.

For a wrong transformation, inspect the search feedback and the corresponding
generator in `src/solver.py`. For an unexpected instruction result or
termination, reduce the candidate and input to a direct `Executor.execute()`
call and inspect `ExecutionResult.observations`. For unexpected eligibility or
persistence, inspect `PuzzleStateRepository.load()` and the relevant `.solve`
status before looking at Solver.

### Useful breakpoints and instrumentation points

- `Manager._run()` — scheduling, message routing, failure classification, and
  chapter advancement.
- `_solver_worker()` / `_validation_worker()` — process-boundary failures and
  serialization/pickling issues.
- `validate_candidate()` — line-count failures and the authoritative per-case
  decision.
- `SolverSession.run_until_submission()` — proposal/feedback sequence and
  session reuse after Manager rejection.
- `SolverFramework._trial_candidate()` — selected cases and Executor
  infrastructure escalation.
- `CandidateSynthesisAlgorithm.propose()` and `_generate_candidates()` —
  candidate order, exhaustion, deduplication, and `min_lines` filtering.
- `Executor._parse_program()` — invalid syntax and line-length errors.
- `Executor.execute()` / `_apply_instruction()` — control flow, state changes,
  keyword behavior, and nontermination.
- `DiagnosticReporter.write()` and `Manager._record_search()` /
  `_record_validation()` — report payload and report-volume issues.

Keep Debug observation gathering observational. It may collect more data and
perform additional checks, but must not change candidate selection or execution
semantics.

## Safe extension points

### Add or replace a solving strategy

Implement the `SolvingAlgorithm` protocol and an `AlgorithmFactory`. For an
experiment, inject the factory into `Manager(algorithm_factory=...)` or call
`SolverFramework.solve()` directly. For a permanent change, update
`create_solver_algorithm()` and/or the chapter dispatch in
`_generate_candidates()` while keeping serialized candidates and Executor
feedback as the boundary.

New generators should remain lazy, derive behavior from `Puzzle` data rather
than copy external solutions, respect `min_lines`, and use fresh auxiliary
symbols safely. Add a focused regression when introducing a reusable inference
helper, then run the full chapter synthesis tests affected by the change.

### Change search-time trial selection

Set `CandidateProposal.case_indices` to a unique, non-empty tuple of valid
zero-based indices. The framework validates it. This can reduce search cost,
but a submitted candidate will still receive Manager's full-dataset validation.
Do not weaken or bypass that final step.

### Add diagnostics

Extend immutable observation/result data at the producing layer and serialize
it in Manager. Keep exactly one persistence owner for an event. Avoid writing
reports from both a worker and Manager for the same information.

### Change persistence or review behavior

Machine-managed candidate state belongs in `PuzzleStateRepository`; owner
decisions belong in `tools/review_candidates.py`. Preserve atomic writes and
strict loading. A schema change affects committed state files and may cross a
normative specification boundary, so confirm authority before implementing it.

### Change A=B execution behavior

This is the highest-risk extension. Start by comparing
`src/rules/a2b_rules.yaml`, the natural-language source, Executor tests, and the
observed real-game behavior. A semantic correction may require an owner-approved
change to protected Rules before code can change. Keep all semantics in
Executor and add focused rule/limit/control-flow tests.

Any new third-party Python dependency requires explicit owner approval.

## Invariants future contributors must preserve

The component and workflow sections above define the ordinary responsibility
boundaries. The less obvious contribution guardrails worth keeping together are:

1. `test_data/*.a2b` is immutable authoritative input.
2. `src/rules/a2b_rules.yaml` is normative, protected content and cannot be
   edited as routine implementation cleanup.
3. Automated code may create `pending` after Manager validation but may not
   infer or create owner `accepted`, `rejected`, or `re-solve` decisions.
4. Targeted Debug execution must not overwrite authoritative `.solve` state.
5. Reports are diagnostics only; deleting or retaining them must not change
   puzzle behavior or status.
6. Candidate validity applies to the exact serialized program: raw line count
   and length, every intermediate operating-string length, termination, and
   all exhaustive I/O cases matter.
7. Candidate failure is recoverable feedback; infrastructure failure is
   fail-fast and invalidates continued results.
8. Passing local tests or validation never substitutes for owner real-game
   acceptance.

When a proposed change would alter requirements, protected Rules, architecture,
state ownership, or acceptance semantics, stop and obtain an owner decision.
Ordinary internal refactoring is safe only while these boundaries remain true.
