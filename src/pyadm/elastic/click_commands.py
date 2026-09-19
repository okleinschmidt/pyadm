import sys
import click
import json
import re

from tabulate import tabulate

from pyadm import output

from pyadm.elastic.elastic import ElasticSearch
from pyadm.config import cluster_config
from pyadm.context_utils import register_context_commands
from pyadm.helper import Helper

defaults = {
    "url": "http://localhost:9200",
    "username": "elastic",
    "password": "changeme",
    "suffix": "reindex"
}


def match_indices(all_indices, pattern: str):
    """
    Return the indices matching *pattern*.

    A pattern is only treated as a wildcard if it actually contains one. An exact
    name matches that one index and nothing else - silently widening "logs" into
    "logs*" would also hit "logs-prod".
    """
    if '*' not in pattern:
        return [idx for idx in all_indices if idx['index'] == pattern]
    regex = '^' + re.escape(pattern).replace(r'\*', '.*') + '$'
    return [idx for idx in all_indices if re.match(regex, idx['index'])]


def parse_json_arg(value: str, label: str = "JSON"):
    """Parse a JSON string argument, raising ClickException on failure."""
    try:
        return json.loads(value)
    except Exception as e:
        raise click.ClickException(f"Invalid {label}: {e}")


# Holds the selected context name
selected_context = {"name": None}

# define click commands
@click.group("elastic", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--context", "-c", default=None, help="Select Elastic context name")
def elastic(context):
    """Manage Elasticsearch/OpenSearch clusters with multi-cluster support.
    
    Provides comprehensive tools for cluster management, index operations,
    document searches, and monitoring across multiple Elasticsearch or OpenSearch clusters.
    
    \b
    Examples:
        pyadm elastic info                          # Show cluster information
        pyadm elastic indices                       # List all indices
        pyadm elastic indices --limit 20            # List the first 20 indices
        pyadm elastic search logs -q '{"match_all":{}}'   # Search the logs index
        pyadm elastic shards                        # Shard budget and disk headroom
        pyadm elastic aliases                       # Show index aliases
        pyadm elastic health                       # Check cluster health
        
    \b
    Multi-cluster usage:
        pyadm elastic -c production info          # Use production context
        pyadm elastic -c staging indices          # Use staging context
    """
    selected_context["name"] = context


def get_es():
    try:
        cluster_cfg = cluster_config.get_cluster(selected_context["name"], prefix="ELASTIC")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    output.init_colors(cluster_cfg)
    return ElasticSearch(cluster_cfg)


@elastic.group("context", context_settings={'help_option_names': ['-h', '--help']})
def elastic_context():
    """Manage saved Elastic contexts."""
    pass


register_context_commands(elastic_context, "ELASTIC", "Elastic")

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
    data = dict(get_es().cluster_health())
    if "status" in data:
        data["status"] = output.cluster_status(data["status"])
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
    body_dict = parse_json_arg(body, "index body") if body else None
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
    query_dict = parse_json_arg(query, "query JSON")
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
    settings_dict = parse_json_arg(settings, "settings JSON")
    success = get_es().update_settings(index, settings_dict)
    if success:
        print(f"Settings updated for index '{index}'.")
    else:
        print(f"Failed to update settings for index '{index}'.", file=sys.stderr)

@elastic.command("shards")
@click.option('--by-index', is_flag=True, help='Show shard count per index instead of the summary')
@click.option('--limit', '-l', default=20, type=int, help='With --by-index: how many indices to show (0 = all)')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def shards(by_index, limit, as_json):
    """Show shard budget usage and disk headroom.

    A cluster stops accepting new shards once the number of open shards reaches
    cluster.max_shards_per_node times the number of data nodes. Unassigned
    replicas count towards that budget too. Running out of disk blocks writes in
    the same way, so both are reported together.

    \b
    Examples:
        pyadm elastic shards                  # Budget, headroom and disk per node
        pyadm elastic shards --by-index       # Which indices consume the budget
        pyadm elastic shards --by-index -l 0  # All indices
        pyadm elastic shards --json           # Machine-readable
    """
    try:
        client = get_es()

        if by_index:
            rows = client.get_shards_per_index()
            if limit:
                rows = rows[:limit]
            if as_json:
                click.echo(json.dumps(rows, indent=2))
                return
            if not rows:
                click.echo("No shards found.")
                return
            fields = ['index', 'shards', 'primaries', 'replicas', 'unassigned']
            click.echo(tabulate([[r[f] for f in fields] for r in rows], headers=fields))
            return

        capacity = client.get_shard_capacity()
        allocation = client.get_node_allocation()

        if as_json:
            click.echo(json.dumps({"capacity": capacity, "nodes": allocation}, indent=2))
            return

        limit_total = capacity['limit']
        percent = capacity['percent_used']

        click.echo(f"Cluster status : {output.cluster_status(capacity['cluster_status'])}")
        if limit_total:
            budget = f"{capacity['used']} / {limit_total} used ({percent}%), {capacity['remaining']} remaining"
            # Colour the budget line by how close it is to refusing new shards.
            budget_color = 'red' if percent >= 90 else 'yellow' if percent >= 80 else 'green'
            click.echo(f"Shard budget   : {output.style(budget, budget_color)}")
        else:
            click.echo(f"Shard budget   : {capacity['used']} used (no limit could be determined)")
        click.echo(
            f"                 {capacity['max_shards_per_node']} max_shards_per_node "
            f"x {capacity['data_nodes']} data node(s)"
        )
        unassigned = capacity['unassigned']
        unassigned_text = f"{unassigned} unassigned"
        if unassigned:
            unassigned_text = output.style(unassigned_text, 'yellow')
        click.echo(
            f"Shards         : {capacity['primaries']} primaries, "
            f"{capacity['replicas']} replicas, {unassigned_text}"
        )

        node_rows = [row for row in allocation if row.get('disk.percent') is not None]
        if node_rows:
            marks = node_rows[0]
            click.echo(
                f"\nDisk per node (watermarks: low {marks['watermark_low']}, "
                f"high {marks['watermark_high']}, flood {marks['watermark_flood']})"
            )
            headers = ['node', 'shards', 'used', 'avail', 'total', 'use%', 'state']
            table = [
                [
                    row.get('node', ''),
                    row.get('shards', ''),
                    row.get('disk.used', ''),
                    row.get('disk.avail', ''),
                    row.get('disk.total', ''),
                    f"{row.get('disk.percent')}%",
                    output.disk_state(row.get('state')),
                ]
                for row in sorted(node_rows, key=lambda r: -float(r.get('disk.percent') or 0))
            ]
            click.echo(tabulate(table, headers=headers))

        notes = []
        if unassigned:
            notes.append(
                f"{unassigned} unassigned shard(s) still consume budget. Reducing replicas frees it."
            )
        if limit_total and percent is not None and percent >= 80:
            notes.append(
                f"{percent}% of the shard budget is in use. New indices are refused at 100%."
            )
        for row in node_rows:
            if row.get('state') in ('low', 'high', 'flood'):
                notes.append(
                    f"Node '{row['node']}' is at {row['disk.percent']}% disk "
                    f"({row['state']} watermark); indices go read-only at flood stage."
                )
        if notes:
            click.echo()
            for note in notes:
                click.echo(output.style(f"! {note}", 'yellow'))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}")


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
    # Apply the limit if provided
    if limit:
        data = data[:limit]

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
        matches = match_indices(get_es().list_indices(), index)
        if not matches:
            click.echo(f"No index matches '{index}'. Nothing to reindex.")
            return
        for idx in matches:
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
@click.option('--index', '-i', required=True, help='Index name or pattern to delete')
@click.option('--force', '-f', is_flag=True, help='Force deletion without confirmation')
@click.option('--dry-run', is_flag=True, help='Show which indices would be deleted, delete nothing')
def delete(index, force, dry_run):
    """Delete one or more indices permanently.
    
    ⚠️  WARNING: This operation is irreversible and will permanently delete data!
    
    Supports wildcards for deleting multiple indices at once.
    Always prompts for confirmation unless --force is used.
    
    \b
    Examples:
        pyadm elastic delete --index "old-logs"           # Delete exactly that index
        pyadm elastic delete --index "temp-*"             # Delete all temp indices
        pyadm elastic delete --index "logs-2022*" --dry-run # Show what would go
    """
    try:
        matches = match_indices(get_es().list_indices(), index)
        if not matches:
            click.echo(f"No index matches '{index}'. Nothing to delete.")
            return

        click.echo(f"{len(matches)} index/indices match '{index}':")
        for idx in matches:
            click.echo(f"  {idx['index']}")
        if dry_run:
            click.echo("DRY-RUN: nothing was deleted.")
            return

        for idx in matches:
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
