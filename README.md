# CodeLens

[![tests](https://github.com/BlackCat-art/codelens/actions/workflows/test.yml/badge.svg)](https://github.com/BlackCat-art/codelens/actions/workflows/test.yml)

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

### Report language

Reports are available in English and Chinese. Use `--lang en` or `--lang zh`. The default is `--lang auto`, which picks Chinese when `LC_ALL` or `LANG` starts with `zh` and English otherwise.

```bash
python codelens.py map /path/to/your/project --lang zh
python codelens.py trace /path/to/your/project function_name --lang en
```

Only the text CodeLens generates is translated. Module descriptions come from your own docstrings.

## Example output

The report below comes from a small demo "shop" project in [examples/demo](examples/demo) with typical AI-written problems planted on purpose. Full reports: [English](examples/CODELENS.example.en.md) | [中文](examples/CODELENS.example.zh.md).

Smell checklist (section 4):

- `shop.services.inventory:6` swallowed exception (an `except` that does nothing hides bugs)
- `shop.services.inventory:9` empty stub `reserve()`
- `shop.services.orders:11` leftover `# TODO: handle out-of-stock properly`
- `shop.services.payment:2` leftover `# placeholder: integrate real gateway`
- `shop.services.payment:7` empty stub `refund_check()`
- `calc_total` is defined twice (`inventory` and `pricing`), a likely duplicate implementation

Trace of `check_stock`, showing how execution reaches it:

```
== shop.services.inventory.check_stock (./shop/services/inventory.py:3-7) ==
Upstream:
└─ shop.services.orders.create_order (./shop/services/orders.py:4)
   └─ shop.app.main (./shop/app.py:4)
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
- Imports are resolved relative to the directory you pass in, so run CodeLens on your project's top-level source root.
- It is static analysis: it knows nothing about runtime values or business intent.
- The hotspot scoring weights are heuristic and have not been tuned on many real projects.

## Testing

```bash
pip install pytest
pytest
```

The tests run the tool on the demo project in both languages and check the findings, the dependency graph, `trace` output, and that the English and Chinese string tables stay in sync.

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
