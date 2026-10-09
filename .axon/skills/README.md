# hippo-on-axon — user skills

This directory is the **per-project override slot** for Axon SDK skills.

## What lives here

Each subdirectory is one skill, named after the skill it overrides (or a
brand-new one).  Layout:

```
.axon/skills/
├── README.md                 (this file)
└── <skill-name>/
    └── SKILL.md              (the skill body)
```

## Override semantics

This directory is the single place **you** edit. No coding agent reads
`.axon/skills/` directly, so `axon setup` (or `axon setup --refresh`)
**projects** each skill here into the directory each agent actually reads:

- `.claude/skills/<name>` — read by Claude Code (and Cursor)
- `.agents/skills/<name>` — read by Codex (and Cursor)

Each link is a symlink back to your skill here (a copy on
filesystems without symlink support). So if you create
`.axon/skills/axon-setup/SKILL.md` and run `axon setup --refresh`, the
agent picks up your version. Naming a directory after a skill that does
not exist in the bundle simply adds a new skill local to this project.

**How reliably your override beats the bundled skill depends on the
agent:**

| Agent       | Override guarantee                                              |
|-------------|----------------------------------------------------------------|
| Claude Code | **Guaranteed** — a project-level skill shadows the bundled one. |
| Codex       | Discovered and preferred by scan order. For a *hard* override of a same-named bundled skill, disable the bundled twin in `~/.codex/config.toml` (`[[skills.config]] enabled = false`). |
| Cursor      | Discovered via the links above; Cursor documents no same-name precedence, so treat it as best-effort. |

Run `axon doctor` to confirm the links are live and current.

## Authoring tips for the FDE

- A skill is a folder with one `SKILL.md`. The first heading is the
  name the agent uses to find it.
- Keep skills focused on **one** workflow-authoring concern (e.g.
  "delegate variable threading") — a long all-in-one skill drags the
  agent off-track.
- Skills shipped with the SDK live one level above this directory in
  the installed package (`python -c "import axon; print(axon.bundled_skill_path('<name>'))"`).
  Read those to see the house style before authoring a new one.

## Upgrade safety

This directory lives in your repo, not inside the SDK wheel, so
upgrading the SDK leaves it untouched — the bundled-skills tree that
ships inside the wheel is what gets replaced, not your local
overrides. Keep this directory under version control alongside the
rest of the project.

After upgrading the SDK, run `axon setup --refresh` to rebuild the
per-agent links against the new bundled skills. `axon doctor`
warns you when a refresh is needed.
