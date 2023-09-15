import click
import json
import elasticsearch

from pyadm.config import config

defaults = {
    "server": "ldap://localhost",
    "base_dn": "dc=example,dc=org",
    "username": "root@example.org",
    "password": "s3cur3_p455w0rd",
}

click_options = {}

def prompt_password_if_needed(ctx, param, value):
    if value:  # `-p` was provided without an argument
        return click.prompt("Specify the password for authentication", hide_input=True)
    return None  # Default value, if `-p` was not provided at all.

# define click commands
@click.group("elastic")
@click.option("--server", "-s", help="Specify the Search server.")
@click.option("--username", "-u", help="Specify the username for authentication.")
@click.option("--password", "-p", help="Specify the password for authentication.",
              prompt=False,  # Do not use built-in prompting.
              callback=prompt_password_if_needed, 
              is_flag=True, 
              flag_value=True, 
              expose_value=True,
              default=None)
def elastic(server, base_dn, username, password):
    """
    Elastic/OpenSearch.   
    """
    if not (server or base_dn or username or password):
        click_options["server"] = config["ELASTIC"]["server"] or defaults["server"]
        click_options["username"] = config["ELASTIC"]["username"] or defaults["username"]
        click_options["password"] = config["ELASTIC"]["password"] or defaults["password"]
    else:
        click_options["server"] = server or defaults["server"]
        click_options["username"] = username or defaults["username"]
        click_options["password"] = password or defaults["password"]

# show information about a user
@elastic.command("list")
def list():
    """
    List indices
    """


