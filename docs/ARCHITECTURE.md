# A2B Auto Solver — Architecture

## 1. Core Components

The runtime architecture contains three primary components:

* `Manager`: global orchestration, process lifecycle, and authoritative full-dataset validation workflow.
* `Solver`: puzzle-solving algorithms.
* `Executor`: the unique implementation of A=B execution semantics.

The architecture must keep these responsibilities separate.

Full-dataset validation is a Manager-owned workflow step that uses Executor. It may be implemented as a helper, wrapper, worker operation, or other internal structure, but is not a separate primary architectural component.

---

## 2. Manager

Manager owns global runtime control flow.

Responsibilities:

* discover puzzles from `test_data/`;
* preserve chapter and puzzle ordering;
* launch and manage Solver processes;
* schedule validation work;
* enforce maximum chapter concurrency;
* coordinate IPC;
* handle graceful stop;
* propagate fatal errors using fail-fast behavior;
* receive final Solver candidates;
* persist `.solve` files after successful full validation.

Manager must not contain:

* solving algorithms;
* puzzle-specific search logic;
* A=B instruction semantics.

A puzzle may be dispatched to Solver using only its identifier:

```text
c{x}_{y}_{zzz}
```

where `x` is chapter, `y` is puzzle number, and `zzz` is the short name.

---

## 3. Solver

Solver is an independent puzzle-solving component.

Its task is:

```text
problem_id -> candidate A=B program
```

Solver may derive from `problem_id`:

* chapter;
* puzzle number;
* short name;
* corresponding `.a2b` file;
* applicable Rules;
* `min_lines`;
* input/output cases.

Natural-language puzzle descriptions are not required for solving.

Different chapters may load different Solver implementations. Solver implementations may share helper code but are not required to share algorithms.

During search, Solver may directly and repeatedly call Executor using selected cases. It may use partial validation, execution observations, traces, or other feedback according to its algorithm.

When Solver believes it has found a viable candidate, it submits the final serialized A=B code to Manager.

Solver self-acceptance is not authoritative validation.

If full validation fails, the same active Solver receives the failed cases and continues solving the same puzzle.

The chapter does not advance until the current puzzle passes full validation.

---

## 4. Executor

Executor is the only implementation of A=B program execution semantics.

No other component may independently implement A=B execution behavior.

Conceptual interface:

```text
execute(input, code_snippet) -> ExecutionResult
```

Rules are an internal runtime dependency of Executor and need not be passed on every call.

Executor implements the A=B control flow:

1. scan instructions from the first line;
2. execute the first currently executable instruction;
3. after execution, restart scanning from the first line;
4. terminate when a complete scan finds no executable instruction.

Executor maps structured operation identifiers from Rules to Python implementations.

`ExecutionResult` must support at least:

* final output;
* normal/abnormal termination;
* loop detection;
* execution errors.

Executor must also support optional execution observations needed by Solver or Debug tooling.

Tracing or instrumentation must not alter execution semantics.

Executor should avoid external side effects and must not modify:

* Rules;
* puzzle inputs;
* `.solve` files;
* unrelated Solver state;
* unrelated filesystem state.

Executor is responsible for detecting invalid nonterminating execution.

---

## 5. Full Local Validation

Authoritative full local validation is a Manager-owned workflow step that uses Executor.

It contains no independent A=B execution semantics and is not required to exist as a separate architectural subsystem.

Its implementation may take the form of a helper, wrapper, worker operation, or other suitable internal structure.

Conceptually, full validation runs the final serialized candidate against every input/output pair in the puzzle and checks:

* full output correctness;
* valid termination;
* absence of execution errors;
* `min_lines`;
* compliance with the program-line length limit;
* no operating-string state exceeding its length limit.

Validation outcomes:

### PASS

All cases pass and all applicable line-count and length limits are satisfied.

Manager may create/update the corresponding `.solve`.

### FAIL

The candidate is invalid but execution infrastructure remains trustworthy.

The full-validation workflow returns all failed cases to the active Solver, including useful structured information such as:

* input;
* expected output;
* actual output;
* termination information where relevant.

Solver continues solving.

### ERROR

A project-level failure prevents trustworthy validation.

Examples include Executor failure, invalid Rules, corrupted puzzle data, validation-workflow failure, or process failure.

ERROR propagates through Manager and triggers fail-fast behavior.

---

## 6. Puzzle Lifecycle

```text
Manager
  -> start Solver for puzzle
Solver
  -> search
  -> repeatedly call Executor as needed
  -> submit candidate
Manager
  -> dispatch Manager-owned full validation using Executor
  -> FAIL: return failed cases to same Solver
  -> ERROR: trigger fail-fast handling
  -> PASS: persist .solve
  -> release current puzzle Solver
  -> advance chapter to next puzzle
```

A Solver must remain available while its candidate is undergoing full validation because a failed candidate is immediately returned for continued solving.

---

## 7. Process Model

Each active chapter normally runs in an independent Solver process.

Chapter-level process isolation matches the requirement that chapter solving contexts are logically independent.

A chapter Solver may optionally create puzzle-specific child processes if its algorithm benefits from stronger isolation or independent state.

Validation work must run independently of Manager's synchronous control path so one slow validation does not block unrelated chapters.

Solver processes and validation workers may each instantiate Executor.

"Executor is unique" means one execution implementation in the codebase, not one global Executor instance.

Manager owns the Solver and validation process trees it starts and is responsible for:

* startup;
* graceful stop;
* abnormal termination handling;
* exit-status collection;
* preventing orphaned child processes where practical.

---

## 8. Concurrency

Manager uses a simple chapter-level resource pool:

```text
max_concurrency = N
```

When capacity exists, another chapter Solver may start.

`N = 1` naturally produces serial execution.

The initial architecture does not require dynamic CPU, memory, GPU, or CUDA-aware scheduling.

Only one authoritative Solver owns a given puzzle at a time.

---

## 9. IPC

Manager, Solver processes, and validation workers communicate using local process IPC.

Preferred mechanisms are standard Python process communication primitives such as multiprocessing queues or pipes.

The filesystem must not be used as the normal runtime message queue.

---

## 10. Rules

Rules are the single machine-readable runtime specification of the A=B instruction set required by the six known chapters.

Rules are distinct from:

* official natural-language documentation;
* Executor implementation;
* Solver algorithms.

The repository contains official rule excerpts in Markdown.

Initial development flow:

1. Codex reads project documentation.
2. Codex reads the official rule Markdown.
3. Codex creates the machine-readable Rules file.
4. Owner reviews and accepts Rules.
5. Downstream implementation proceeds according to `ROADMAP.md`.

There is no runtime natural-language parser.

All six chapters use one Rules file. Each instruction declares the chapters in which it is available.

Rules should structurally describe information such as:

* instruction identity;
* syntax;
* parameters;
* semantic operation identifier;
* available chapters.

Rules do not need to form a complete executable DSL.

Executor owns the Python implementation of semantic operations.

Solver may read Rules to discover the instruction set and structured rule information required by its algorithm.

Rules must not contain human-style solving guidance merely to make them easier for Solver to "understand."

### Rules Permissions

Rules are normative project specification.

Codex may inspect Rules, identify suspected errors, and propose corrections.

Codex must not modify Rules without explicit owner authorization.

The project-level `AGENTS.md` must explicitly classify Rules as protected normative content.

---

## 11. Puzzle Input

Authoritative puzzle files live in:

```text
test_data/
```

Filename format:

```text
c{x}_{y}_{zzz}.a2b
```

The `.a2b` contents are JSON.

Puzzle files contain the structured data needed for solving and validation, including `min_lines`, inputs, and outputs.

`.a2b` files are authoritative and runtime-read-only.

---

## 12. Solution Output

Validated candidate solutions live in:

```text
test_output/
```

A solution uses the same basename as its input:

```text
test_data/c{x}_{y}_{zzz}.a2b
test_output/c{x}_{y}_{zzz}.solve
```

`.solve` contents are JSON.

A `.solve` file is created only after a candidate passes Manager-owned full-validation.

No empty placeholder `.solve` files are created.

Manager owns authoritative `.solve` persistence.

Manager determines normal Solver eligibility from persisted puzzle status according to `REQUIREMENTS.md`.

When a newly produced candidate passes authoritative full validation, Manager persists it as the current candidate with `status: pending`. This includes successful replacement of a candidate previously marked `re-solve`.

When processing `re-solve`, the existing candidate and persisted owner decision remain authoritative until the replacement candidate passes authoritative full validation.

A superseded failed candidate may be replaced by the newly validated candidate. Separate failed-candidate history is not required.

---

## 13. Reports

Diagnostic artifacts live in:

```text
reports/
```

Report filenames reuse the puzzle identifier and add a unique ordered run/event marker:

```text
c{x}_{y}_{zzz}_{run-id}.report.*
```

The exact marker format is implementation-defined. Timestamp, sequence, hash, or another simple mechanism is acceptable if repeated reports do not overwrite one another and their order can be determined where needed.

A component may either write its own diagnostic report or send the diagnostic data to Manager for persistence.

Each diagnostic event must have exactly one persistence owner. Duplicate copies of the same report must not be created by multiple components.

Reports are diagnostic artifacts, not authoritative puzzle state.

---

## 14. Error and Stop Handling

Normal candidate failure is not a runtime error. Failed cases return to Solver.

Infrastructure or implementation failures propagate to Manager and follow fail-fast behavior.

Manager coordinates graceful termination of active Solver and validation processes.

Graceful stop should preserve useful diagnostics.

Exact search-state resume is not required.

---

## 15. Optional Learned State

The base architecture does not assume machine learning or persistent learned state.

Do not introduce ML-specific infrastructure unless a selected Solver algorithm actually requires it.

If persistent learned state is later required, it belongs to Solver and must follow the existing requirements for:

* chapter isolation;
* versioned non-overwriting persistence;
* optional Git versioning.

---

## 16. Existing Simulator Migration

Historical simulator code may be reused as behavioral and implementation reference.

Its responsibilities should conceptually migrate as follows:

```text
global A=B execution loop
    -> Executor

instruction execution functions
    -> Executor semantic operations

chapter instruction availability
    -> Rules

full expected-output comparison
    -> Manager-owned full-validation workflow using Executor
```

Legacy simulator APIs do not require compatibility preservation.

---

## 17. Architectural Invariants

1. Manager owns global control flow.
2. Solver owns solving algorithms.
3. Executor is the sole A=B execution implementation.
4. Manager owns the authoritative full local validation workflow, which uses Executor.
5. Full validation is not required to exist as a separate architectural subsystem.
6. Solver may call Executor directly during search.
7. Failed full validation returns failed cases to the same Solver.
8. A chapter advances only after the current puzzle passes full validation.
9. Chapters may execute concurrently.
10. Concurrency is controlled by a simple maximum chapter count.
11. Runtime coordination uses IPC rather than filesystem messaging.
12. `.a2b` files are authoritative read-only inputs.
13. `.solve` files are lazy-created validated outputs.
14. Reports are diagnostics, not puzzle state.
15. One Rules file covers all six chapters.
16. Rules are normative and owner-protected.
17. ML infrastructure is introduced only if an actual Solver requires it.

---

## 18. Deferred Decisions

The architecture intentionally does not yet define:

* exact Rules schema;
* exact Executor result schemas;
* exact IPC message schema;
* exact Python multiprocessing primitives;
* exact Solver class/protocol design;
* exact tracing implementation;
* exact cycle-detection implementation;
* exact default concurrency count;
* exact report run-ID format;
* exact `.solve` JSON schema;
* exact Python package layout;
* exact Solver algorithms;
* exact chapter-specific Solver implementations;
* ML implementation details.
