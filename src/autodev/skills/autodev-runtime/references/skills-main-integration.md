# `skills-main` Integration Notes

This project-local note captures the reusable structure observed in the bundled
`skills-main/` repository so `autodev` can scaffold compatible tooling.

## Structural Pattern

`skills-main` follows a consistent packaging model:

1. `skills/<skill-name>/SKILL.md` is the entrypoint contract.
2. `references/`, `scripts/`, `templates/`, and `assets/` are colocated with each skill.
3. `plugins/<plugin-name>/` composes multiple skills and specialist agents around one domain.
4. Host-tool installation stays thin: each tool only links or discovers the same shared content through its native path conventions.

## What `autodev` copies from that design

- Canonical workflow text and skills live once under `AGENT.md` and `.skills/`.
- Each host tool gets a thin native wrapper in its own discovery path.
- Skills stay file-based and portable instead of relying on one host-specific registry.
- Optional plugin or extension packaging is separate from the canonical skill text.

## Tool mapping

- Claude: wrappers + plugin metadata
- Codex: wrappers + install doc
- Gemini: wrappers + commands + settings + extension scaffold
- OpenCode: wrappers + install doc

## Developer essentials

Every supported tool should be provisioned with the same high-level capability set:

- filesystem and shell access
- git inspection
- browser or devtools access when relevant
- documentation fetch or web lookup
- reusable planning skills such as `coca-spec` and `spec-driven-develop`
