# Developer MCP Essentials

This file declares the project-owned MCP categories that should be provisioned for
supported tools.

## Supported tools

- claude
- codex
- gemini
- opencode

## Recommended MCP categories

- filesystem: read/write project files
- shell: run local build, test, and validation commands
- git: inspect diffs, status, and commit history
- browser/devtools: inspect local web apps when relevant
- docs/web-fetch: retrieve external documentation when needed

## Provisioning guidance

- Keep tool-specific MCP wiring out of shared skills.
- Prefer tool-local config snippets or install docs per host tool.
- Add concrete server definitions in tool-specific config files only after validating the host tool's expected format.
