import click
import json
import sys
import os
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client, selected_pve


@pvecli.group("ct")
def container():
    """
    Manage containers (LXC) on Proxmox VE.
    """
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
        
        # Check if vmid is numeric (ID) or name
        try:
            vm_id = int(vmid)
            is_id = True
        except ValueError:
            is_id = False
            
        if is_id:
            # If node is not provided, try to find it
            if not node:
                for ct in client.get_containers():
                    if ct['vmid'] == vm_id:
                        node = ct['node']
                        break
                        
            if not node:
                raise click.ClickException(f"Could not find node for container ID {vm_id}. Please specify with --node.")
                
            # Get status using ID
            status = client.get_container_status(node, vm_id)
            
        else:
            # Get container by name
            container = client.find_container_by_name(vmid)
            if not container:
                raise click.ClickException(f"Container '{vmid}' not found.")
                
            # Get status using found info
            status = client.get_container_status(container['node'], container['vmid'])
            
        if json_output:
            click.echo(json.dumps(status, indent=2))
        else:
            # Format and display status
            click.echo(f"Container: {vmid}")
            click.echo(f"Status: {status.get('status', 'unknown')}")
            click.echo(f"Node: {node or container['node']}")
            
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
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if container name is unique)")
def start_container(vmid, node):
    """
    Start a container by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Check if vmid is numeric (ID) or name
        try:
            vm_id = int(vmid)
            is_id = True
        except ValueError:
            is_id = False
            
        if is_id:
            # If node is not provided, try to find it
            if not node:
                for ct in client.get_containers():
                    if ct['vmid'] == vm_id:
                        node = ct['node']
                        break
                        
            if not node:
                raise click.ClickException(f"Could not find node for container ID {vm_id}. Please specify with --node.")
                
            # Start container using ID
            result = client.start_container(node, vm_id)
            
        else:
            # Get container by name
            container = client.find_container_by_name(vmid)
            if not container:
                raise click.ClickException(f"Container '{vmid}' not found.")
                
            # Start container using found info
            result = client.start_container(container['node'], container['vmid'])
            
        click.echo(f"Container '{vmid}' start initiated. Task ID: {result.get('data')}")
                
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
        
        # Check if vmid is numeric (ID) or name
        try:
            vm_id = int(vmid)
            is_id = True
        except ValueError:
            is_id = False
            
        if is_id:
            # If node is not provided, try to find it
            if not node:
                for ct in client.get_containers():
                    if ct['vmid'] == vm_id:
                        node = ct['node']
                        break
                        
            if not node:
                raise click.ClickException(f"Could not find node for container ID {vm_id}. Please specify with --node.")
                
            # Stop container using ID
            result = client.stop_container(node, vm_id)
            
        else:
            # Get container by name
            container = client.find_container_by_name(vmid)
            if not container:
                raise click.ClickException(f"Container '{vmid}' not found.")
                
            # Stop container using found info
            result = client.stop_container(container['node'], container['vmid'])
            
        click.echo(f"Container '{vmid}' stop initiated. Task ID: {result.get('data')}")
                
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