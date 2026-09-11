# A2B Auto Solver — Roadmap

## 1. Purpose

This roadmap defines the planned implementation sequence for the A2B Auto Solver.

Feature specifications are stored under `features/`.

Feature acceptance represents completion of the corresponding implementation scope. It must not be confused with final project completion.

---

## 2. Milestones and Features

### M1 — Rules

Establish the machine-readable A=B Rules required by all later runtime components.

* `FEAT0001` — Formalize A=B Rules

**Exit condition:** FEAT0001 accepted by owner.

---

### M2 — Executor

Establish the shared implementation of A=B execution semantics.

* `FEAT0002` — Implement A=B Executor

**Dependency:** M1

**Exit condition:** FEAT0002 accepted by owner.

---

### M3 — Solver

Establish the common Solver execution framework and actual solving capability for all six chapters.

* `FEAT0003` — Implement Solver Framework
* `FEAT0004` — Solver Algorithms — Chapters 1–3
* `FEAT0005` — Solver Algorithms — Chapters 4–6

**Dependency:** M2

Planned order:

```text
FEAT0003 -> FEAT0004 -> FEAT0005
```

**Exit condition:** FEAT0003–FEAT0005 accepted by owner.

---

### M4 — Manager

Integrate the implemented components into the complete runtime workflow.

* `FEAT0006` — Implement Manager Workflow

**Dependency:** M3

**Exit condition:** FEAT0006 accepted by owner.

FEAT0006 acceptance demonstrates that the Manager-driven end-to-end workflow functions correctly. It does not require the complete project problem set to have reached final solving completion.

---

## 3. Planned Feature Sequence

```text
FEAT0001  Formalize A=B Rules
  |
  v
FEAT0002  Implement A=B Executor
  |
  v
FEAT0003  Implement Solver Framework
  |
  v
FEAT0004  Solver Algorithms — Chapters 1–3
  |
  v
FEAT0005  Solver Algorithms — Chapters 4–6
  |
  v
FEAT0006  Implement Manager Workflow
```

The sequence defines the initial implementation plan. Later work may revisit an accepted feature when integrated testing identifies a defect or required improvement.

---

## 4. Post-Feature Integrated Solving Phase

Acceptance of FEAT0001–FEAT0006 completes the planned initial implementation features, but does not by itself complete the project.

After all planned features are accepted, the owner performs integrated runtime testing of the complete tool.

During this phase:

1. the owner runs the tool;
2. unsolved puzzles, incorrect behavior, defects, or other problems are reported to Codex;
3. Codex diagnoses and modifies the relevant implementation;
4. applicable verification and owner review are repeated;
5. the cycle continues until the project completion criteria in `REQUIREMENTS.md` are satisfied.

This phase may include improvements to previously accepted Solver algorithms or fixes to other components discovered only during real integrated solving.

Final project completion remains:

> Every puzzle in the closed problem set has been accepted by the owner through real-game validation.

---

## 5. Status

Feature status is owner-controlled.

Suggested lifecycle:

```text
PLANNED -> READY -> IN_PROGRESS -> REVIEW -> ACCEPTED
```

Only the owner may mark a feature `ACCEPTED`.

Current working status:

| Feature | Status  |
| ------- | ------- |
| FEAT0001   | READY |
| FEAT0002   | PLANNED |
| FEAT0003   | PLANNED |
| FEAT0004   | PLANNED |
| FEAT0005   | PLANNED |
| FEAT0006   | PLANNED |
