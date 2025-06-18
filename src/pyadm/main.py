import click

from pyadm.ldapcli.click_commands import ldapcli
from pyadm.elastic.click_commands import elastic
from pyadm.pvecli import pvecli
from pyadm.config_commands import config_cli


@click.group()
def cli():
    """
    pyadm - Swiss Army Knife for Engineers and Administrators

    This tool provides modular functionality to perform various tasks efficiently.
    Currently, the available modules are 'ldap' and 'elastic'.

    Usage: pyadm <module> SUBCOMMAND [OPTIONS]

    For more information on a particular subcommand, run 'pyadm <module> SUBCOMMAND --help'.

    Example:
        $ pyadm ldap user jdoe             # Retrieve information for a user in the LDAP directory
        $ pyadm ldap groups jdoe           # Show groups associated with a user in the LDAP directory
        $ pyadm ldap members "Developers"  # Show members of a group in the LDAP directory
        $ pyadm elastic indices            # List all indices in the elastic cluster
    """
    pass

@click.command()
def version():
    """Display version information."""
    with open("VERSION", "r") as version_file:
        version = version_file.read().strip()
    click.echo(f"Version: {version}")


# Register the config command group
cli.add_command(config_cli)
cli.add_command(ldapcli)
cli.add_command(elastic)
cli.add_command(version)
cli.add_command(pvecli)



if __name__ == "__main__":
    cli()
