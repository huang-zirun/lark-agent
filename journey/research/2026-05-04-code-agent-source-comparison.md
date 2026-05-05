# Code Agent Source Comparison

Date: 2026-05-04

## Goal

Choose the migration boundary for DevFlow's third node, `code-generation-agent`, by comparing local Claw Code with nano-style and Gemini-style code agents.

## Sources Checked

- `D:\lark\claw-code-main`: local source reference. Most useful for file tools, permission modes, workspace boundary checks, tool registry shape, and structured patch/diff audit.
- `https://github.com/shareAI-lab/learn-claude-code`: nano Claude Code style agent harness. Useful as a reminder that a small shell/tool loop can be enough for v1.
- `https://github.com/SafeRL-Lab/cheetahclaws`: Python-native autonomous assistant. Useful for keeping DevFlow Python-first instead of vendoring another runtime.
- `https://github.com/google-gemini/gemini-cli`: official Gemini CLI. Useful for product boundaries: built-in file/shell/web tools, MCP extension, checkpointing, and non-interactive JSON/stream modes.

`git clone --depth 1` was attempted for the public GitHub references under `.test-tmp\code-agent-research`, but this machine failed TLS credential acquisition through Git. The implementation will use the accessible GitHub repository pages plus the local `claw-code-main` source and avoid depending on un-cloned temporary source.

## Decision

Build a Python-native `devflow.code` package rather than vendoring Claw's Rust workspace or Gemini's Node/TypeScript runtime.

The migrated core is:

- bounded file tools: read, write, edit, glob, grep;
- workspace-write permission checks;
- destructive PowerShell command rejection for v1;
- LLM tool-call loop with audited tool events;
- final code artifact and git diff capture.

Deferred:

- MCP;
- LSP;
- parallel subagents;
- long-running background workers;
- automatic dependency installation;
- automatic commit/PR.

## Rationale

DevFlow is currently a Python standard-library CLI with LLM calls, Feishu integration, local run artifacts, and human checkpoints. A small Python code-agent kernel fits this architecture better than importing a full external code-agent runtime. It also preserves the project's existing contract style: English schema fields, Chinese human-readable values, and audit artifacts under `artifacts/runs/{run_id}`.
