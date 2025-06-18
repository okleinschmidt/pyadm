import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

class OfflinePVEClient:
    """
    Offline client that provides sample data for Proxmox VE commands.
    Used when no actual server is available for testing or demo purposes.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Using offline PVE client with sample data")
    
    def get_nodes(self) -> List[Dict[str, Any]]:
        """Get sample node data."""
        return [
            {
                'node': 'node1',
                'status': 'online',
                'uptime': 1234567,
                'cpu': 0.05,
                'maxmem': 16 * 1024**3,  # 16GB
                'maxdisk': 500 * 1024**3,  # 500GB
            },
            {
                'node': 'node2',
                'status': 'online',
                'uptime': 2345678,
                'cpu': 0.10,
                'maxmem': 32 * 1024**3,  # 32GB
                'maxdisk': 1000 * 1024**3,  # 1TB
            },
            {
                'node': 'node3',
                'status': 'offline',
            }
        ]
    
    def get_node_status(self, node: str) -> Dict[str, Any]:
        """Get sample node status."""
        if node == 'node3':
            return {'status': 'offline'}
            
        return {
            'status': 'online',
            'uptime': 1234567 if node == 'node1' else 2345678,
            'loadavg': [0.01, 0.05, 0.10],
            'cpu': 0.05 if node == 'node1' else 0.10,
            'memory': {
                'total': 16 * 1024**3 if node == 'node1' else 32 * 1024**3,
                'used': 8 * 1024**3 if node == 'node1' else 16 * 1024**3,
            },
            'swap': {
                'total': 8 * 1024**3,
                'used': 1 * 1024**3,
            }
        }
    
    def get_vms(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sample VM data."""
        all_vms = [
            {
                'vmid': 100,
                'name': 'sample-vm1',
                'status': 'running',
                'node': 'node1',
                'cpu': 2,
                'maxmem': 4 * 1024**3,  # 4GB
            },
            {
                'vmid': 101,
                'name': 'sample-vm2',
                'status': 'stopped',
                'node': 'node1',
                'cpu': 4,
                'maxmem': 8 * 1024**3,  # 8GB
            },
            {
                'vmid': 102,
                'name': 'sample-vm3',
                'status': 'running',
                'node': 'node2',
                'cpu': 8,
                'maxmem': 16 * 1024**3,  # 16GB
            }
        ]
        
        if node:
            return [vm for vm in all_vms if vm['node'] == node]
        return all_vms
    
    def get_vm_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """Get sample VM status."""
        # Find the VM in our sample data
        for vm in self.get_vms():
            if vm['vmid'] == vmid and vm['node'] == node:
                status = vm['status']
                uptime = 86400 if status == 'running' else 0  # 1 day uptime if running
                return {
                    'status': status,
                    'vmid': vmid,
                    'name': vm['name'],
                    'cpus': vm['cpu'],
                    'maxmem': vm['maxmem'],
                    'uptime': uptime,
                }
        
        # If VM not found
        return {'status': 'unknown'}
    
    def start_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """Simulate starting a VM."""
        return {'data': f'UPID:node{node}:{datetime.now().strftime("%Y%m%d")}:start:'}
    
    def stop_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """Simulate stopping a VM."""
        return {'data': f'UPID:node{node}:{datetime.now().strftime("%Y%m%d")}:stop:'}
    
    def shutdown_vm(self, node: str, vmid: int) -> Dict[str, Any]:
        """Simulate shutting down a VM."""
        return {'data': f'UPID:node{node}:{datetime.now().strftime("%Y%m%d")}:shutdown:'}
    
    def get_containers(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sample container data."""
        all_containers = [
            {
                'vmid': 200,
                'name': 'sample-ct1',
                'status': 'running',
                'node': 'node1',
                'maxmem': 2 * 1024**3,  # 2GB
            },
            {
                'vmid': 201,
                'name': 'sample-ct2',
                'status': 'stopped',
                'node': 'node1',
                'maxmem': 4 * 1024**3,  # 4GB
            },
            {
                'vmid': 202,
                'name': 'sample-ct3',
                'status': 'running',
                'node': 'node2',
                'maxmem': 8 * 1024**3,  # 8GB
            }
        ]
        
        if node:
            return [ct for ct in all_containers if ct['node'] == node]
        return all_containers
    
    def get_container_status(self, node: str, vmid: int) -> Dict[str, Any]:
        """Get sample container status."""
        # Find the container in our sample data
        for ct in self.get_containers():
            if ct['vmid'] == vmid and ct['node'] == node:
                status = ct['status']
                uptime = 43200 if status == 'running' else 0  # 12 hours uptime if running
                return {
                    'status': status,
                    'vmid': vmid,
                    'name': ct['name'],
                    'cpus': 2,  # Assuming 2 CPUs for all containers
                    'maxmem': ct['maxmem'],
                    'uptime': uptime,
                }
        
        # If container not found
        return {'status': 'unknown'}
    
    def start_container(self, node: str, vmid: int) -> Dict[str, Any]:
        """Simulate starting a container."""
        return {'data': f'UPID:node{node}:{datetime.now().strftime("%Y%m%d")}:lxc-start:'}
    
    def stop_container(self, node: str, vmid: int) -> Dict[str, Any]:
        """Simulate stopping a container."""
        return {'data': f'UPID:node{node}:{datetime.now().strftime("%Y%m%d")}:lxc-stop:'}
    
    def get_storage(self, node: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get sample storage data."""
        all_storage = [
            {
                'storage': 'local',
                'type': 'dir',
                'content': 'images,rootdir',
                'active': 1,
                'total': 500 * 1024**3,  # 500GB
                'used': 100 * 1024**3,  # 100GB
                'avail': 400 * 1024**3,  # 400GB
            },
            {
                'storage': 'cephfs',
                'type': 'rbd',
                'content': 'images',
                'active': 1,
                'total': 2000 * 1024**3,  # 2TB
                'used': 500 * 1024**3,  # 500GB
                'avail': 1500 * 1024**3,  # 1.5TB
            }
        ]
        
        return all_storage
    
    def get_tasks(self, node: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get sample task data."""
        now = int(datetime.now().timestamp())
        return [
            {
                'upid': f'UPID:{node}:{now-3600}:start:100:root@pam:',
                'type': 'qmstart',
                'status': 'OK',
                'starttime': now - 3600,
                'endtime': now - 3500,
                'id': '100'
            },
            {
                'upid': f'UPID:{node}:{now-7200}:stop:101:root@pam:',
                'type': 'qmstop',
                'status': 'OK',
                'starttime': now - 7200,
                'endtime': now - 7150,
                'id': '101'
            }
        ]
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get sample cluster status."""
        return {
            'quorate': 1,
            'nodes': 3,
            'version': '7.0-1',
        }
    
    def find_vm_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a VM by name in sample data."""
        for vm in self.get_vms():
            if vm['name'] == name:
                return vm
        return None
    
    def find_container_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a container by name in sample data."""
        for container in self.get_containers():
            if container['name'] == name:
                return container
        return None