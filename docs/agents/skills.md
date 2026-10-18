# Project skills

## Shared discovery

- `.agents/skills/<name>/SKILL.md` is the canonical copy, discovered by Codex CLI, the Codex IDE extension, and the Codex app.
- `.claude/skills` is a relative symlink to `../.agents/skills`, the project skill path for Claude Code. Do not maintain a second copy.
- `AGENTS.md` holds the shared project instructions. Root `CLAUDE.md` imports it with `@AGENTS.md` for Claude Code, including versions that do not load `AGENTS.md` directly.
- Start a new session in this checkout after pulling these files. A session that is already open can retain an older skill list. No global install or account configuration is part of this setup.

On macOS/Linux, a normal Git checkout preserves the symlink. On Windows, enable Developer Mode and `git config --global core.symlinks true` **before cloning**. Otherwise Git can check out the link as an ordinary text file, and Claude Code will not discover the shared directory. Check your own platform before changing global Git configuration.

## Source and catalog

Copied without content changes from `MarcinGruchala/project-knowledge-fun`, branch `claude/ai-skills-folder-setup-2d0f1b`, commit **`1a216db63ca34b76694b9292eb861a0f2d892e1f`** ([source PR #209](https://github.com/MarcinGruchala/project-knowledge-fun/pull/209)). At copy time that PR was open: this is deliberately not a claim that the skills were on the source repository's `main`.

The entire `.agents/skills/` tree is copied, including metadata, scripts, templates, references, and the HTML plan runtime. `docs/agents/domain.md` is copied unchanged; `docs/agents/issue-tracker.md` is adapted to LocalScribe. No global/profile skills are copied or modified.

| Skill | Upstream recorded by the source project | Use in LocalScribe |
| --- | --- | --- |
| `wayfinder` | `mattpocock/skills` | Decision maps and dependent work |
| `grilling` | `mattpocock/skills` | Clarify a plan one question at a time |
| `grill-me` | `mattpocock/skills` | Shortcut to grilling |
| `grill-with-docs` | `mattpocock/skills` | Grilling with domain modeling |
| `domain-modeling` | `mattpocock/skills` | Domain vocabulary and meaningful ADRs |
| `to-spec` | `mattpocock/skills` | Turn an agreed discussion into a specification |
| `to-tickets` | `mattpocock/skills` | Split a specification into implementation tickets |
| `implement` | `mattpocock/skills` | Implement scoped work with tests and review |
| `tdd` | `mattpocock/skills` | Test-first implementation |
| `code-review` | `mattpocock/skills` | Review standards and specification compliance |
| `codebase-design` | `mattpocock/skills` | Module boundaries and deep-module design |
| `improve-codebase-architecture` | `mattpocock/skills` | Find justified architectural improvements |
| `diagnosing-bugs` | `mattpocock/skills` | Investigate bugs and performance problems |
| `prototype` | `mattpocock/skills` | Scoped throwaway experiments |
| `research` | `mattpocock/skills` | Record findings and sources |
| `setup-matt-pocock-skills` | `mattpocock/skills` | Maintain tracker/domain documentation when needed |
| `html-plan` | `anthropics/claude-plugins-community` | Review an interactive implementation plan |

These are the source project's recorded upstreams, not a new audit of upstream versions or licensing. This revision pins the source copy; it does not track upstream automatically.

## Project-specific context and limits

- Read `AGENTS.md`, the accepted MVP specification, relevant tickets, and current progress before implementation. Do not run the setup skill again just to create placeholder files.
- GitHub operations target **`MarcinGruchala/local-scribe`**. Use `docs/agents/issue-tracker.md`, including the authentication restrictions of your harness. Copying a skill does not authorize tracker writes, model downloads, inference, issue closure, merging, or deployment.
- LocalScribe has a single domain context. Read a glossary/ADR if one exists; create one only when an actual term or decision needs recording. See `docs/agents/domain.md`.
- The original skills can name harness-specific tools, commands, or optional skills that are not installed. Use the supported equivalent in your agent; report a missing capability rather than pretending it ran or installing unrelated tools automatically. For example, use Codex's supported sub-agent mechanism instead of assuming a Claude `Agent` tool exists.
- Upstream `disable-model-invocation` and `agents/openai.yaml` metadata can have different support across agents. Explicitly invoke a workflow when needed (Claude Code: `/skill-name`; Codex: `/skills` or `$skill-name`). Personal skills with the same name can take precedence; check for overrides if a local edit appears ineffective.
- Keep private media, model weights, credentials, stores, and generated transcripts out of Git and out of external model/research requests.

## Validation and maintenance

For a clean checkout, confirm that:

1. Every `.agents/skills/*/SKILL.md` has YAML frontmatter with a unique `name` matching its directory and a nonempty `description`.
2. `.claude/skills` is a real symlink to `../.agents/skills` and exposes the same skill files.
3. `CLAUDE.md` imports the existing root `AGENTS.md`.
4. All vendored file bytes and Git modes match the pinned source tree when claiming an unchanged copy.
5. `git diff --check` passes for locally authored setup/docs and only agent setup/documentation paths changed. The unchanged upstream HTML runtime contains three trailing-whitespace lines (`htmlplan.css:327`, `htmlplan.js:1016`, `pack.mjs:108`); retain those bytes for source parity and report them separately rather than claiming an entirely whitespace-clean vendored tree.

Then open a new Codex session and inspect `/skills`. In Claude Code inspect `/` for the skill commands and `/memory` for the imported instructions. These interactive checks require each client and its authorized login; filesystem/source-parity checks alone do not prove a live model session loaded the skills.

To update, copy from an explicitly reviewed source revision, preserve all companion files and modes, rerun the checks, and update the provenance above. Edit the canonical `.agents/skills/` files for deliberate local changes; document deviations instead of calling them an unchanged copy.

References: [Codex skills](https://developers.openai.com/codex/skills/), [Claude Code skills](https://code.claude.com/docs/en/skills), [Claude Code instruction imports](https://code.claude.com/docs/en/memory#import-additional-files).
