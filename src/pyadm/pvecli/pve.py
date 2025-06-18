import logging
import re
from typing import Dict, List, Optional, Any, Union
from proxmoxer import ProxmoxAPI
import requests

class PVEClient:
    """
    Client for Proxmox Virtual Environment API.
    """
    def __init__(self, config: Dict[str, str], debug: bool = False):
        """
        Initialize PVE client with configuration.
        
        Args:
            config: Configuration dictionary with connection parameters
            debug: Enable debug output
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.debug = debug
        self._api = None
        self._online_nodes = None
    
    @property
    def api(self) -> ProxmoxAPI:
        """Get or create the API connection."""
        if self._api is None:
            self._connect()
        return self._api
    
    def _connect(self) -> None:
        """Connect to Proxmox API."""
        host = self.config.get('host', 'localhost')
        port = self.config.get('port', '8006')
        user = self.config.get('user', 'root@pam')
        password = self.config.get('password', '')
        token_name = self.config.get('token_name', '')
        token_value = self.config.get('token_value', '')
        verify_ssl = self.config.get('verify_ssl', 'true').lower() == 'true'
        
        # Show connection info in debug mode
        if self.debug:
            self.logger.debug(f"Connecting to Proxmox VE at {host}:{port}")
            self.logger.debug(f"User: {user}")
            self.logger.debug(f"Using token: {bool(token_name)}")
            self.logger.debug(f"Verify SSL: {verify_ssl}")
        
        try:
            if token_name and token_value:
                # Connect with API token
                self._api = ProxmoxAPI(
                    host=host,
                    port=port,
                    user=user,
                    token_name=token_name,
                    token_value=token_value,
                    verify_ssl=verify_ssl
                )
            else:
                # Connect with password
                self._api = ProxmoxAPI(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    verify_ssl=verify_ssl
                )
            self.logger.debug(f"Connected to Proxmox VE at {host}:{port}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Proxmox VE: {e}")
            raise
    
    def get_nodes(self) -> List[Dict[str, Any]]:
        """
        Get list of all nodes.
        
        Returns:
            List of node dictionaries
        """
        try:
            return self.api.nodes.get()
        except Exception as e:
            self.logger.error(f"Error getting nodes: {e}")
            raise
    
    def get_online_nodes(self) -> List[str]:
        """
        Get list of nodes that are currently online.
        
        Returns:
            List of online node names
        """
        if self._online_nodes is None:
            try:
                nodes = self.get_nodes()
                self._online_nodes = [node['node'] for node in nodes if node.get('status') == 'online']
                if self.debug:
                    self.logger.debug(f"Online nodes: {', '.join(self._online_nodes)}")
                    offline_nodes = [node['node'] for node in nodes if node.get('status') != 'online']
                    if offline_nodes:
                        self.logger.debug(f"Offline nodes: {', '.join(offline_nodes)}")
            except Exception as e:
                self.logger.error(f"Error determining online nodes: {e}")
                return []
        return self._online_nodes
    
    def get_node_status(self, node: str) -> Dict[str, Any]:
        """
        Get status of a specific node.
        
        Args:
            node: Node name
            
        Returns:
            Node status dictionary
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                return {'status': 'offline', 'node': node}
                
            return self.api.nodes(node).status.get()
        except Exception as e:
            self.logger.error(f"Error getting status for node '{node}': {e}")
            raise
    
    def get_vms(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all VMs, optionally filtered by node.
        
        Args:
            node: Optional node name to filter by
            
        Returns:
            List of VM dictionaries
        """
        vms = []
        errors = []
        
        try:
            if node:
                # Check if node is online
                online_nodes = self.get_online_nodes()
                if node not in online_nodes:
                    self.logger.warning(f"Node '{node}' is offline, skipping VM retrieval")
                    return []
                    
                # Get VMs from the specific node
                try:
                    node_vms = self.api.nodes(node).qemu.get()
                    
                    # Add node information to each VM
                    for vm in node_vms:
                        vm['node'] = node
                        
                    vms.extend(node_vms)
                except Exception as e:
                    errors.append(f"Error getting VMs from node '{node}': {e}")
            else:
                # Get VMs from all online nodes
                online_nodes = self.get_online_nodes()
                for node_name in online_nodes:
                    try:
                        node_vms = self.api.nodes(node_name).qemu.get()
                        
                        # Add node information to each VM
                        for vm in node_vms:
                            vm['node'] = node_name
                            
                        vms.extend(node_vms)
                    except Exception as e:
                        errors.append(f"Error getting VMs from node '{node_name}': {e}")
        
            # Log errors but don't fail if we have some results
            if errors and not vms:
                raise Exception("; ".join(errors))
            elif errors:
                for error in errors:
                    self.logger.warning(error)
                    
            return vms
                
        except Exception as e:
            if isinstance(e, list) and len(e) > 0:
                e = e[0]
            self.logger.error(f"Error getting VMs: {e}")
            raise
    
    def get_containers(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all containers, optionally filtered by node.
        
        Args:
            node: Optional node name to filter by
            
        Returns:
            List of container dictionaries
        """
        containers = []
        errors = []
        
        try:
            if node:
                # Check if node is online
                online_nodes = self.get_online_nodes()
                if node not in online_nodes:
                    self.logger.warning(f"Node '{node}' is offline, skipping container retrieval")
                    return []
                
                # Get containers from the specific node
                try:
                    node_containers = self.api.nodes(node).lxc.get()
                    
                    # Add node information to each container
                    for container in node_containers:
                        container['node'] = node
                        
                    containers.extend(node_containers)
                except Exception as e:
                    errors.append(f"Error getting containers from node '{node}': {e}")
            else:
                # Get containers from all online nodes
                online_nodes = self.get_online_nodes()
                for node_name in online_nodes:
                    try:
                        node_containers = self.api.nodes(node_name).lxc.get()
                        
                        # Add node information to each container
                        for container in node_containers:
                            container['node'] = node_name
                            
                        containers.extend(node_containers)
                    except Exception as e:
                        errors.append(f"Error getting containers from node '{node_name}': {e}")
        
            # Log errors but don't fail if we have some results
            if errors and not containers:
                raise Exception("; ".join(errors))
            elif errors:
                for error in errors:
                    self.logger.warning(error)
                    
            return containers
                
        except Exception as e:
            if isinstance(e, list) and len(e) > 0:
                e = e[0]
            self.logger.error(f"Error getting containers: {e}")
            raise
    
    def get_vm_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get status of a specific VM.
        
        Args:
            node: Node name
            vmid: VM ID
            
        Returns:
            VM status dictionary
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                return {'status': 'unknown', 'error': f"Node '{node}' is offline"}
                
            return self.api.nodes(node).qemu(vmid).status.current.get()
        except Exception as e:
            self.logger.error(f"Error getting status for VM {vmid} on node '{node}': {e}")
            raise
    
    def get_container_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Get status of a specific container.
        
        Args:
            node: Node name
            vmid: Container ID
            
        Returns:
            Container status dictionary
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                return {'status': 'unknown', 'error': f"Node '{node}' is offline"}
                
            return self.api.nodes(node).lxc(vmid).status.current.get()
        except Exception as e:
            self.logger.error(f"Error getting status for container {vmid} on node '{node}': {e}")
            raise
    
    def start_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Start a VM.
        
        Args:
            node: Node name
            vmid: VM ID
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot start VM")
                
            return self.api.nodes(node).qemu(vmid).status.start.post()
        except Exception as e:
            self.logger.error(f"Error starting VM {vmid} on node '{node}': {e}")
            raise
    
    def stop_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Stop a VM.
        
        Args:
            node: Node name
            vmid: VM ID
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot stop VM")
                
            return self.api.nodes(node).qemu(vmid).status.stop.post()
        except Exception as e:
            self.logger.error(f"Error stopping VM {vmid} on node '{node}': {e}")
            raise
    
    def shutdown_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Shutdown a VM gracefully.
        
        Args:
            node: Node name
            vmid: VM ID
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot shutdown VM")
                
            return self.api.nodes(node).qemu(vmid).status.shutdown.post()
        except Exception as e:
            self.logger.error(f"Error shutting down VM {vmid} on node '{node}': {e}")
            raise
    
    def start_container(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Start a container.
        
        Args:
            node: Node name
            vmid: Container ID
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot start container")
                
            return self.api.nodes(node).lxc(vmid).status.start.post()
        except Exception as e:
            self.logger.error(f"Error starting container {vmid} on node '{node}': {e}")
            raise
    
    def stop_container(self, node: str, vmid: int) -> Dict[str, Any]:
        """
        Stop a container.
        
        Args:
            node: Node name
            vmid: Container ID
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot stop container")
                
            return self.api.nodes(node).lxc(vmid).status.stop.post()
        except Exception as e:
            self.logger.error(f"Error stopping container {vmid} on node '{node}': {e}")
            raise
    
    def get_storage(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of storage resources, optionally filtered by node.
        
        Args:
            node: Optional node name to filter by
            
        Returns:
            List of storage dictionaries with detailed information
        """
        storage_list = []
        
        try:
            if node:
                # Check if node is online
                online_nodes = self.get_online_nodes()
                if node not in online_nodes:
                    self.logger.warning(f"Node '{node}' is offline, skipping storage retrieval")
                    return []
                
                # Get storage list for this specific node
                node_storages = self.api.nodes(node).storage.get()
                
                # Get more detailed information for each storage on this node
                for storage in node_storages:
                    storage['node'] = node
                    # Add this node's usage statistics if available
                    try:
                        if 'storage' in storage:
                            storage_status = self.api.nodes(node).storage(storage['storage']).status.get()
                            storage.update(storage_status)
                    except Exception as e:
                        self.logger.debug(f"Could not get detailed storage info for {storage['storage']} on {node}: {e}")
                    storage_list.append(storage)
                    
            else:
                # First get all storages at cluster level
                cluster_storages = self.api.storage.get()
                
                # Get online nodes to check storage on each
                online_nodes = self.get_online_nodes()
                
                # For each storage, collect details from the first node where it's available
                for storage in cluster_storages:
                    storage_name = storage['storage']
                    storage_details = None
                    
                    # Try to get storage details from any online node
                    for test_node in online_nodes:
                        try:
                            # Check if this storage is available on this node
                            node_storages = self.api.nodes(test_node).storage.get()
                            if any(s['storage'] == storage_name for s in node_storages):
                                # Get detailed status
                                storage_details = self.api.nodes(test_node).storage(storage_name).status.get()
                                storage_details['node'] = test_node
                                # Update with cluster-level info
                                for key in storage:
                                    if key not in storage_details:
                                        storage_details[key] = storage[key]
                                break
                        except Exception as e:
                            self.logger.debug(f"Could not get storage {storage_name} details on node {test_node}: {e}")
                    
                    # If we found details, add them, otherwise add basic info
                    if storage_details:
                        storage_list.append(storage_details)
                    else:
                        # No details found, use basic info and mark node as 'cluster'
                        storage['node'] = 'cluster'
                        storage_list.append(storage)
                        
            return storage_list
        except Exception as e:
            self.logger.error(f"Error getting storage: {e}")
            raise
    
    def get_tasks(self, node: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent tasks for a node.
        
        Args:
            node: Node name
            limit: Maximum number of tasks to return
            
        Returns:
            List of task dictionaries
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                self.logger.warning(f"Node '{node}' is offline, cannot retrieve tasks")
                return []
                
            return self.api.nodes(node).tasks.get(limit=limit)
        except Exception as e:
            self.logger.error(f"Error getting tasks for node '{node}': {e}")
            raise
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """
        Get cluster status.
        
        Returns:
            Cluster status information
        """
        try:
            return self.api.cluster.status.get()
        except Exception as e:
            self.logger.error(f"Error getting cluster status: {e}")
            raise
    
    def find_vm_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a VM by its name across all nodes.
        
        Args:
            name: VM name to search for
            
        Returns:
            VM info if found, None otherwise
        """
        try:
            # Only search in VMs from online nodes (get_vms already handles this)
            for vm in self.get_vms():
                if vm['name'] == name:
                    return vm
            return None
        except Exception as e:
            self.logger.error(f"Error finding VM '{name}': {e}")
            raise
    
    def find_container_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a container by its name across all nodes.
        
        Args:
            name: Container name to search for
            
        Returns:
            Container info if found, None otherwise
        """
        try:
            # Only search in containers from online nodes (get_containers already handles this)
            for container in self.get_containers():
                if container['name'] == name:
                    return container
            return None
        except Exception as e:
            self.logger.error(f"Error finding container '{name}': {e}")
            raise
    
    def get_templates(self, node: str) -> List[Dict[str, Any]]:
        """
        Get list of available container templates on a node.
        
        Args:
            node: Node name
            
        Returns:
            List of template dictionaries
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                self.logger.warning(f"Node '{node}' is offline, cannot get templates")
                return []
                
            # Get templates from each storage that supports vztmpl content
            templates = []
            storages = self.api.nodes(node).storage.get()
            template_storages = [s for s in storages if 'vztmpl' in s.get('content', '')]
            
            if not template_storages:
                self.logger.warning(f"No storage with template support found on node '{node}'")
                return []
            
            for storage in template_storages:
                try:
                    # Get templates from this storage
                    storage_templates = self.api.nodes(node).storage(storage['storage']).content.get(content='vztmpl')
                    for template in storage_templates:
                        template['storage'] = storage['storage']
                    templates.extend(storage_templates)
                except Exception as e:
                    self.logger.debug(f"Error getting templates from storage {storage['storage']}: {e}")
                    
            return templates
        except Exception as e:
            self.logger.error(f"Error getting templates on node '{node}': {e}")
            raise

    def get_available_isos(self, node: str) -> List[Dict[str, Any]]:
        """
        Get list of available ISO images on a node.
        
        Args:
            node: Node name
            
        Returns:
            List of ISO dictionaries
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                self.logger.warning(f"Node '{node}' is offline, cannot get ISOs")
                return []
                
            # Get ISOs from storage
            isos = []
            node_storages = self.api.nodes(node).storage.get()
            
            # For each storage that supports ISOs, fetch the list
            for storage in node_storages:
                if 'iso' in storage.get('content', ''):
                    try:
                        storage_isos = self.api.nodes(node).storage(storage['storage']).content.get(content='iso')
                        for iso in storage_isos:
                            iso['storage'] = storage['storage']
                        isos.extend(storage_isos)
                    except Exception as e:
                        self.logger.debug(f"Error getting ISOs from storage {storage['storage']}: {e}")
                        
            return isos
        except Exception as e:
            self.logger.error(f"Error getting ISOs on node '{node}': {e}")
            raise

    def get_next_vmid(self) -> int:
        """
        Get next available VM/CT ID.
        
        Returns:
            Next available VMID
        """
        try:
            return int(self.api.cluster.nextid.get())
        except Exception as e:
            self.logger.error(f"Error getting next VMID: {e}")
            # Fallback to manual ID if cluster API fails
            try:
                # Get all existing VMs and containers
                vms = self.get_vms()
                cts = self.get_containers()
                
                # Get all used IDs
                ids = set()
                for vm in vms:
                    if 'vmid' in vm:
                        ids.add(vm['vmid'])
                for ct in cts:
                    if 'vmid' in ct:
                        ids.add(ct['vmid'])
                        
                # Start from 100 and find first available ID
                next_id = 100
                while next_id in ids:
                    next_id += 1
                    
                return next_id
            except Exception as inner_e:
                self.logger.error(f"Error finding next VMID manually: {inner_e}")
                raise
                
    def create_vm(self, node: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new virtual machine.
        
        Args:
            node: Node name
            params: Dictionary of VM parameters
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot create VM")
                
            # Create VM
            return self.api.nodes(node).qemu.post(**params)
        except Exception as e:
            self.logger.error(f"Error creating VM on node '{node}': {e}")
            raise
            
    def create_container(self, node: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new container.
        
        Args:
            node: Node name
            params: Dictionary of container parameters
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot create container")
                
            # Create container
            return self.api.nodes(node).lxc.post(**params)
        except Exception as e:
            self.logger.error(f"Error creating container on node '{node}': {e}")
            raise

    def get_vm_templates(self) -> List[Dict[str, Any]]:
        """
        Get list of all VM templates.
        
        Returns:
            List of VM template dictionaries
        """
        try:
            # Get all VMs
            all_vms = self.get_vms()
            
            # Filter only templates
            templates = [vm for vm in all_vms if vm.get('template') == 1]
            
            return templates
        except Exception as e:
            self.logger.error(f"Error getting VM templates: {e}")
            raise

    def get_regular_vms(self) -> List[Dict[str, Any]]:
        """
        Get list of regular VMs (excluding templates).
        
        Returns:
            List of regular VM dictionaries
        """
        try:
            # Get all VMs
            all_vms = self.get_vms()
            
            # Filter out templates
            regular_vms = [vm for vm in all_vms if not vm.get('template')]
            
            return regular_vms
        except Exception as e:
            self.logger.error(f"Error getting regular VMs: {e}")
            raise

    def clone_vm(self, node: str, vmid: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clone a VM or VM template.
        
        Args:
            node: Node name
            vmid: Source VM ID to clone
            params: Dictionary of clone parameters
            
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot clone VM")
                
            # Clone VM
            return self.api.nodes(node).qemu(vmid).clone.post(**params)
        except Exception as e:
            self.logger.error(f"Error cloning VM {vmid} on node '{node}': {e}")
            raise

    def get_network_interfaces(self, node: str) -> List[Dict[str, Any]]:
        """
        Get list of network interfaces on a node.
    
        Args:
            node: Node name
        
        Returns:
            List of network interface dictionaries
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                self.logger.warning(f"Node '{node}' is offline, cannot get network interfaces")
                return []
            
            # Get network interfaces
            ifaces = self.api.nodes(node).network.get()
            
            # Add node info to each interface
            for iface in ifaces:
                iface['node'] = node
                
            return ifaces
        except Exception as e:
            self.logger.error(f"Error getting network interfaces on node '{node}': {e}")
            raise

    def get_network_config(self, node: str, iface: str) -> Dict[str, Any]:
        """
        Get configuration of a specific network interface.
    
        Args:
            node: Node name
            iface: Interface name
        
        Returns:
            Network interface configuration
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                self.logger.warning(f"Node '{node}' is offline, cannot get network config")
                return {'error': 'Node is offline'}
            
            # Get interface config
            config = self.api.nodes(node).network(iface).get()
            config['node'] = node
            return config
        except Exception as e:
            self.logger.error(f"Error getting config for interface '{iface}' on node '{node}': {e}")
            raise

    def create_bridge(self, node: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new network bridge on a node.
    
        Args:
            node: Node name
            params: Bridge parameters (name, bridge_ports, etc.)
        
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot create bridge")
            
            # Set type to bridge
            params['type'] = 'bridge'
            
            # Create bridge
            return self.api.nodes(node).network.post(**params)
        except Exception as e:
            self.logger.error(f"Error creating bridge on node '{node}': {e}")
            raise

    def delete_network_interface(self, node: str, iface: str) -> Dict[str, Any]:
        """
        Delete a network interface from a node.
    
        Args:
            node: Node name
            iface: Interface name
        
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot delete interface")
            
            # Delete interface
            return self.api.nodes(node).network(iface).delete()
        except Exception as e:
            self.logger.error(f"Error deleting interface '{iface}' on node '{node}': {e}")
            raise

    def apply_network_changes(self, node: str) -> Dict[str, Any]:
        """
        Apply pending network changes on a node.
    
        Args:
            node: Node name
        
        Returns:
            Task result
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot apply network changes")
            
            # Apply network changes
            return self.api.nodes(node).network.put()
        except Exception as e:
            self.logger.error(f"Error applying network changes on node '{node}': {e}")
            raise

    def get_network_config_file(self, node: str) -> Dict[str, Any]:
        """
        Get contents of the network configuration file.
    
        Args:
            node: Node name
        
        Returns:
            Network configuration file contents
        """
        try:
            # Check if node is online
            online_nodes = self.get_online_nodes()
            if node not in online_nodes:
                raise Exception(f"Node '{node}' is offline, cannot get network config file")
            
            # Get config file (interfaces)
            return self.api.nodes(node).network.get(type='interfaces')
        except Exception as e:
            self.logger.error(f"Error getting network config file on node '{node}': {e}")
            raise