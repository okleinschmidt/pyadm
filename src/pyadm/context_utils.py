import click
from pyadm.config import cluster_config
from pyadm.table import echo_table


def register_context_commands(group, prefix: str, label: str):
    """Register list/current/use commands for a context group."""

    @group.command("list", help=f"List available {label} contexts.")
    def list_contexts():
        try:
            contexts = cluster_config.list_contexts(prefix=prefix)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        active = cluster_config.get_active_context(prefix=prefix)
        rows = [
            ["*" if active and e["name"].lower() == active.lower() else "", e["name"], e["section"]]
            for e in contexts
        ]
        echo_table(rows, ["active", "context", "section"], empty=f"No {label} contexts found.")

    @group.command("current", help=f"Show the currently active {label} context.")
    def current_context():
        try:
            resolved = cluster_config.resolve_context(prefix=prefix)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{resolved['name']} (section: {resolved['section']})")

    @group.command("use", help=f"Switch active {label} context.")
    @click.argument("context_name")
    def use_context(context_name):
        try:
            selected = cluster_config.set_active_context(prefix=prefix, name=context_name)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Active {label} context set to: {selected}")
