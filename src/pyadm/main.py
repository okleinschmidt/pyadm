import click

from pyadm.ldapcli.click_commands import ldapcli


@click.group()
def cli():
    """
    pyadm - Swiss Army Knife for Engineers and Administrators
 
    It provides modular functionality to perform various tasks efficiently.
    Currently, the only available module is 'ldap', which enables LDAP-related operations.

    Usage: pyadm ldap SUBCOMMAND [OPTIONS]

    To use the LDAP module, execute the 'pyadm ldap' command followed by the desired subcommand to perform specific LDAP operations.

    For more information on a particular subcommand, run 'pyadm ldap SUBCOMMAND --help'.
    
    \b
    Example:
    $ pyadm ldap user jdoe             # Retrieve information for a user in the LDAP directory
    $ pyadm ldap groups jdoe           # Show groups associated with a user in the LDAP directory
    $ pyadm ldap members "Developers"  # Show members of a group in the LDAP directory
    """
    pass

@click.command()
def version():
    """Display version information"""
    with open("VERSION", "r") as version_file:
        version = version_file.read().strip()
    click.echo(f"Version: {version}")

cli.add_command(ldapcli)
cli.add_command(version)

if __name__ == "__main__":
    cli()
