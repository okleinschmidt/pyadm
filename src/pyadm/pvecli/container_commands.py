import click
import json
import sys
import os
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client, selected_pve, resolve_resource_id


@pvecli.group("ct", context_settings={'help_option_names': ['-h', '--help']})
def container():
    """Manage containers (LXC) on Proxmox VE."""
    pass


@container.command("list")
@click.option("--node", "-n", default=None, help="Filter by node name")
@click.option("--status", "-s", default=None, help="Filter by status (running, stopped)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
def list_containers(node, status, json_output, output):
    """
    List containers.
    """
    try:
        client = get_pve_client()
        containers = client.get_containers(node)
        
        # Filter by status if requested
        if status:
            containers = [c for c in containers if c.get('status') == status]
            
        if json_output:
            click.echo(json.dumps(containers, indent=2))
            return
        
        # Determine fields to display
        fields = ['vmid', 'name', 'status', 'node', 'maxmem']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for container in containers:
            row = []
            for field in fields:
                if field in container:
                    if field == 'maxmem' and isinstance(container[field], int):
                        # Convert bytes to MB for memory
                        row.append(f"{container[field] / (1024**2):.0f} MB")
                    else:
                        row.append(container[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing containers: {e}")
        raise click.ClickException(f"Error listing containers: {e}")


@container.command("status")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if container name is unique)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def get_container_status(vmid, node, json_output):
    """
    Get status of a container by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve container ID and node
        ct_id, node = resolve_resource_id(client, vmid, node, "container")
            
        # Get status
        status = client.get_container_status(node, ct_id)
        
        if json_output:
            click.echo(json.dumps(status, indent=2))
        else:
            # Format and display status
            click.echo(f"Container: {vmid}")
            click.echo(f"Status: {status.get('status', 'unknown')}")
            click.echo(f"Node: {node}")
            
            # Display additional details
            if 'cpus' in status:
                click.echo(f"CPUs: {status['cpus']}")
            if 'maxmem' in status:
                mem_mb = status['maxmem'] / (1024**2)
                click.echo(f"Memory: {mem_mb:.0f} MB")
            if 'uptime' in status and status['uptime']:
                uptime_hours = status['uptime'] / 3600
                click.echo(f"Uptime: {uptime_hours:.2f} hours")
                
    except Exception as e:
        logging.error(f"Error getting container status: {e}")
        raise click.ClickException(f"Error getting container status: {e}")


@container.command("start")
@click.argument("ctid")
@click.option("--node", "-n", default=None, help="Node name (not needed if container name is unique)")
def start_container(ctid, node):
    """
    Start a container by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve container ID and node
        ct_id, node = resolve_resource_id(client, ctid, node, "container")
                
        # Start container
        result = client.start_container(node, ct_id)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"Container '{ctid}' start initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error starting container: {e}")
        raise click.ClickException(f"Error starting container: {e}")


@container.command("stop")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if container name is unique)")
def stop_container(vmid, node):
    """
    Stop a container by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve container ID and node
        ct_id, node = resolve_resource_id(client, vmid, node, "container")
            
        # Stop container
        result = client.stop_container(node, ct_id)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"Container '{vmid}' stop initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error stopping container: {e}")
        raise click.ClickException(f"Error stopping container: {e}")


@container.command("list-templates")
@click.option("--node", "-n", required=True, help="Node name where templates are stored")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def list_templates(node, json_output):
    """
    List available container templates on a node.
    """
    try:
        client = get_pve_client()
        templates = client.get_templates(node)
        
        if not templates:
            click.echo(f"No templates found on node '{node}'")
            return
            
        if json_output:
            click.echo(json.dumps(templates, indent=2))
            return
        
        # Create table data
        headers = ['Name', 'Size', 'Format', 'Storage']
        table_data = []
        for template in templates:
            # Extract the template name from the volid (format: storage:vztmpl/template.tar.gz)
            template_name = template.get('volid', '')
            if ':vztmpl/' in template_name:
                template_name = template_name.split(':vztmpl/')[1]
            
            size_mb = template.get('size', 0) / (1024**2) if 'size' in template else 0
            row = [
                template_name,
                f"{size_mb:.2f} MB",
                template.get('format', ''),
                template.get('storage', '')
            ]
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=headers))
        
    except Exception as e:
        logging.error(f"Error listing templates: {e}")
        raise click.ClickException(f"Error listing templates: {e}")


@container.command("create")
@click.option("--node", "-n", required=True, help="Node name where container will be created")
@click.option("--name", required=True, help="Name of the container")
@click.option("--template", required=True, help="Container template (list available with list-templates)")
@click.option("--memory", default=512, help="Memory in MB (default: 512)")
@click.option("--swap", default=0, help="Swap memory in MB (default: 0)")
@click.option("--cores", default=1, help="Number of CPU cores (default: 1)")
@click.option("--disk", default="8G", help="Disk size (e.g., '8G', '20G') (default: 8G)")
@click.option("--storage", default="local", help="Storage for container disk (default: local)")
@click.option("--password", help="Root password (if not set, will be prompted)")
@click.option("--ssh-public-keys", help="Path to SSH public keys file")
@click.option("--net0", help="Network config (e.g. 'name=eth0,bridge=vmbr0,ip=dhcp')")
@click.option("--vmid", type=int, help="Container ID (auto-generated if not specified)")
@click.option("--start/--no-start", default=False, help="Start container after creation (default: no)")
@click.option("--unprivileged/--privileged", default=True, help="Create as unprivileged container (default: unprivileged)")
def create_ct_command(node, name, template, memory, swap, cores, disk, storage, password, 
                      ssh_public_keys, net0, vmid, start, unprivileged):
    """
    Create a new container.
    """
    try:
        client = get_pve_client()
        
        # Verify template exists
        templates = client.get_templates(node)
        template_ids = [t.get('volid', '') for t in templates]
        
        if template not in template_ids:
            click.echo(f"Warning: Template '{template}' not found. Available templates:")
            for t in template_ids:
                click.echo(f"  - {t}")
            if not click.confirm("Continue with container creation?"):
                return
        
        # Get next VMID if not specified
        if not vmid:
            vmid = client.get_next_vmid()
            click.echo(f"Using next available VMID: {vmid}")
        
        # Prompt for password if not provided
        if not password:
            password = click.prompt("Enter root password", hide_input=True, confirmation_prompt=True)
        
        # Prepare container creation parameters
        params = {
            'vmid': vmid,
            'hostname': name,
            'memory': memory,
            'swap': swap,
            'cores': cores,
            'ostemplate': template,
            'storage': storage,
            'rootfs': f"{storage}:{disk}",
            'password': password,
            'unprivileged': 1 if unprivileged else 0,
        }
        
        # Add network config if provided
        if net0:
            params['net0'] = net0
        else:
            params['net0'] = 'name=eth0,bridge=vmbr0,ip=dhcp'
            
        # Add SSH keys if provided
        if ssh_public_keys:
            try:
                with open(os.path.expanduser(ssh_public_keys), 'r') as f:
                    ssh_keys = f.read()
                params['ssh-public-keys'] = ssh_keys
            except Exception as e:
                click.echo(f"Warning: Could not read SSH keys file: {e}")
                if not click.confirm("Continue without SSH keys?"):
                    return
            
        # Confirm creation
        click.echo("\nContainer will be created with the following parameters:")
        for key, value in params.items():
            if key != 'password':  # Don't show the password
                click.echo(f"{key}: {value}")
            
        if not click.confirm("\nProceed with container creation?"):
            click.echo("Container creation cancelled.")
            return
            
        # Create container
        result = client.create_container(node, params)
        
        click.echo(f"Container creation initiated. Task ID: {result.get('data')}")
        
        # Start container if requested
        if start:
            click.echo("Starting container...")
            client.start_container(node, vmid)
            
    except Exception as e:
        logging.error(f"Error creating container: {e}")
        raise click.ClickException(f"Error creating container: {e}")


@container.command("migrate")
@click.argument("ctid")
@click.option("--target", "-t", required=True, help="Target node name")
@click.option("--node", "-n", default=None, help="Source node name (not needed if container name is unique)")
@click.option("--online", is_flag=True, help="Perform online migration (container stays running)")
@click.option("--restart", is_flag=True, help="Restart container after migration")
def migrate_container(ctid, target, node, online, restart):
    """
    Migrate a container to another node.
    
    CTID: Container ID or name to migrate
    
    Supports both offline and online migration. Online migration
    keeps the container running during the migration process.
    
    \b
    Examples:
        pyadm pve ct migrate 200 --target node2           # Offline migration
        pyadm pve ct migrate web-ct --target node2        # Migrate by name
        pyadm pve ct migrate 200 --target node2 --online  # Online migration
        pyadm pve ct migrate 200 --target node2 --restart # Restart after migration
    """
    try:
        client = get_pve_client()
        
        # Resolve container ID and source node
        ct_id, source_node = resolve_resource_id(client, ctid, node, "container")
        
        # Prepare migration options
        options = {
            'target': target
        }
        
        if online:
            options['online'] = 1
            
        if restart:
            options['restart'] = 1
            
        # Perform migration
        result = client.migrate_container(source_node, ct_id, **options)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result
            
        migration_type = "online" if online else "offline"
        click.echo(f"Container '{ctid}' {migration_type} migration from '{source_node}' to '{target}' initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error migrating container: {e}")
        raise click.ClickException(f"Error migrating container: {e}")


@container.command("config")
@click.argument("ctid")
@click.option("--node", "-n", default=None, help="Source node name (not needed if container name is unique)")
@click.option("--set", "set_configs", multiple=True, help="Set configuration option (format: key=value)")
@click.option("--delete", "delete_configs", multiple=True, help="Delete configuration option")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output configuration as JSON")
def config_container(ctid, node, set_configs, delete_configs, show, json_output):
    """
    Configure a container.
    
    CTID: Container ID or name to configure
    
    View current configuration or modify container settings such as memory,
    CPU cores, network interfaces, mount points, and more.
    
    \b
    Examples:
        pyadm pve ct config 200 --show                     # Show current config
        pyadm pve ct config web-ct --show --json           # Show as JSON
        pyadm pve ct config 200 --set "memory=2048"        # Set 2GB RAM
        pyadm pve ct config 200 --set "cores=2"            # Set 2 CPU cores
        pyadm pve ct config 200 --set "memory=4096" --set "cores=4"  # Multiple settings
        pyadm pve ct config 200 --delete "net1"            # Remove network interface
        pyadm pve ct config 200 --set "net1=name=eth1,bridge=vmbr1"  # Add network interface
    """
    try:
        client = get_pve_client()
        
        # Resolve container ID and node
        ct_id, ct_node = resolve_resource_id(client, ctid, node, "container")
        
        # If only showing configuration
        if show or (not set_configs and not delete_configs):
            config = client.get_container_config(ct_node, ct_id)
            
            if json_output:
                click.echo(json.dumps(config, indent=2))
            else:
                click.echo(f"Configuration for Container '{ctid}' (ID: {ct_id}) on node '{ct_node}':")
                click.echo("=" * 60)
                
                # Group and display configuration options
                basic_config = {}
                storage_config = {}
                network_config = {}
                other_config = {}
                
                for key, value in config.items():
                    if key in ['memory', 'cores', 'cpulimit', 'cpuunits', 'swap', 'hostname', 'ostype']:
                        basic_config[key] = value
                    elif key.startswith(('mp', 'rootfs')):
                        storage_config[key] = value
                    elif key.startswith('net'):
                        network_config[key] = value
                    else:
                        other_config[key] = value
                
                if basic_config:
                    click.echo("\nBasic Configuration:")
                    for key, value in sorted(basic_config.items()):
                        click.echo(f"  {key}: {value}")
                
                if storage_config:
                    click.echo("\nStorage Configuration:")
                    for key, value in sorted(storage_config.items()):
                        click.echo(f"  {key}: {value}")
                
                if network_config:
                    click.echo("\nNetwork Configuration:")
                    for key, value in sorted(network_config.items()):
                        click.echo(f"  {key}: {value}")
                
                if other_config:
                    click.echo("\nOther Configuration:")
                    for key, value in sorted(other_config.items()):
                        click.echo(f"  {key}: {value}")
            return
        
        # Prepare configuration changes
        config_updates = {}
        
        # Handle set operations
        for config_item in set_configs:
            if "=" not in config_item:
                raise click.ClickException(f"Invalid set format. Use 'key=value'. Got: {config_item}")
            key, value = config_item.split("=", 1)
            config_updates[key.strip()] = value.strip()
        
        # Handle delete operations
        for key in delete_configs:
            config_updates[key.strip()] = ""  # Empty value deletes the option
        
        if config_updates:
            # Apply configuration changes
            result = client.set_container_config(ct_node, ct_id, config_updates)
            
            # Handle both string and dictionary results
            if isinstance(result, dict):
                task_id = result.get('data', 'Unknown')
            else:
                task_id = result
            
            click.echo(f"Container '{ctid}' configuration updated. Task ID: {task_id}")
            
            # Show what was changed
            for key, value in config_updates.items():
                if value == "":
                    click.echo(f"  Deleted: {key}")
                else:
                    click.echo(f"  Set: {key} = {value}")
        else:
            click.echo("No configuration changes specified.")
                
    except Exception as e:
        logging.error(f"Error configuring container: {e}")
        raise click.ClickException(f"Error configuring container: {e}")