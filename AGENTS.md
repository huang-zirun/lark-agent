# Project Instructions for Agents

## Working Rules

- **Use `uv` for Python**: prefer `uv pip install`, `uv run`, `uv venv` over pip/conda.
- **Use PowerShell**: all CLI operations use PowerShell syntax; avoid cmd.exe/Bash.
- **PowerShell Limitation**: PowerShell does not support `&&` syntax for chaining commands; use semicolon `;` or separate commands instead.
- **Use Standard Git Commit**: follow conventional commits format (`type(scope): subject`) with clear, descriptive messages; keep commits atomic and focused.
- **Clean Up Temporary Scripts**: delete any temporary scripts created for testing or validation purposes once verification is complete.

## Journey memory

Use `journey/` as the shared project memory across agent sessions.

- Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project: current strategy, key design decisions, trade-offs, constraints, and scope.
- Use `journey/logs/` for chronological process notes, progress, experiments, and failed paths.
- Use `journey/research/` for research notes and background findings.
- Update `journey/design.md` whenever the effective understanding of the project changes. Do not leave important decisions or trade-offs only in logs.

For any new project, planning-focused request, or sufficiently complex task, start with a fresh plan and write it to `journey/plans/YYYY-MM-DD-{title}.md` before implementing. Treat files in `journey/plans/` as the canonical plans. As work progresses, record concise updates in `journey/logs/YYYY-MM-DD-{title}.md` using the same date and title convention. In chat, provide only a brief summary and the relevant file path(s).
