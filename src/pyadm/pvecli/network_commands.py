import click
import json
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client, selected_pve


@pvecli.group("network")
def network():
    """
    Manage network interfaces on Proxmox VE.
    """
    pass


@network.command("list")
@click.option("--node", "-n", required=True, help="Node name")
@click.option("--type", "-t", default=None, help="Filter by interface type (bridge, bond, etc.)")
@click.option("--active", is_flag=True, help="Show only active interfaces")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
def list_interfaces(node, type, active, json_output, output):
    """
    List network interfaces on a node.
    """
    try:
        client = get_pve_client()
        interfaces = client.get_network_interfaces(node)
        
        # Filter by type if requested
        if type:
            interfaces = [iface for iface in interfaces if iface.get('type') == type]
            
        # Filter by active status if requested
        if active:
            interfaces = [iface for iface in interfaces if iface.get('active')]
            
        if json_output:
            click.echo(json.dumps(interfaces, indent=2))
            return
        
        # Determine fields to display
        fields = ['iface', 'type', 'active', 'method', 'address', 'netmask', 'gateway', 'bridge_ports']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for iface in interfaces:
            row = []
            for field in fields:
                if field in iface:
                    if field == 'active':
                        row.append("Yes" if iface[field] else "No")
                    else:
                        row.append(iface[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing network interfaces: {e}")
        raise click.ClickException(f"Error listing network interfaces: {e}")


@network.command("bridges")
@click.option("--node", "-n", required=True, help="Node name")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def list_bridges(node, json_output):
    """
    List network bridges on a node.
    """
    try:
        client = get_pve_client()
        interfaces = client.get_network_interfaces(node)
        
        # Filter only bridges
        bridges = [iface for iface in interfaces if iface.get('type') == 'bridge']
        
        if json_output:
            click.echo(json.dumps(bridges, indent=2))
            return
        
        # Define bridge-specific fields
        fields = ['iface', 'active', 'method', 'address', 'bridge_ports', 'comments']
        
        # Create table data
        table_data = []
        for bridge in bridges:
            row = []
            for field in fields:
                if field in bridge:
                    if field == 'active':
                        row.append("Yes" if bridge[field] else "No")
                    else:
                        row.append(bridge[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing network bridges: {e}")
        raise click.ClickException(f"Error listing network bridges: {e}")


@network.command("show")
@click.argument("interface")
@click.option("--node", "-n", required=True, help="Node name")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def show_interface(interface, node, json_output):
    """
    Show details of a specific network interface.
    
    INTERFACE is the name of the interface (e.g., vmbr0, eth0)
    """
    try:
        client = get_pve_client()
        config = client.get_network_config(node, interface)
        
        if json_output:
            click.echo(json.dumps(config, indent=2))
            return
        
        # Display interface details
        click.echo(f"Interface: {interface}")
        click.echo(f"Node: {node}")
        click.echo(f"Type: {config.get('type', 'unknown')}")
        click.echo(f"Active: {'Yes' if config.get('active') else 'No'}")
        
        # Display additional details
        additional_fields = [
            'method', 'address', 'netmask', 'gateway', 'comments', 
            'bridge_ports', 'autostart', 'mtu', 'vlan-raw-device', 'vlan-id'
        ]
        
        for field in additional_fields:
            if field in config and config[field]:
                click.echo(f"{field.capitalize()}: {config[field]}")
                
    except Exception as e:
        logging.error(f"Error getting interface details: {e}")
        raise click.ClickException(f"Error getting interface details: {e}")


@network.command("create-bridge")
@click.option("--node", "-n", required=True, help="Node name")
@click.option("--name", required=True, help="Bridge name (e.g., vmbr1)")
@click.option("--ports", help="Physical interfaces to include in bridge (comma-separated)")
@click.option("--address", help="IP address")
@click.option("--netmask", help="Network mask")
@click.option("--gateway", help="Gateway")
@click.option("--method", default="manual", help="Address assignment method (static, manual, dhcp)")
@click.option("--autostart/--no-autostart", default=True, help="Start on boot")
@click.option("--comments", help="Comments")
@click.option("--mtu", type=int, help="MTU")
@click.option("--vlan", type=int, help="VLAN tag")
def create_bridge_command(node, name, ports, address, netmask, gateway, method,
                    autostart, comments, mtu, vlan):
    """
    Create a new network bridge on a node.
    """
    try:
        client = get_pve_client()
        
        # Prepare bridge parameters
        params = {
            'iface': name,
            'type': 'bridge',
            'autostart': 1 if autostart else 0,
            'method': method
        }
        
        # Add optional parameters if provided
        if ports:
            params['bridge_ports'] = ports
        if address:
            params['address'] = address
        if netmask:
            params['netmask'] = netmask
        if gateway:
            params['gateway'] = gateway
        if comments:
            params['comments'] = comments
        if mtu:
            params['mtu'] = mtu
        if vlan:
            params['vlan-id'] = vlan
            
        # Confirm creation
        click.echo(f"\nCreating network bridge '{name}' on node '{node}' with parameters:")
        for key, value in params.items():
            click.echo(f"{key}: {value}")
            
        if not click.confirm("\nProceed with bridge creation?"):
            click.echo("Bridge creation cancelled.")
            return
            
        # Create bridge
        result = client.create_bridge(node, params)
        
        click.echo(f"Bridge creation initiated. Restart network to apply.")
        if not click.confirm("Apply network changes now?"):
            click.echo("Please apply network changes manually when ready.")
            return
            
        # Apply network changes
        apply_result = client.apply_network_changes(node)
        click.echo(f"Network changes applied. Task ID: {apply_result.get('data')}")
        
    except Exception as e:
        logging.error(f"Error creating bridge: {e}")
        raise click.ClickException(f"Error creating bridge: {e}")


@network.command("delete")
@click.argument("interface")
@click.option("--node", "-n", required=True, help="Node name")
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
def delete_interface(interface, node, force):
    """
    Delete a network interface from a node.
    
    INTERFACE is the name of the interface to delete.
    """
    try:
        client = get_pve_client()
        
        # Confirm deletion unless forced
        if not force:
            if not click.confirm(f"Are you sure you want to delete interface '{interface}' on node '{node}'?"):
                click.echo("Deletion cancelled.")
                return
                
        # Delete interface
        result = client.delete_network_interface(node, interface)
        
        click.echo(f"Interface deletion initiated. Restart network to apply.")
        if not click.confirm("Apply network changes now?"):
            click.echo("Please apply network changes manually when ready.")
            return
            
        # Apply network changes
        apply_result = client.apply_network_changes(node)
        click.echo(f"Network changes applied. Task ID: {apply_result.get('data')}")
        
    except Exception as e:
        logging.error(f"Error deleting interface: {e}")
        raise click.ClickException(f"Error deleting interface: {e}")


@network.command("apply")
@click.option("--node", "-n", required=True, help="Node name")
def apply_changes(node):
    """
    Apply pending network changes on a node.
    """
    try:
        client = get_pve_client()
        
        # Confirm application
        if not click.confirm(f"Apply all pending network changes on node '{node}'?"):
            click.echo("Operation cancelled.")
            return
            
        # Apply network changes
        result = client.apply_network_changes(node)
        
        click.echo(f"Network changes applied. Task ID: {result.get('data')}")
        
    except Exception as e:
        logging.error(f"Error applying network changes: {e}")
        raise click.ClickException(f"Error applying network changes: {e}")


@network.command("config")
@click.option("--node", "-n", required=True, help="Node name")
def show_config(node):
    """
    Show the network configuration file of a node.
    """
    try:
        client = get_pve_client()
        
        # Get config
        config = client.get_network_config_file(node)
        
        # Print config file
        if 'data' in config:
            click.echo(config['data'])
        else:
            click.echo("No network configuration found.")
        
    except Exception as e:
        logging.error(f"Error getting network configuration: {e}")
        raise click.ClickException(f"Error getting network configuration: {e}")