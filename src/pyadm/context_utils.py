import click
from tabulate import tabulate
from pyadm.config import cluster_config


def register_context_commands(group, prefix: str, label: str):
    """Register list/current/use commands for a context group."""

    @group.command("list")
    def list_contexts():
        f"""List available {label} contexts."""
        try:
            contexts = cluster_config.list_contexts(prefix=prefix)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        if not contexts:
            click.echo(f"No {label} contexts found.")
            return
        active = cluster_config.get_active_context(prefix=prefix)
        rows = [
            ["*" if active and e["name"].lower() == active.lower() else "", e["name"], e["section"]]
            for e in contexts
        ]
        click.echo(tabulate(rows, headers=["ACTIVE", "CONTEXT", "CONFIG SECTION"], tablefmt="plain"))

    @group.command("current")
    def current_context():
        f"""Show the currently active {label} context."""
        try:
            resolved = cluster_config.resolve_context(prefix=prefix)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{resolved['name']} (section: {resolved['section']})")

    @group.command("use")
    @click.argument("context_name")
    def use_context(context_name):
        f"""Switch active {label} context."""
        try:
            selected = cluster_config.set_active_context(prefix=prefix, name=context_name)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Active {label} context set to: {selected}")
