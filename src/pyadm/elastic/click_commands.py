# New imports for new commands
import sys
import click
import json
import re

from tabulate import tabulate

from pyadm.elastic.elastic import ElasticSearch
from pyadm.config import cluster_config
from pyadm.helper import Helper

defaults = {
    "url": "http://localhost:9200",
    "username": "elastic",
    "password": "changeme",
    "suffix": "reindex"
}


# Holds the selected cluster name
selected_cluster = {"name": None}

def prompt_password_if_needed(ctx, param, value):
    if value:  # `-p` was provided without an argument
        return click.prompt("Specify the password for authentication", hide_input=True)
    return None  # Default value, if `-p` was not provided at all.

# define click commands
@click.group("elastic")
@click.option("--cluster", "-c", default=None, help="Select cluster by name (section in config)")
def elastic(cluster):
    """
    Elastic/OpenSearch (multi-cluster support).
    """
    selected_cluster["name"] = cluster


def get_es():
    # Get config for selected cluster
    cluster_cfg = cluster_config.get_cluster(selected_cluster["name"])
    return ElasticSearch(cluster_cfg)

# show information about a user
# show information about a user
@elastic.command("info")
def info():
    """
    Show cluster info
    """
    data = get_es().info()
    Helper.print_data(data)


# Show cluster health
@elastic.command("health")
def health():
    """
    Show cluster health
    """
    data = get_es().cluster_health()
    Helper.print_data(data)


# Create a new index
@elastic.command("create-index")
@click.argument('index')
@click.option('--body', '-b', default=None, help='Index settings/mappings as JSON string')
def create_index(index, body):
    """
    Create a new index
    """
    import json
    body_dict = json.loads(body) if body else None
    success = get_es().create_index(index, body_dict)
    if success:
        print(f"Index '{index}' created.")
    else:
        print(f"Failed to create index '{index}'.", file=sys.stderr)


# Show mapping of an index
@elastic.command("mapping")
@click.argument('index')
def mapping(index):
    """
    Show mapping of an index
    """
    data = get_es().get_mapping(index)
    Helper.print_data(data)


# Search documents in an index
@elastic.command("search")
@click.argument('index')
@click.option('--query', '-q', required=True, help='Query as JSON string (Elasticsearch DSL)')
@click.option('--size', '-s', default=10, help='Number of results to return')
def search(index, query, size):
    """
    Search for documents in an index
    """
    import json
    try:
        query_dict = json.loads(query)
    except Exception as e:
        print(f"Invalid query JSON: {e}", file=sys.stderr)
        return
    data = get_es().search(index, query_dict, size)
    Helper.print_data(data)


# Show aliases
@elastic.command("aliases")
@click.argument('index', required=False)
def aliases(index):
    """
    Show aliases for an index or all indices
    """
    data = get_es().get_aliases(index)
    Helper.print_data(data)


# Show settings
@elastic.command("settings")
@click.argument('index', required=False)
def settings(index):
    """
    Show settings for an index or all indices
    """
    data = get_es().get_settings(index)
    Helper.print_data(data)


# Update settings
@elastic.command("update-settings")
@click.argument('index')
@click.option('--settings', '-s', required=True, help='Settings as JSON string')
def update_settings(index, settings):
    """
    Update settings for an index
    """
    import json
    try:
        settings_dict = json.loads(settings)
    except Exception as e:
        print(f"Invalid settings JSON: {e}", file=sys.stderr)
        return
    success = get_es().update_settings(index, settings_dict)
    if success:
        print(f"Settings updated for index '{index}'.")
    else:
        print(f"Failed to update settings for index '{index}'.", file=sys.stderr)

@elastic.command("indices")
@click.option('--limit', '-l', default=None, type=int, help='Limit the number of rows to display')
@click.option('--output', '-o', type=click.Choice(['table', 'json']), default='table', help='Output format: table or json')
def indices(limit, output):
    """ List all indices """
    data = get_es().list_indices()
    if not data:
        print("No indices found.")
        return
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
        indices = get_es().list_indices()
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
                get_es().reindex(idx['index'], new_index_name)
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
        indices = get_es().list_indices()
        if not index.endswith('*'):
            index += '*'
        pattern = '^' + index.replace("*", ".*") + '$'  
        for idx in indices:
            if re.match(pattern, idx['index']):
                if not force:
                    if not click.confirm(f"Do you really want to delete index {idx['index']} with {idx['uuid']}?"):
                        continue  # Skip to next iteration if user says 'no'
                if get_es().delete_index(idx['index']):
                    print(f"Index {idx['index']} with {idx['uuid']} deleted.")
                else:
                    print(f"Index {idx['index']} with {idx['uuid']} not deleted.")
    except click.ClickException as e:
        raise e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")

