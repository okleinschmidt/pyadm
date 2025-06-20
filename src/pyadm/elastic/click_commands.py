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
@click.group("elastic", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--cluster", "-c", default=None, help="Select cluster by name (section in config)")
def elastic(cluster):
    """Manage Elasticsearch/OpenSearch clusters with multi-cluster support.
    
    Provides comprehensive tools for cluster management, index operations,
    document searches, and monitoring across multiple Elasticsearch or OpenSearch clusters.
    
    \b
    Examples:
        pyadm elastic info                          # Show cluster information
        pyadm elastic indices                       # List all indices
        pyadm elastic indices --size               # Show indices with sizes
        pyadm elastic search "error" --index logs  # Search for "error" in logs index
        pyadm elastic nodes                        # Show cluster nodes
        pyadm elastic health                       # Check cluster health
        
    \b
    Multi-cluster usage:
        pyadm elastic -c production info           # Use production cluster
        pyadm elastic -c staging indices          # Use staging cluster
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
    """Show comprehensive cluster information and statistics.
    
    Displays cluster name, version, status, node count, and other
    essential cluster metadata.
    """
    data = get_es().info()
    Helper.print_data(data)


# Show cluster health
@elastic.command("health")
def health():
    """Show cluster health status and diagnostics.
    
    Displays cluster health color (green/yellow/red), number of nodes,
    active/relocating shards, and other health metrics.
    """
    data = get_es().cluster_health()
    Helper.print_data(data)


# Create a new index
@elastic.command("create-index")
@click.argument('index')
@click.option('--body', '-b', default=None, help='Index settings/mappings as JSON string')
def create_index(index, body):
    """Create a new index with optional settings and mappings.
    
    INDEX: Name of the index to create
    
    \b
    Examples:
        pyadm elastic create-index my-logs
        pyadm elastic create-index users --body '{"settings":{"number_of_shards":3}}'
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
    """Show field mappings and data types for an index.
    
    INDEX: Name of the index to inspect
    
    \b
    Example:
        pyadm elastic mapping my-logs
    """
    data = get_es().get_mapping(index)
    Helper.print_data(data)


# Search documents in an index
@elastic.command("search")
@click.argument('index')
@click.option('--query', '-q', required=True, help='Query as JSON string (Elasticsearch DSL)')
@click.option('--size', '-s', default=10, help='Number of results to return')
def search(index, query, size):
    """Search for documents in an index using Elasticsearch DSL.
    
    INDEX: Name of the index to search
    
    \b
    Examples:
        pyadm elastic search logs --query '{"match":{"message":"error"}}'
        pyadm elastic search users --query '{"term":{"status":"active"}}' --size 5
        pyadm elastic search "*" --query '{"match_all":{}}' --size 20
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
    """Show index aliases and their associated indices.
    
    INDEX: Optional index name to filter aliases (shows all if omitted)
    
    \b
    Examples:
        pyadm elastic aliases                    # Show all aliases
        pyadm elastic aliases my-logs           # Show aliases for specific index
    """
    data = get_es().get_aliases(index)
    Helper.print_data(data)


# Show settings
@elastic.command("settings")
@click.argument('index', required=False)
def settings(index):
    """Show index settings like shards, replicas, and analysis configuration.
    
    INDEX: Optional index name to filter settings (shows all if omitted)
    
    \b
    Examples:
        pyadm elastic settings                  # Show settings for all indices
        pyadm elastic settings my-logs         # Show settings for specific index
    """
    data = get_es().get_settings(index)
    Helper.print_data(data)


# Update settings
@elastic.command("update-settings")
@click.argument('index')
@click.option('--settings', '-s', required=True, help='Settings as JSON string')
def update_settings(index, settings):
    """Update dynamic settings for an index.
    
    INDEX: Name of the index to update
    
    \b
    Examples:
        pyadm elastic update-settings my-logs --settings '{"number_of_replicas":2}'
        pyadm elastic update-settings logs --settings '{"refresh_interval":"30s"}'
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
    """List all indices with detailed information.
    
    Shows index names, document counts, sizes, health status, and other metrics
    in a comprehensive overview of your cluster's indices.
    
    \b
    Examples:
        pyadm elastic indices                   # Show all indices in table format
        pyadm elastic indices --limit 10       # Show only first 10 indices
        pyadm elastic indices --output json    # Output as JSON for scripting
    """
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
              help='Source index pattern. Use "*" as wildcard (e.g., "logs-2023*")')
@click.option('--suffix', '-s', default=defaults["suffix"],
              help='Suffix for destination index name (default: "reindex")')
@click.option('--force', '-f', is_flag=True, help='Force reindexing without confirmation')
def reindex(index, suffix, force):
    """Reindex data from source indices to new destination indices.
    
    Creates new indices with a suffix and copies all data from matching source indices.
    Useful for applying new mappings, changing settings, or reorganizing data.
    
    \b
    Examples:
        pyadm elastic reindex --index "logs-2023*"                    # Reindex all 2023 logs
        pyadm elastic reindex --index "old-data" --suffix "v2"       # Create old-data-v2
        pyadm elastic reindex --index "users*" --force               # Skip confirmations
    """
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
@click.option('--index', '-i', help='Index name or pattern to delete')
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation')
def delete(index, force):
    """Delete one or more indices permanently.
    
    ⚠️  WARNING: This operation is irreversible and will permanently delete data!
    
    Supports wildcards for deleting multiple indices at once.
    Always prompts for confirmation unless --force is used.
    
    \b
    Examples:
        pyadm elastic delete --index "old-logs"           # Delete single index
        pyadm elastic delete --index "temp-*"             # Delete all temp indices
        pyadm elastic delete --index "logs-2022*" --force # Force delete without prompt
    """
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

