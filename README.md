# A=B Auto Solver

English | [简体中文](README.zh-CN.md)

This repository is an automatic solver for the [**A=B**](#acknowledgements) game's complete six-chapter, 47-puzzle set. It generates real A=B programs for every puzzle, and all 47 included solutions have passed both exhaustive local validation and the original game.

## Why does this exist?

Is my aging brain still smart enough to finish A=B? Apparently not.

Four years later and I still hadn't cleared the whole game? Yeah, that was driving me nuts.

So what does a programmer do? Build a perfectly legal cheat and call it a **puzzle solver**. Obviously.

And since we live in 2026, why stop there? I didn't even want to write the solving algorithms myself.

Thanks, Codex. This is your problem now.

## What are you here for?

### “I just want the answers.”

Fair. That's why this project exists in the first place.

Open [`user_docs/Verified-Answers.md`](user_docs/Verified-Answers.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Verified-Answers)). It collects all 47 accepted A=B code answers. (Notice 5-5 might take ~15 mins to run. Go grab a coffee and **DON'T POKE IT!**)

### “I want to make the Solver suffer through a puzzle myself.”

Excellent. You can wipe the included solution states and make it solve all 47 puzzles again. Start with [Want to run it yourself?](#want-to-run-it-yourself), then see [`user_docs/Getting-Started.md`](user_docs/Getting-Started.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Getting-Started)) for the complete guide.

### “I actually want to know how it works.”

Unlike this README, [`user_docs/Solving-Algorithms.md`](user_docs/Solving-Algorithms.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Solving-Alogirthm)) takes itself seriously. It starts with the search problem behind A=B, follows the Solver's toolbox as the six chapters grow more complicated, walks through representative puzzles step by step, and maps all 47 puzzles to the strategies that solve them. Read it if you want to understand not just *what* answers were produced, but *why those programs work*.

### “I want to read the code.”

Planning to modify, extend, audit, or borrow from the implementation? [`user_docs/Codebase-Guide.md`](user_docs/Codebase-Guide.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Codebase-Guide)) is the developer's map: where each responsibility lives, how a command flows through Manager, Solver, and Executor, how processes and data communicate, where Rules and persisted state fit, and how the test suite is organized.

### “I found a bug.”

Please [open an issue](../../issues). Reproducible evidence is appreciated; psychic debugging remains outside the current feature set.

### “I have something else to say.”

Feel free to [contact me](#contact) for anything!

## What does it actually do?

This is not a table of hard-coded answers.

For each puzzle, the Solver examines the supplied input/output pairs, recognizes the kind of transformation involved, and builds candidate A=B programs from chapter-specific strategies and templates. Every candidate is executed using the same machine-readable game rules and must produce the expected output for every supplied case. The Manager then independently validates the final candidate before it can be saved.

In less dignified terms:

1. Look at the puzzle.
2. Try an A=B program.
3. Let the Executor say “nope.”
4. Try something better.
5. Repeat until all cases pass.
6. Save the program and test it in the real game.

The result is native A=B code—not a Python substitute for the answer.

The Solver is deliberately built for the closed set of 47 puzzles in the game's six known chapters. It is a data-driven, template-based synthesizer, not a general-purpose solver for arbitrary future A=B puzzles.

## Want to run it yourself?

The project was developed and tested as a Linux command-line application on Python 3.14. Windows users can obtain the same kind of environment through WSL2 or a Linux virtual machine.

The committed `.solve` files record the upstream project owner's accepted results, so Manager correctly skips them. For your own clean solving run, those decisions are reference artifacts rather than decisions you need to preserve: remove the files so every puzzle starts unsolved. The new `.solve` files generated afterward become your local candidates and await your own review.

Run the following from your local checkout:

```bash
cd <path-to-your-cloned-repository-root>/   # Enter the repository root; its directory name does not matter.
python -m pip install -r requirements.txt
rm -- test_output/*.solve                   # Remove existing accepted candidates, otherwise Solver will skip solving.

# To solve the complete six-chapter, 47-puzzle set automatically.
python a2bautosolver.py solve all

# To solve one puzzle in targeted Debug mode, pass its full identifier after 'solve'.
# Find identifiers in test_data/; they follow c{chapter_id}_{puzzle_id}_{puzzle_name}.
python a2bautosolver.py solve c1_1_atob     # Force-run puzzle c1_1_atob in non-persistent targeted mode.
```

For concurrency, Debug behavior, report sizes, tests, input/output formats, and the owner review workflow, see [user_docs/Getting-Started.md](user_docs/Getting-Started.md).

## How does it solve A=B?

The short version: not with one magical universal algorithm.

The Solver uses a growing toolbox of transformation recognizers and A=B program templates. Early chapters can often be handled with direct replacements, mappings, sorting rewrites, or counting patterns. Later chapters need markers, transducer-like passes, auxiliary symbols, bounded search, binary arithmetic through intermediate representations, and puzzle-specific constructions.

Candidates are generated from puzzle data, deduplicated, filtered by the puzzle's line limit, executed against the complete supplied dataset, and independently validated before persistence.

The long—and much more interesting—version belongs in [`user_docs/Solving-Algorithms.md`](user_docs/Solving-Algorithms.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Solving-Algorithms))

## Built with AI, on purpose

There is a second experiment hiding inside this one: the project was also a test of an AI-assisted software-engineering workflow from requirements to final review.

- **I** owned the project, made the requirements and architecture decisions, reviewed every feature, tested the candidates in the real A=B game, and made every final acceptance decision.
- **ChatGPT** helped discuss and refine the requirements, architecture, development plan, and documentation.
- **Codex** implemented the Rules, Executor, Solver, Manager, tests, and fixes; ran first-level testing and review; and reported the evidence for owner review.

The point was not merely to ask AI for a pile of code. The project used written requirements, protected specifications, feature boundaries, testing, review, and owner-controlled acceptance throughout the development process.

The same requirements, architecture, roadmap, feature specifications, project instructions, and machine-readable Rules used to guide Codex are included in the repository. If you want the Solver to behave differently, support your own experiments, or simply see whether the workflow survives contact with your ideas, you can fork the project and continue from those files instead of starting from an empty prompt. The [MIT License](LICENSE) permits modification and redistribution under its terms.

## Project status

**Complete for the included problem set.**

- 6 chapters
- 47 puzzles
- 47 committed solution states
- 47 owner-accepted solutions after real-game validation
- 126,626 supplied input/output cases passed in the final full local revalidation
- 48 automated tests passing at the documentation baseline

Puzzle inputs live in [`test_data/`](test_data/). Copy-friendly accepted programs live in [`user_docs/Verified-Answers.md`](user_docs/Verified-Answers.md)([**Read in Wiki**](https://github.com/huangxs139/Game-A2B-auto-solver/wiki/Verified-Answers)); their persisted Solver state and validation metadata remain in [`test_output/`](test_output/).

Local validation and real-game acceptance are intentionally separate: the program can prove that a candidate matches every supplied case, but only the project owner can confirm that it is accepted by the original game.

## Issues

For reproducible bugs, incorrect behavior, or documentation problems, please [open an issue](../../issues).

## Contact

- **Personal:** [huangxs139@gmail.com](mailto:huangxs139@gmail.com)
- **Work:** [stevenwong.work.275@gmail.com](mailto:stevenwong.work.275@gmail.com)
- **Business Contact:** [business-contact@megazero.cn](mailto:business-contact@megazero.cn)

## Acknowledgements

**A=B** is a programming puzzle game by Artless Games with only one instruction: `A=B`, meaning “replace A with B.” That tiny language has to solve problems ranging from uppercasing letters to multiplying binary numbers—preferably in as few lines as possible.

You can find the original game on its [official Steam store page](https://store.steampowered.com/app/1720850/AB/).

This is an independent experimental project. A=B and its original game materials belong to their respective creator or rights holder.

## License

The original source code and documentation created for this project are
available under the [MIT License](LICENSE). That license does not grant rights
to A=B or to game-derived material owned by Artless Games or another applicable
rights holder.
