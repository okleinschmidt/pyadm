# pyadm - Swiss Army Knife for Engineers and Administrators

**pyadm** is a versatile command-line tool designed as a Swiss Army Knife for engineers and administrators.\
It provides modular functionality to perform various tasks efficiently. 

**Available modules include:**
- **LDAP** - for LDAP/Active Directory operations
- **Elastic** - for Elasticsearch/OpenSearch operations
- **PVE** - for Proxmox Virtual Environment management

## Installation

To install `pyadm`, use the following command (soon!):

```shell
pip install pyadm-toolkit
```
## Usage
The general command structure for pyadm is as follows:
```shell
pyadm MODULE SUBCOMMAND [OPTIONS]
```

Available modules:
- `ldap` - For LDAP/Active Directory operations
- `elastic` - For Elasticsearch/OpenSearch operations
- `pve` - For Proxmox Virtual Environment management
- `config` - For configuration management

To see all available commands and modules:
```shell
pyadm --help
```

To get help for a specific module:
```shell
pyadm MODULE --help
```

## LDAP Module
The LDAP module within pyadm allows you to interact with LDAP servers and perform common operations, such as retrieving user information, showing group associations, and displaying group members.

### Examples
* Retrieve information for a user in the LDAP directory:
  ```shell
  pyadm ldap user USERNAME
  ```
* Show groups associated with a user in the LDAP directory:
  ```shell
  pyadm ldap groups USERNAME
  ```
* Show members of a group in the LDAP directory:
  ```shell
  pyadm ldap members GROUP_CN
  ```
For more information on each subcommand, you can use the --help option, as shown in the examples below:
```shell
pyadm ldap user --help
pyadm ldap groups --help
pyadm ldap members --help
```

## Elastic Module
The Elastic module allows you to interact with Elasticsearch or OpenSearch clusters and perform common operations such as retrieving cluster information, managing indices, searching documents, and reindexing data.

### Multi-cluster Support
The Elastic module supports multiple clusters via configuration sections. Use the `--cluster/-c` option to specify which cluster to use:

```shell
pyadm elastic --cluster ELASTIC_PROD info
```

### Examples
* Get cluster information:
  ```shell
  pyadm elastic info
  ```
* Check cluster health:
  ```shell
  pyadm elastic health
  ```
* List all indices:
  ```shell
  pyadm elastic indices
  ```
* List indices with output formatting options:
  ```shell
  pyadm elastic indices --limit 10 --output json
  ```
* Get index mappings:
  ```shell
  pyadm elastic mapping INDEX_NAME
  ```
* Search documents:
  ```shell
  pyadm elastic search INDEX_NAME --query '{"query": {"match_all": {}}}'
  ```
* Get index settings:
  ```shell
  pyadm elastic settings INDEX_NAME
  ```
* Update index settings:
  ```shell
  pyadm elastic update-settings INDEX_NAME --settings '{"index.number_of_replicas": 2}'
  ```
* Create a new index:
  ```shell
  pyadm elastic create-index INDEX_NAME --body '{"settings": {"number_of_shards": 3}}'
  ```
* Get aliases:
  ```shell
  pyadm elastic aliases [INDEX_NAME]
  ```
* Reindex:
  ```shell
  pyadm elastic reindex --index "logstash-*" --suffix archived
  ```

## Proxmox VE Module
The Proxmox VE module allows you to manage Proxmox Virtual Environment clusters, virtual machines, containers, storage, and network configurations.

### Multi-cluster Support
The PVE module supports multiple clusters via configuration sections. Use the `--server/-s` option to specify which server to use:

```shell
pyadm pve --server PVE_PROD vm list
```

### Offline Mode
You can use the `--offline` flag to work with sample data when no server is available:

```shell
pyadm pve --offline vm list
```

### Debug Mode
Enable debug output for API calls with the `--debug/-d` flag:

```shell
pyadm pve --debug vm list
```

### Virtual Machine Management
* List all VMs:
  ```shell
  pyadm pve vm list
  ```
* Filter VMs by node:
  ```shell
  pyadm pve vm list --node nodename
  ```
* Filter VMs by status:
  ```shell
  pyadm pve vm list --status running
  ```
* Get VM status:
  ```shell
  pyadm pve vm status VM_ID
  ```
* Start, stop, or restart VMs:
  ```shell
  pyadm pve vm start VM_ID
  pyadm pve vm stop VM_ID
  pyadm pve vm restart VM_ID
  ```

### Container Management
* List all containers:
  ```shell
  pyadm pve container list
  ```
* Start, stop, or restart containers:
  ```shell
  pyadm pve container start CONTAINER_ID
  pyadm pve container stop CONTAINER_ID
  pyadm pve container restart CONTAINER_ID
  ```

### Storage Management
* List storage information:
  ```shell
  pyadm pve storage list
  ```

### Network Management
* List network configurations:
  ```shell
  pyadm pve network list
  ```

## Configuration
The pyadm tool allows you to customize its behavior through a configuration file. By default, the configuration file is located at `~/.config/pyadm/pyadm.conf`.

You can generate a configuration template:
```shell
pyadm config generate 
```

Or edit the existing config:
```shell
pyadm config edit
```

### Example Configuration

```ini
[LDAP]
server = ldaps://dc.example.org
base_dn = dc=example,dc=org
bind_username = administrator@example.org
bind_password = s3cr3t-p455w0rd!

[LDAP_PROD]
server = ldaps://dc-prod.example.org
base_dn = dc=example,dc=org
bind_username = administrator@example.org
bind_password = s3cr3t-p455w0rd!

[ELASTIC]
url = http://localhost:9200
username = elastic
password = changeme

[PVE]
host = pve.example.org
username = root@pam
password = s3cr3t-p455w0rd!
# For token-based authentication:
# token_name = username@pam!tokenname
# token_value = secret-token-value
```

You can specify different sections in the configuration file to manage multiple environments (e.g., LDAP_PROD, ELASTIC_PROD, PVE_PROD).

## Contributing
Contributions are welcome! If you encounter any issues, have suggestions, or would like to add new features, please submit an issue or a pull request.

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).\
Feel free to copy and use this markdown source as needed for your `README.md` file.
