import click
import json
import re

from tabulate import tabulate

from pyadm.elastic.elastic import ElasticSearch
from pyadm.config import config
from pyadm.helper import Helper

defaults = {
    "url": "http://localhost:9200",
    "username": "elastic",
    "password": "changeme",
    "suffix": "reindex"
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
@elastic.command("info")
def info():
    """
    Show cluster info
    """
    data = ElasticSearch(click_options).info()
    Helper.print_data(data)

@elastic.command("indices")
@click.option('--limit', '-l', default=None, type=int, help='Limit the number of rows to display')
@click.option('--output', '-o', type=click.Choice(['table', 'json']), default='table', help='Output format: table or json')
def indices(limit, output):
    """ List all indices """
    data = ElasticSearch(click_options).list_indices()
    
    header = data[0].keys()
    rows =  [x.values() for x in data]
    # Apply the limit if provided
    if limit:
        data = list(reversed(data))[:limit]

    if output == "json":
        print(json.dumps(data, indent=4))
    else:
        header = data[0].keys()
        rows = [x.values() for x in data]
        print(tabulate(rows, header, tablefmt="grid"))

@elastic.command("reindex")
@click.option('--index', '-i', 
              required=True,
              help=
              """
              Set the source index pattern. Use "*" as a wildcard to match multiple indices.
              e.g., "rsyslog-2023*" matches indices beginning with "rsyslog-2023".
              By default, a suffix "reindex" is added to the new index name, 
              resulting in names like "syslog-2023.07.01-reindex".
              """
              )
@click.option('--suffix', '-s', default=defaults["suffix"],
              help='Define the suffix for the destination index. Default is "reindex".')
@click.option('--force', '-f', is_flag=True, help='Force reindexing without confirmation.')
def reindex(index, suffix, force):
    """ Reindex indices """
    try:
        if suffix:
            suffix = suffix
            
        indices = ElasticSearch(click_options).list_indices()

        if not index.endswith('*'):
            index += '*'

        pattern = '^' + index.replace("*", ".*") + '$'

        for idx in indices:
            if re.match(pattern, idx['index']):
                new_index_name = f"{idx['index']}-{suffix}"
                if not force:
                    if not click.confirm(f"Do you really want to reindex from {idx['index']} to {new_index_name}?"):
                        continue  # Skip to next iteration if user says 'no'
                print(f"Reindexing {idx['index']} to {new_index_name}.")
                ElasticSearch(click_options).reindex(idx['index'], new_index_name)
                
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")



@elastic.command("delete")
@click.option('--index', '-i', help='Index name')
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation.')
def delete(index, force):
    """ Delete an index """
    try:    
        indices = ElasticSearch(click_options).list_indices()
        if not index.endswith('*'):
              index += '*'

        pattern = '^' + index.replace("*", ".*") + '$'  
        for index in indices:
            if re.match(pattern, index['index']):
                if not force:
                    if not click.confirm(f"Do you really want to delete index {index['index']} with {index['uuid']}?"):
                        continue  # Skip to next iteration if user says 'no'
                if ElasticSearch(click_options).delete_index(index):
                    print(f"Index {index['index']} with {index['uuid']} deleted.")
                else:
                    print(f"Index {index['index']} with {index['uuid']} not deleted.")
                  
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")

