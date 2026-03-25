# skills-main Integration

This note captures the design principles extracted from [`skills-main`](../skills-main/README.md) and how `autodev` applies them.

## What `skills-main` is doing well

1. Each capability is a self-contained package rooted at `skills/<name>/SKILL.md`.
2. Heavy guidance lives close to the skill in `references/`, `scripts/`, `templates/`, and `assets/`.
3. Plugins are composition units, not the canonical source of truth. They bundle domain workflows, specialist agents, and sub-skills around one job.
4. Tool installation is thin. Claude, Codex, Gemini-style tools, and OpenCode should all discover the same skill content through their own native entrypoints.

## The principle `autodev` now follows

`autodev` keeps canonical workflow content in one shared location and generates thin wrappers per host tool:

- shared source: `AGENT.md` and `.skills/`
- shared runtime references: `.skills/autodev-runtime/`
- Claude wrapper: `.claude/` plus `.claude-plugin/`
- Codex wrapper: `.codex/`
- Gemini wrapper: `.gemini/` plus `.gemini/extensions/autodev-local/`
- OpenCode wrapper: `.opencode/`

This mirrors `skills-main`:

- one canonical body of guidance
- one canonical body of reusable skills
- multiple host-specific discovery adapters
- optional plugin or extension packaging layered on top

`autodev` keeps installation explicit:

- `autodev init --use <tool>` only scaffolds project-local files
- `autodev install-skills` registers those wrappers for the configured `backend.default`
- `autodev skills list` shows the current bundled or project-local skill catalog
- `autodev skills recommend "<need>"` helps route users toward the right shared skill

## Support matrix

| Tool | Backend runtime | Skill wrappers | Commands | Plugin / Extension | MCP reference |
| --- | --- | --- | --- | --- | --- |
| Claude | Yes | Yes | Yes | `.claude-plugin/` | `.skills/autodev-runtime/references/mcp-essentials.md` |
| Codex | Yes | Yes | No | No native plugin scaffold | `.skills/autodev-runtime/references/mcp-essentials.md` |
| Gemini | Yes | Yes | `.gemini/commands/` | `.gemini/extensions/autodev-local/` | `.skills/autodev-runtime/references/mcp-essentials.md` |
| OpenCode | Yes | Yes | No | No native plugin scaffold | `.skills/autodev-runtime/references/mcp-essentials.md` |

## Developer essentials to provision across all tools

- Filesystem and shell access
- Git inspection
- Browser or devtools access when relevant
- External documentation fetch when needed
- Reusable planning skills such as `coca-spec` and `spec-driven-develop`
- Discovery and authoring skills such as `find-skills` and `skill-creator`

## Why this structure is maintainable

- The real workflow text is edited once.
- Runtime references live with the shared skills instead of a parallel hidden directory.
- Projects get a curated default `.skills/` set that can be recommended on demand.
- Tool-specific files stay small and low-risk.
- Adding a new host tool becomes an adapter exercise instead of a content rewrite.
- External skill packs like `skills-main` can be linked in without changing `autodev` core logic.
