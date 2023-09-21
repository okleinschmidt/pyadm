import click
import json

from pyadm.elastic.elastic import ElasticSearch
from pyadm.config import config

defaults = {
    "url": "http://localhost:9200",
    "username": "elastic",
    "password": "changeme",
}

click_options = {}

def prompt_password_if_needed(ctx, param, value):
    if value:  # `-p` was provided without an argument
        return click.prompt("Specify the password for authentication", hide_input=True)
    return None  # Default value, if `-p` was not provided at all.

# define click commands
@click.group("elastic")
@click.option("--url", "-url", help="Specify the Search URL.")
@click.option("--username", "-u", help="Specify the username for authentication.")
@click.option("--password", "-p", help="Specify the password for authentication.",
              prompt=False,  # Do not use built-in prompting.
              callback=prompt_password_if_needed, 
              is_flag=True, 
              flag_value=True, 
              expose_value=True,
              default=None)
def elastic(url, username, password):
    """
    Elastic/OpenSearch.   
    """
    if not (url or username or password):
        click_options["url"] = config["ELASTIC"]["url"] or defaults["url"]
        click_options["username"] = config["ELASTIC"]["username"] or defaults["username"]
        click_options["password"] = config["ELASTIC"]["password"] or defaults["password"]
    else:
        click_options["url"] = url or defaults["url"]
        click_options["username"] = username or defaults["username"]
        click_options["password"] = password or defaults["password"]

# show information about a user
@elastic.command("list")
def list():
    """
    List indices
    """
    ElasticSearch(click_options).info()

