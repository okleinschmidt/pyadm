import click

from pyadm.ldapcli.click_commands import ldapcli


@click.group(help="PyADM")
def cli():
    pass


cli.add_command(ldapcli)

if __name__ == "__main__":
    cli()
