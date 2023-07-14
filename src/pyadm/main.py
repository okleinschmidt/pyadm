import click

from pyadm.ldap.click_commands import ldap

@click.group(help='PyADM')
def cli():
    pass

cli.add_command(ldap)

if __name__ == "__main__":
    cli()