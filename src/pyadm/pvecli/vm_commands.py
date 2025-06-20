import json
import click
import logging
import json
import click
import logging
from tabulate import tabulate
from pyadm.pvecli.pve_commands import pvecli, get_pve_client, selected_pve, resolve_resource_id


@pvecli.group("vm", context_settings={'help_option_names': ['-h', '--help']})
def vm():
    """Manage virtual machines on Proxmox VE."""
    pass


@vm.command("list")
@click.option("--node", "-n", default=None, help="Filter by node name")
@click.option("--status", "-s", default=None, help="Filter by status (running, stopped)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
@click.option("--include-templates", is_flag=True, help="Include VM templates in list")
def list_vms(node, status, json_output, output, include_templates):
    """
    List virtual machines.
    """
    try:
        client = get_pve_client()
        
        # If a specific node is requested, check if it's online first
        if node:
            nodes = client.get_nodes()
            node_info = next((n for n in nodes if n['node'] == node), None)
            
            if not node_info:
                raise click.ClickException(f"Node '{node}' not found in cluster.")
                
            if node_info.get('status') != 'online':
                raise click.ClickException(f"Node '{node}' is offline. Cannot retrieve VMs.")
        
        # Get VMs, either all or just regular ones
        if include_templates:
            vms = client.get_vms(node)
        else:
            vms = client.get_vms(node)
            # Filter out templates (VMs with template=1)
            vms = [vm for vm in vms if not vm.get('template', 0)]
        
        # Filter by status if requested
        if status:
            vms = [vm for vm in vms if vm.get('status') == status]
            
        if json_output:
            click.echo(json.dumps(vms, indent=2))
            return
        
        # Determine fields to display
        fields = ['vmid', 'name', 'status', 'node', 'cpu', 'maxmem']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for vm in vms:
            row = []
            for field in fields:
                if field in vm:
                    if field == 'maxmem' and isinstance(vm[field], int):
                        # Convert bytes to GB for memory
                        row.append(f"{vm[field] / (1024**3):.2f} GB")
                    else:
                        row.append(vm[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing VMs: {e}")
        raise click.ClickException(f"Error listing VMs: {e}")


@vm.command("status")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if VM name is unique)")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
def get_vm_status(vmid, node, json_output):
    """
    Get status of a virtual machine by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve VM ID and node
        vm_id, node = resolve_resource_id(client, vmid, node, "vm")
            
        # Get status
        status = client.get_vm_status(node, vm_id)
            
        if json_output:
            click.echo(json.dumps(status, indent=2))
        else:
            # Format and display status
            click.echo(f"VM: {vmid}")
            click.echo(f"Status: {status.get('status', 'unknown')}")
            click.echo(f"Node: {node}")
            
            # Display additional details
            if 'cpus' in status:
                click.echo(f"CPUs: {status['cpus']}")
            if 'maxmem' in status:
                mem_gb = status['maxmem'] / (1024**3)
                click.echo(f"Memory: {mem_gb:.2f} GB")
            if 'uptime' in status and status['uptime']:
                # Format uptime
                uptime_seconds = status['uptime']
                days = uptime_seconds // 86400
                hours = (uptime_seconds % 86400) // 3600
                minutes = (uptime_seconds % 3600) // 60
                uptime_str = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
                click.echo(f"Uptime: {uptime_str}")
                
    except Exception as e:
        logging.error(f"Error getting VM status: {e}")
        raise click.ClickException(f"Error getting VM status: {e}")


@vm.command("start")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if VM name is unique)")
def start_vm(vmid, node):
    """
    Start a virtual machine by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve VM ID and node
        vm_id, node = resolve_resource_id(client, vmid, node, "vm")
                
        # Start VM
        result = client.start_vm(node, vm_id)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"VM '{vmid}' start initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error starting VM: {e}")
        raise click.ClickException(f"Error starting VM: {e}")


@vm.command("stop")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if VM name is unique)")
def stop_vm(vmid, node):
    """
    Stop a virtual machine by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve VM ID and node
        vm_id, node = resolve_resource_id(client, vmid, node, "vm")
            
        # Stop VM
        result = client.stop_vm(node, vm_id)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"VM '{vmid}' stop initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error stopping VM: {e}")
        raise click.ClickException(f"Error stopping VM: {e}")


@vm.command("shutdown")
@click.argument("vmid")
@click.option("--node", "-n", default=None, help="Node name (not needed if VM name is unique)")
def shutdown_vm(vmid, node):
    """
    Gracefully shut down a virtual machine by ID or name.
    """
    try:
        client = get_pve_client()
        
        # Resolve VM ID and node
        vm_id, node = resolve_resource_id(client, vmid, node, "vm")
            
        # Shutdown VM
        result = client.shutdown_vm(node, vm_id)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"VM '{vmid}' graceful shutdown initiated. Task ID: {task_id}")
                
    except Exception as e:
        logging.error(f"Error shutting down VM: {e}")
        raise click.ClickException(f"Error shutting down VM: {e}")


@vm.command("create")
@click.option("--node", "-n", required=True, help="Node name where VM will be created")
@click.option("--name", required=True, help="Name of the VM")
@click.option("--memory", default=1024, help="Memory in MB (default: 1024)")
@click.option("--cores", default=1, help="Number of CPU cores (default: 1)")
@click.option("--disk", required=True, help="Disk size (e.g., '10G', '50G')")
@click.option("--storage", default="local", help="Storage for VM disk (default: local)")
@click.option("--iso", help="ISO image for installation")
@click.option("--net-model", default="virtio", help="Network model (default: virtio)")
@click.option("--net-bridge", default="vmbr0", help="Network bridge (default: vmbr0)")
@click.option("--vmid", type=int, help="VM ID (auto-generated if not specified)")
@click.option("--start/--no-start", default=False, help="Start VM after creation (default: no)")
def create_vm_command(node, name, memory, cores, disk, storage, iso, net_model, net_bridge, vmid, start):
    """
    Create a new virtual machine.
    """
    try:
        client = get_pve_client()
        
        # If ISO is specified, show available ISOs if it doesn't exist
        if iso:
            isos = client.get_available_isos(node)
            iso_names = [i.get('volid', '') for i in isos]
            
            if iso not in iso_names:
                click.echo(f"Warning: ISO '{iso}' not found. Available ISOs:")
                for available_iso in iso_names:
                    click.echo(f"  - {available_iso}")
                if not click.confirm("Continue with VM creation?"):
                    return
        
        # Get next VMID if not specified
        if not vmid:
            vmid = client.get_next_vmid()
            click.echo(f"Using next available VMID: {vmid}")
        
        # Prepare VM creation parameters
        params = {
            'vmid': vmid,
            'name': name,
            'memory': memory,
            'cores': cores,
            'sockets': 1,
            'net0': f"{net_model}={net_bridge}",
            'ostype': 'l26',  # Linux 2.6+ kernel
        }
        
        # Add disk
        params[f'scsi0'] = f"{storage}:{disk}"
        
        # Add ISO if specified
        if iso:
            params['ide2'] = f"{iso},media=cdrom"
            params['boot'] = 'order=ide2;scsi0'
            
        # Confirm creation
        click.echo("\nVM will be created with the following parameters:")
        for key, value in params.items():
            click.echo(f"{key}: {value}")
            
        if not click.confirm("\nProceed with VM creation?"):
            click.echo("VM creation cancelled.")
            return
            
        # Create VM
        result = client.create_vm(node, params)
        
        click.echo(f"VM creation initiated. Task ID: {result.get('data')}")
        
        # Start VM if requested
        if start:
            click.echo("Starting VM...")
            client.start_vm(node, vmid)
            
    except Exception as e:
        logging.error(f"Error creating VM: {e}")
        raise click.ClickException(f"Error creating VM: {e}")


@vm.command("list-templates")
@click.option("--node", "-n", default=None, help="Filter by node name")
@click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
@click.option("--output", "-o", default=None, help="Comma-separated list of fields to display")
def list_vm_templates(node, json_output, output):
    """
    List VM templates.
    """
    try:
        client = get_pve_client()
        
        # If a specific node is requested, check if it's online first
        if node:
            nodes = client.get_nodes()
            node_info = next((n for n in nodes if n['node'] == node), None)
            
            if not node_info:
                raise click.ClickException(f"Node '{node}' not found in cluster.")
                
            if node_info.get('status') != 'online':
                raise click.ClickException(f"Node '{node}' is offline. Cannot retrieve templates.")
        
        # Get VM templates
        templates = client.get_vm_templates()
        
        # Filter by node if specified
        if node:
            templates = [tpl for tpl in templates if tpl.get('node') == node]
        
        if not templates:
            click.echo(f"No VM templates found" + (f" on node '{node}'" if node else ""))
            return
            
        if json_output:
            click.echo(json.dumps(templates, indent=2))
            return
        
        # Determine fields to display
        fields = ['vmid', 'name', 'node', 'cpu', 'maxmem']
        if output:
            fields = output.split(',')
        
        # Create table data
        table_data = []
        for template in templates:
            row = []
            for field in fields:
                if field in template:
                    if field == 'maxmem' and isinstance(template[field], int):
                        # Convert bytes to GB for memory
                        row.append(f"{template[field] / (1024**3):.2f} GB")
                    else:
                        row.append(template[field])
                else:
                    row.append("")
            table_data.append(row)
        
        # Print table
        click.echo(tabulate(table_data, headers=fields))
        
    except Exception as e:
        logging.error(f"Error listing VM templates: {e}")
        raise click.ClickException(f"Error listing VM templates: {e}")


@vm.command("clone")
@click.argument("source_vmid")
@click.option("--name", required=True, help="Name for the new VM")
@click.option("--node", "-n", default=None, help="Node name where source VM is located")
@click.option("--target-node", default=None, help="Target node for the new VM (defaults to same as source)")
@click.option("--storage", default=None, help="Target storage for the new VM's disks")
@click.option("--full", is_flag=True, help="Create a full clone (instead of linked clone)")
@click.option("--vmid", type=int, help="VM ID for the new VM (auto-generated if not specified)")
@click.option("--start/--no-start", default=False, help="Start VM after cloning (default: no)")
def clone_vm_command(source_vmid, name, node, target_node, storage, full, vmid, start):
    """
    Clone a VM or VM template.
    
    SOURCE_VMID can be either a VM ID or VM name (if name is unique).
    """
    try:
        client = get_pve_client()
        
        # Resolve source VM ID and node
        source_id, source_node = resolve_resource_id(client, source_vmid, node, "vm")
        
        # Get next VMID if not specified
        if not vmid:
            vmid = client.get_next_vmid()
            click.echo(f"Using next available VMID: {vmid}")
        
        # Set target node to source node if not specified
        if not target_node:
            target_node = source_node
            
        # Prepare clone parameters
        params = {
            'newid': vmid,
            'name': name,
            'full': 1 if full else 0,
        }
        
        if target_node and target_node != source_node:
            params['target'] = target_node
            
        if storage:
            params['storage'] = storage
            
        # Confirm cloning
        confirm_msg = f"Clone VM '{source_vmid}' (ID: {source_id}) to new VM '{name}' (ID: {vmid})"
            
        if target_node and target_node != source_node:
            confirm_msg += f" on node '{target_node}'"
            
        if full:
            confirm_msg += " as a full clone"
        else:
            confirm_msg += " as a linked clone"
            
        if not click.confirm(confirm_msg + "?"):
            click.echo("VM cloning cancelled.")
            return
            
        # Clone VM
        result = client.clone_vm(source_node, source_id, params)
        
        # Handle both string and dictionary results
        if isinstance(result, dict):
            task_id = result.get('data', 'Unknown')
        else:
            task_id = result  # Assume result is a string containing task ID
            
        click.echo(f"VM clone initiated. Task ID: {task_id}")
        
        # Start VM if requested
        if start:
            click.echo("Waiting for clone to finish before starting...")
            click.echo("Warning: Starting immediately may fail if clone is not complete.")
            start_result = client.start_vm(target_node or source_node, vmid)
            
            # Handle both string and dictionary results for start operation
            if isinstance(start_result, dict):
                start_task_id = start_result.get('data', 'Unknown')
            else:
                start_task_id = start_result
                
            click.echo(f"VM start initiated. Task ID: {start_task_id}")
            
    except Exception as e:
        logging.error(f"Error cloning VM: {e}")
        raise click.ClickException(f"Error cloning VM: {e}")