# CodeLens

[中文说明](README.zh.md)

A zero-dependency tool that turns an AI-generated Python project into a map a human can read, so you can understand the code, locate bugs, and fix them without asking an AI.

## Why

AI coding agents produce code faster than people can read it. When something breaks, it is tempting to paste the error back into the agent and hope. Over time nobody holds a mental model of the system. CodeLens uses plain static analysis (Python's `ast` module, no LLM, no network) to give you facts with file and line numbers, not guesses.

## Quick start

Requires Python 3.9+. No packages to install.

```bash
git clone https://github.com/BlackCat-art/codelens.git
cd codelens

# 1. Generate a project map
python codelens.py map /path/to/your/project -o CODELENS.md

# 2. Trace a function: who calls it, and what it calls
python codelens.py trace /path/to/your/project function_name -d 3
```

## What the map contains

- Entry points: modules with a `__main__` block and functions decorated as routes or commands.
- Module table and a Mermaid dependency graph (paste it into any Markdown viewer that supports Mermaid).
- Hotspots: the top 10 functions ranked by cyclomatic complexity, length, and number of callers. Read these first.
- Smell checklist for AI-written code: empty stub functions, swallowed exceptions (`except` that does nothing), leftover TODO/FIXME/placeholder markers, and same-named functions that may be duplicate implementations.
- Most frequently changed files from `git log`, since they are often where bugs live.

## Debugging with `trace`

`trace` prints two trees for the function you name:

- Upstream: who calls it, which shows how execution can reach the failing code.
- Downstream: what it calls, which shows where the fault may come from.

Each line includes `path:line`, so you can walk the chain by hand in your editor.

## Limitations

- Python only for now.
- Calls are matched by function name. Dynamic dispatch, callbacks, and same-named functions can cause false positives or missed edges.
- It is static analysis: it knows nothing about runtime values or business intent.
- The hotspot scoring weights are heuristic and have not been tuned on many real projects.

## Roadmap

- Multi-language support (JS/TS, Go, Java) via tree-sitter.
- Interactive HTML report with click-through to source.
- `git blame` integration to flag code that was AI-authored and never reviewed.
- Suggested reading order and per-module templates for recording design intent.
- Pre-commit / CI check that fails on excessive complexity or empty stubs.

## Contributing

Issues and pull requests are welcome. Real-world false positives and false negatives are especially useful: please include a minimal code sample.

## License

MIT. See [LICENSE](LICENSE).
