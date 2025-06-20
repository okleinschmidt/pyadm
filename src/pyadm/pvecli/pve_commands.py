import click
import logging
import os.path
from typing import Optional
from pyadm.config import cluster_config
from pyadm.pvecli.pve import PVEClient

# Holds the selected PVE server name
selected_pve = {"name": None, "debug": False, "dry_run": False, "offline": False}


@click.group("pve", context_settings={'help_option_names': ['-h', '--help']})
@click.option("--server", "-s", default=None, help="Select Proxmox VE server by name (section in config)")
@click.option("--debug", "-d", is_flag=True, help="Enable debug output for API calls")
@click.option("--dry-run", is_flag=True, help="Show what would be done without connecting")
@click.option("--offline", is_flag=True, help="Work in offline mode with sample data")
def pvecli(server, debug, dry_run, offline):
    """Manage Proxmox Virtual Environment clusters.
    
    Use --server/-s to select a config section (e.g. [PVE], [PVE_PROD], ...).
    Use --offline to work with sample data when no server is available.
    """
    selected_pve["name"] = server
    selected_pve["debug"] = debug
    selected_pve["dry_run"] = dry_run
    selected_pve["offline"] = offline


def get_pve_client() -> Optional[PVEClient]:
    """Get a PVE client instance based on configuration."""
    if selected_pve["dry_run"]:
        click.echo("DRY-RUN mode: Would connect to Proxmox VE server")
        return None
        
    if selected_pve["offline"]:
        from pyadm.pvecli.offline_client import OfflinePVEClient
        click.echo("OFFLINE mode: Using sample data")
        return OfflinePVEClient()
        
    # Get configuration path
    config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
    
    # Check if config exists
    if not os.path.exists(config_path):
        raise click.ClickException(
            f"Configuration file not found: {config_path}\n"
            f"Please create a configuration file with 'pyadm config generate -o {config_path}'\n"
            f"Then edit it with 'pyadm config edit' to add your Proxmox VE server details."
            f"\n\nYou can also use --offline mode to work with sample data."
        )
    
    try:
        cfg = cluster_config.get_cluster(selected_pve["name"], prefix="PVE")
        
        # Check for required config values
        required_keys = ['host']
        
        # Check if we have token auth or password auth
        has_token = 'token_name' in cfg and 'token_value' in cfg
        has_password = 'password' in cfg
        
        if not has_token and not has_password:
            required_keys.extend(['password'])
        
        missing = [k for k in required_keys if k not in cfg]
        if missing:
            section = selected_pve["name"] or "PVE"
            raise click.ClickException(
                f"Missing required configuration in [{section}] section: {', '.join(missing)}\n"
                f"Please edit your configuration with 'pyadm config edit'"
                f"\n\nYou can also use --offline mode to work with sample data."
            )
            
        if selected_pve["debug"]:
            logging.basicConfig(level=logging.DEBUG)
            
        return PVEClient(cfg, debug=selected_pve["debug"])
    except Exception as e:
        if "No section" in str(e):
            section = selected_pve["name"] or "PVE"
            raise click.ClickException(
                f"Configuration section [{section}] not found.\n"
                f"Add it to your config with 'pyadm config edit' or specify a different section with --server"
                f"\n\nYou can also use --offline mode to work with sample data."
            )
        
        if "No route to host" in str(e) or "Connection refused" in str(e):
            raise click.ClickException(
                f"Cannot connect to Proxmox server: {str(e)}\n"
                f"Please check your network connection and server configuration.\n"
                f"\n\nYou can use --offline mode to work with sample data when no server is available."
            )
            
        raise

def resolve_resource_id(client, resource_id, node=None, resource_type="vm"):
    """
    Resolve a resource ID or name to its numeric ID and node.
    
    Args:
        client: The PVE client instance
        resource_id: Either numeric ID or name string
        node: Optional node specification
        resource_type: Either "vm" or "container"
        
    Returns:
        tuple: (numeric_id, node_name)
    
    Raises:
        click.ClickException: If the resource cannot be found
    """
    # Check if resource_id is numeric (ID) or name
    try:
        numeric_id = int(resource_id)
        is_id = True
    except ValueError:
        is_id = False
        
    if is_id:
        # If node is not provided, try to find it
        if not node:
            if resource_type == "vm":
                resources = client.get_vms()
            else:
                resources = client.get_containers()
                
            for resource in resources:
                if resource['vmid'] == numeric_id:
                    node = resource['node']
                    break
                    
        if not node:
            raise click.ClickException(
                f"Could not find node for {resource_type.upper()} ID {numeric_id}. "
                f"Please specify with --node."
            )
        
        return numeric_id, node
        
    else:
        # Get resource by name
        if resource_type == "vm":
            resource = client.find_vm_by_name(resource_id)
        else:
            resource = client.find_container_by_name(resource_id)
            
        if not resource:
            raise click.ClickException(f"{resource_type.upper()} '{resource_id}' not found.")
            
        # If node is specified, check that it matches
        if node and resource['node'] != node:
            raise click.ClickException(
                f"{resource_type.upper()} '{resource_id}' exists on node '{resource['node']}', "
                f"not on specified node '{node}'."
            )
            
        return resource['vmid'], resource['node']

# Import commands from separate files to register with Click
from pyadm.pvecli.vm_commands import *
from pyadm.pvecli.container_commands import *
from pyadm.pvecli.node_commands import *
from pyadm.pvecli.storage_commands import *