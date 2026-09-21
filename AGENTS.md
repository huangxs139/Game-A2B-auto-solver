# A2B Auto Solver — Project Instructions

## 1. Scope and Authority

This file defines repository-specific instructions for the A2B Auto Solver project.

The global `~/.codex/AGENTS.md` remains applicable. This file supplements it and does not relax its authority, approval, testing, Git, scope, or acceptance rules.

The repository is the authoritative project source of truth.

## 2. Authoritative Project Documents

Before substantive development, Codex must read the project documents relevant to the assigned work:

* `REQUIREMENTS.md` — required behavior, constraints, validation, and project completion criteria;
* `ARCHITECTURE.md` — component responsibilities and architectural boundaries;
* `ROADMAP.md` — feature order, dependencies, and owner-controlled status;
* `features/FEATxxxx.md` — direct scope, verification, and acceptance boundary for the assigned Feature.

For Rules-related work, Codex must also read the official A=B rule documentation identified by the project.

Codex must not use chat history, model memory, prior sessions, or temporary notes as substitutes for current repository specifications.

If authoritative documents materially conflict or are insufficient to continue correctly, Codex must stop the affected work and request an owner decision.

## 3. Project Work Model

The planned Development Units are `FEAT0001` through `FEAT0006`, as defined by `ROADMAP.md`.

A Feature may begin substantive implementation only when its owner-controlled status permits development and its required dependencies have been accepted.

Implementation must remain within the assigned Feature specification and the higher-level requirements and architecture.

Feature acceptance, puzzle acceptance, and project completion are distinct. Only the owner may issue an `ACCEPTED` decision or record successful real-game puzzle acceptance.

## 4. Protected Project Content

The following project content has special authority boundaries.

### Machine-Readable Rules

The machine-readable A=B Rules are normative project specification.

Codex may create them when explicitly authorized by `FEAT0001`.

After owner acceptance, Codex may inspect the Rules, use them, test against them, identify suspected defects, and propose corrections, but must not modify them without explicit owner authorization.

A suspected Rules defect is a specification issue, not permission to repair the Rules autonomously.

### Puzzle Inputs

Files under `test_data/` are authoritative project inputs.

`.a2b` puzzle data must be treated as immutable and read-only during normal development and runtime operation.

Codex must not alter puzzle data to make implementation or Solver behavior pass.

### Puzzle State

`.solve` files contain both machine-managed state and owner-controlled decisions.

Implementation may create or update machine-managed fields only as permitted by the specified Manager/validation workflow.

Owner-controlled acceptance, rejection, and re-solving decisions must not be created, changed, inferred, or marked complete by Codex or runtime components without explicit owner action.

### Reports

Files under `reports/` are diagnostic artifacts, not authoritative puzzle state or normative specification.

They may be created and updated according to the documented diagnostic workflow.

## 5. Architectural Boundaries

Codex must preserve the architecture defined in `ARCHITECTURE.md`, in particular:

* Manager owns global orchestration and authoritative full local validation workflow;
* Solver owns solving algorithms;
* Executor is the sole implementation of A=B execution semantics;
* full validation uses Executor and is not required to be an independent architectural subsystem;
* Rules contain A=B semantics, not Solver-specific search knowledge.

Implementation structure may vary within these boundaries unless a Feature specification constrains it further.

## 6. Verification

Codex must follow the global three-layer verification model together with the project-specific verification requirements in `REQUIREMENTS.md` and the active Feature specification.

Domain-level exhaustive puzzle validation may serve as primary verification where the project specifications explicitly permit it. Conventional tests must still be implemented and run where the active Feature requires them or where they provide applicable low-cost regression protection.

Passing local validation does not constitute real-game puzzle acceptance.

Before owner review, Codex must complete applicable Layer 1 verification and mandatory self-review and report unresolved limitations accurately.

## 7. Dependencies

Any new third-party Python dependency requires explicit owner approval before introduction.

Codex may evaluate or propose dependencies without installing or adding them to the project before approval.

## 8. Operating Principle

Use the current Feature specification as the immediate implementation scope, `REQUIREMENTS.md` and `ARCHITECTURE.md` as its governing constraints, and `ROADMAP.md` as the project sequencing and status authority.

Make ordinary engineering decisions independently inside those boundaries.

When correct continuation would require changing normative content, project scope, architecture, acceptance criteria, protected Rules, authoritative puzzle data, or another owner-reserved decision, stop and ask the owner.

## 9. Temporary Test Execution

Short, simple, foreground-only diagnostic commands may be executed inline.

Temporary tests or diagnostic programs that are long-running, multi-step, non-trivial, or intended to run in the background must not be embedded directly as large inline shell commands.

Such tests must instead be written to a temporary script or other appropriate temporary file so that the executed logic is inspectable, reproducible, and can be safely restarted or terminated.

Temporary diagnostic artifacts must not be committed unless explicitly authorized or intentionally promoted into the project's permanent test suite.
