---
name: reverse-skill-router
description: Use the reverse-skill repository. The full package is installed locally at /var/minis/skills/reverse-skill/ — for authorized reverse engineering, security analysis, CTF, and defensive testing tasks.
---

# Reverse Skill Codex adapter

This plugin is an optional Codex entry point. The repository remains the canonical, client-neutral implementation; a full local install lives at `/var/minis/skills/reverse-skill/`.

When the current workspace is the `reverse-skill` repository (or the local install):

1. Read `RULES.md` at the repository root.
2. Run the platform-native `skills/scripts/master-route` entry with the user's task to select the PRIMARY skill from `skills/config/routing.json`.
3. Before any target action, create and validate `work/<case>/scope.md` with the platform-native `case-init` and `case-guard` scripts.
4. Open the selected `skills/<PRIMARY>/SKILL.md` and follow its task-specific instructions.
5. Resolve tools only through the generated `skills/tool-index.md`; do not register MCP servers or install tools unless the user requested that action.

The canonical repository is installed locally at `/var/minis/skills/reverse-skill/` (source: https://github.com/zhaoxuya520/reverse-skill). If no other repository path is supplied, continue from that path's `RULES.md`.

Do not treat the presence of this plugin, a target name, or a sample path as authorization. Authorization comes from the repository's scope contract.
