# AGENTS.md

Conventions for working on pyadm. They exist so that every module feels like
the same tool: a user who has learned `pyadm pve vm list` should already know
how `pyadm kimai timesheet list` behaves.

## Language

- Everything in the repository is **English**: code, identifiers, comments,
  docstrings, help texts, Markdown files and commit messages.
- User-facing strings are English too - pyadm's audience is administrators.

## Project layout

One directory per module under `src/pyadm/`:

```
src/pyadm/<module>cli/
├── <module>.py           # API/protocol client - no Click, no printing
├── click_commands.py     # The Click group, context handling, small commands
└── <topic>_commands.py   # Further commands, imported at the end of the group file
```

- Shared helpers live at the top level: `table.py` (list output), `output.py`
  (colour), `config.py` (contexts), `net_utils.py`, `context_utils.py`.
- Clients raise; commands catch and re-raise as `click.ClickException`. Keep
  the client free of Click so the logic stays testable on its own.
- Register a new module in `main.py` under `lazy_subcommands`, and add its
  prefix to `ClusterConfig.MODULE_KEYS` in `config.py`.

## List output

**All listings go through `pyadm.table`.** Never call `tabulate` directly in a
command; `pyadm pve vm list` is the reference for how a listing looks.

```python
from pyadm.table import echo_json, echo_table, render_table, rows_from, select_fields

fields = select_fields(fields_option, DEFAULT_FIELDS)
echo_table(rows_from(items, fields), fields, empty="No indices found.")
```

- Format: tabulate's default `simple` (header underlined with dashes, no
  borders). No `grid`, no `plain`, no ad-hoc separators.
- Headers: **lower case**, named after the underlying field (`vmid`, `docs.count`,
  `store.size`), so `-o/--output` uses the same spelling the header shows.
- Empty result: a short sentence (`No timesheet entries found.`), not an empty
  table.
- A single object is printed as `Label: value` lines, not as a table. A missing
  value prints blank, never `None`.

## Command conventions

- Group and command help carry an `\b` Examples block with real invocations.
- `--json` / `-j` is a flag that prints the raw data via `echo_json`.
- `--output` / `-o` takes a comma-separated field list for table columns.
- Other shared short options: `--context/-c`, `--limit/-l`, `--sort`,
  `--dry-run`, `--yes/-y`, `--node/-n`.
- Anything that writes supports `--dry-run` where it is meaningful, and asks
  for confirmation before multiple or destructive changes unless `--yes`.
- Accept names as well as numeric IDs wherever the API has both, and resolve
  ambiguity with an error that lists the candidates.

## Configuration

- Contexts live in `~/.config/pyadm/pyadm.conf` as `[<MODULE>_CONTEXT_<name>]`
  sections; the active one per module is in `[CONTEXT]`.
- Resolve a context with `cluster_config.get_cluster(name, prefix="<MODULE>")`
  and call `output.init_colors(cfg)` afterwards.
- Register `context list/current/use` via
  `context_utils.register_context_commands`.
- Shared section keys keep their meaning across modules: `skip_tls_verify`,
  `force_ipv4`, `timeout`, `colors`.
- Extend `pyadm config generate` whenever a new section or key is introduced.

## Colour

Colour is opt-in (`colors = yes`) and handled by `pyadm.output`: `cluster_status`,
`guest_status`, `disk_state`, `usage`, `age`, `style`. Never emit ANSI codes
directly, and leave a value uncoloured rather than guessing what an unknown
state means.

## Documentation

Every user-visible change updates `README.md`: the module section, the
configuration options and the example configuration.
