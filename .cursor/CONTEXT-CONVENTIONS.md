# Contributor context conventions

`AGENTS.md` is the single canonical project guide. `CLAUDE.md` aliases it.
Cursor's always-on rule points there rather than repeating policy. Code routing
lives in `.cursor/CODEMAP.md`; platform setup lives in
`docs/development/platform-commands.md`; plans live in `plans/active/`.

Optional skills live in `.agents/skills/<name>/SKILL.md`. `.claude/skills` aliases
that directory; `.claude/commands` and `.claude/rules` alias the corresponding
Cursor directories. Edit targets, not links. Do not duplicate a skill and command
under the same name. The app's workspace loader also reads these skill paths.

Most existing skills/commands describe the original Mac project. They do not
activate its scheduled jobs, release policies, model mandates or mail reports in
this fork. Consult the tooling inventory before removing a skill with callers.
Personal settings and unrelated general-purpose agent skills belong outside Git.
