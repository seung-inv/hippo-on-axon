# hippo-on-axon — agent context

This directory is the **per-project override slot** for Axon SDK agent
context — short reference docs a coding agent reads when authoring code
against the SDK (DSL invariants, error taxonomy, common pitfalls).

## What lives here

Flat tree of `*.md` files. Drop one in to override or supplement the
context bundled with the SDK wheel. Naming a file after a bundled
context file overrides it; naming it something new adds a new context
entry visible only to this project.

The bundled context tree is enumerable at runtime:

```bash
uv run python -c "import axon; print(axon.bundled_context_files())"
```

## Override semantics

See `.axon/skills/README.md` — the resolution model is the same.
