# lark-cli 1.0.23 Migration Log

- Started implementation from the approved migration plan.
- Updated tests first to encode the 1.0.23 command surface before changing production code.
- Updated Python adapter entrypoints for v2 document fetch/create and `event consume`.
- Removed the `devflow start --force-subscribe` command-line option and pipeline plumbing.
- Installed project-local and global `@larksuite/cli@1.0.23`, then refreshed Lark skills with `npx.cmd skills add larksuite/cli -y -g`.
- Verified `uv run pytest tests -q -p no:cacheprovider` with 58 passing tests.
- Verified both `npm.cmd run lark:version` and `lark-cli.cmd --version` report `1.0.23`.
