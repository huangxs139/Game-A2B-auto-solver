# Getting Started

This guide starts where the README leaves off: with a local checkout and a desire to run the tools. All commands below assume that your shell is in the repository root, the directory containing `a2bautosolver.py`.

## 1. Prepare the environment

The known-tested environment is Linux, particularly WSL2 with Miniconda3, running Python 3.14. The project does not claim a minimum Python version: other versions may work, but they have not been verified with a complete run. Use Python 3.14 when you want to match the documented environment. The project has one third-party dependency, pinned in `requirements.txt`: PyYAML 6.0.3. No GPU, external service, API key, or A=B game installation is needed for local solving and validation.

Check the interpreter that `python` selects:

```bash
python --version
```

Using an isolated environment is recommended. For example, with the standard library's `venv`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If you use Conda, activate your Python 3.14 environment first and then run the same `python -m pip install -r requirements.txt` command.

This repository is run directly from its checkout; it does not contain a package installer or a console-script entry point. Confirm that the CLI imports correctly and inspect its implemented options:

```bash
python a2bautosolver.py --help
python a2bautosolver.py solve --help
```

To verify the checkout after installing its dependency, you may run the full
automated test suite. This is broader and may take longer than a lightweight
installation check:

```bash
python -m unittest discover -s tests -v
```

## 2. Make the first invocation

Run the normal workflow:

```bash
python a2bautosolver.py solve all
```

The repository ships with a `.solve` file for every puzzle, and all of those files currently have `status: accepted`. Consequently, an unchanged checkout discovers 47 puzzles, reports that none require Solver work, skips all 47, and exits successfully. That is expected; it confirms that the Manager can discover the inputs and read the persisted state, but it does not rerun the Solver.

The final output distinguishes local workflow completion from acceptance in the original game. Process exit and local validation never create or imply real-game acceptance.

## 3. Actually solve puzzles

### Solve one puzzle without changing saved state

Use the full puzzle identifier—the `.a2b` filename without its extension:

```bash
python a2bautosolver.py solve c1_1_atob
```

Identifiers are case-sensitive. List the available names when needed:

```bash
find test_data -maxdepth 1 -name '*.a2b' -printf '%f\n' | sort
```

A targeted run has two important properties:

- It force-runs the named puzzle even if its saved status would normally cause a skip.
- It always enables detailed debug collection and never writes or replaces the puzzle's `.solve` file.

This makes targeted execution the safest way to exercise a solver or investigate a puzzle in an existing checkout. It still performs full-dataset validation before reporting `Validation PASS`, and it writes debug artifacts under `reports/`.

`--max-concurrency` has no practical effect for a single target, because only one chapter is active. Supplying `--debug` is also unnecessary for a target because targeted execution already enables it.

### Rerun the complete set

Normal `solve all` only schedules a puzzle when its `.solve` file is absent, has no candidate, or has `status: re-solve`. The committed states express the upstream project owner's decisions and make an unchanged checkout skip the complete set. Remove them to start your own run with every puzzle unsolved; the replacement states generated afterward belong to your local review workflow.

If you want a convenient copy of the upstream results, back them up first:

```bash
cp -a test_output /tmp/a2b-test-output-accepted
rm -- test_output/*.solve
python a2bautosolver.py solve all
```

The deletion affects tracked files only in your working copy. To discard your generated states and restore the upstream versions later, use:

```bash
git restore test_output
```

During a full run, puzzles remain ordered within each chapter. The Manager starts chapter Solver processes, receives candidates, validates each submitted program independently against every supplied input/output case through the Executor, and writes a successful result to `test_output/<problem_id>.solve` with `status: pending`.

### Use chapter concurrency

The default is one active chapter Solver at a time. Increase it with:

```bash
python a2bautosolver.py solve all --max-concurrency 3
```

The value must be a positive integer. It limits simultaneously active chapter Solvers, not the total number of operating-system processes: validation runs in separate worker processes too. At most six chapters can provide useful chapter-level parallelism. Higher concurrency can reduce elapsed time but increases concurrent CPU and memory use.

### Enable full-run diagnostics

For a diagnostic `solve all` run:

```bash
python a2bautosolver.py solve all --debug
```

Debug mode records search feedback, every debugged Executor trial, and full-validation observations. Since individual puzzles can contain thousands of cases, these JSON reports can be very large. Prefer a targeted run when investigating one puzzle.

## 4. Understand the files involved

The CLI has no user configuration file and no environment-variable configuration. Its runtime locations are fixed by the code relative to the repository:

| Path | Role | Runtime treatment |
| --- | --- | --- |
| `test_data/*.a2b` | The 47 authoritative puzzle definitions and exhaustive input/output cases | Read-only; do not edit to influence a result |
| `src/rules/a2b_rules.yaml` | Machine-readable A=B syntax, chapter capabilities, semantics, and limits | Read-only normative runtime input |
| `test_output/*.solve` | Candidate program, local-validation facts, and owner decision for each puzzle | Read by normal runs; atomically written after a full local pass |
| `reports/*.report.json` | Raw search, validation, error, or interruption diagnostics | Non-authoritative diagnostic artifacts; not used to decide eligibility |

Puzzle names follow `c<chapter>_<number>_<short-name>`, for example `c1_1_atob`. Each `.a2b` file is JSON; the runtime-relevant fields include `id`, `chapter`, `min_lines`, `input`, and `output`.

A generated `.solve` file is also JSON. Its key fields are:

- `candidate`: the native, serialized A=B program;
- `local_validation`: whether it passed locally, plus case and line counts;
- `status`: the workflow state, initialized to `pending` by Manager and later
  changed to `accepted`, `rejected`, or `re-solve` only by the owner;
- `reason`: optional owner metadata for `rejected` or `re-solve`.

The four valid statuses behave as follows:

| Status | Meaning | Scheduled by `solve all`? |
| --- | --- | --- |
| `pending` | Locally valid candidate awaits manual owner review | No |
| `accepted` | Owner accepted it in the real A=B game | No |
| `rejected` | Owner rejected it without requesting another solve | No |
| `re-solve` | Owner explicitly requests a replacement | Yes |

If a replacement passes full local validation, the Manager replaces the old candidate, changes the status to `pending`, and removes any old reason. Until then, the previous candidate and decision remain in the state file. A replacement identical to the current `re-solve` candidate is rejected by the Manager and returned to the active Solver as feedback.

## 5. Review a candidate and record the real-game result

Start the line-oriented review tool with:

```bash
python tools/review_candidates.py
```

It reads the repository's `test_output/` directory by default. To review a separate copy of the states, use its only option:

```bash
python tools/review_candidates.py --state-directory /path/to/copied-states
```

The tool opens directly with a status summary and a puzzle-coordinate prompt. Press Enter to select the displayed default, enter a coordinate such as `1-5` (an underscore also works), or enter `q` to quit. The default is the first pending candidate; when none are pending, it is the first accepted candidate. This makes all 47 accepted programs in the committed checkout directly viewable.

After you select a puzzle, the tool shows its current status, any recorded reason, and its copyable native A=B program. Press Enter at the result prompt to keep the current status unchanged, or record one of these owner decisions after testing the program in the original game:

- `accepted` — real-game testing succeeded;
- `rejected` — it failed and should remain skipped;
- `re-solve` — it failed and should be eligible on the next `solve all` run.

For `rejected` and `re-solve`, the tool optionally records a reason. It updates only the owner-controlled decision fields and writes the state atomically, then returns to the summary and coordinate prompt.

Do not mark a candidate `accepted` merely because local validation passed. Local validation means that the exact candidate obeyed the implemented limits and produced the expected output for every supplied case through this project's Executor. Only successful manual entry into the original game justifies `accepted`.

## 6. Read progress, results, and reports

Release output is intentionally short. Typical messages announce candidate submission and `Validation PASS` or `Validation FAIL`, followed by a summary containing:

- discovered, eligible, and skipped puzzle counts;
- candidates locally validated during this run;
- full-validation failures returned to Solvers;
- persisted pending, accepted, and rejected counts for `solve all`;
- whether the run finished, was interrupted, or failed.

A validation failure is not automatically fatal: its failed-case feedback goes back to the still-running Solver so it can try another candidate. Infrastructure problems—such as malformed Rules, corrupt puzzle/state JSON, Executor errors, or an unhandled Solver failure—are fail-fast because later results would not be trustworthy.

Report filenames contain the puzzle identifier, a timestamp-like nanosecond value, and a short random suffix. Reports from the same Manager invocation share a `run_id` inside the JSON. Depending on the event and mode, `event` may identify search diagnostics, validation pass/failure/error, Solver/process error, or interruption.

Successful non-debug runs do not write routine pass reports. Failures and errors are recorded when available; debug runs additionally persist detailed successful search and validation data. Reports are diagnostics only: deleting or retaining them does not change which puzzles the Manager schedules.

## 7. Stop and resume safely

Press `Ctrl-C` to request a graceful stop. The CLI also handles `SIGTERM` the same way. The Manager stops active work at its next safe loop point, cleans up its Solver and validation processes, writes interruption reports for active puzzles when possible, prints a final summary, and exits with status 130.

Candidates that completed full validation before the stop remain safely persisted because `.solve` writes are atomic. Run the same command again to continue the overall workflow; `solve all` skips those persisted candidates and starts the still-eligible puzzles again.

The Solver does not checkpoint its internal search. An interrupted puzzle restarts its search from the beginning, and targeted runs cannot be resumed from persisted state because they deliberately write no candidate state.

## 8. Common operational issues

### `ModuleNotFoundError: No module named 'yaml'`

The active interpreter does not have the pinned dependency. Activate the intended environment and run:

```bash
python -m pip install -r requirements.txt
```

Using `python -m pip` ensures that installation targets the same interpreter used to launch the solver.

### `solve all` says zero puzzles require work

This is the expected first-invocation behavior described in Section 2. Use a targeted command for a non-persistent rerun, follow “Rerun the complete set” for a clean local run, or mark selected local candidates `re-solve` after reviewing them.

### A target is rejected or cannot be found

Pass the exact case-sensitive filename stem from `test_data/`, not a coordinate such as `1-1` and not a path or `.a2b` filename. For example, Chapter 3 puzzle 1 is `c3_1_Remove`, with an uppercase `R`.

### The run fails while reading a `.solve` file

Normal execution performs strict structural checks on persisted state and stops on malformed JSON, a mismatched identifier, an invalid status/reason combination, missing local-validation data, or invalid metadata types and values. Loading a state does not re-execute its candidate or compare the stored case and line counts with the puzzle. Restore a malformed file from version control or a known-good backup. Use the review tool, rather than hand-editing JSON, for normal status changes.

### Debug reports consume substantial disk space

Debug captures step-by-step execution observations for all trialed cases. Use targeted execution where possible and archive or remove unneeded files under `reports/`; they are not authoritative state. Be aware that this repository does not currently ignore `reports/` in Git, so check `git status` before committing.

### The Solver appears stuck

There is no performance deadline, and a valid search may run for a long time. Retry the exact puzzle as a targeted run to collect diagnostics. If necessary, interrupt gracefully; the unresolved puzzle will restart rather than resume its internal search.

### Exit status interpretation

- `0`: the requested local workflow ended normally, even if no puzzle needed work;
- `1`: a fatal Manager/runtime error occurred;
- `130`: the run was interrupted gracefully;
- `2`: command-line parsing rejected the invocation.

None of these statuses means that the original game accepted a candidate.
