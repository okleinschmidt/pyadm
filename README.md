# pyadm - Swiss Army Knife for Engineers and Administrators

**pyadm** is a versatile command-line tool designed as a Swiss Army Knife for engineers and administrators. It provides modular functionality to perform various tasks efficiently with professional-grade features including robust error handling, shell completion, and multi-server support.

**Available modules include:**
- **LDAP** - for LDAP/Active Directory operations with advanced user and group management
- **Elastic** - for Elasticsearch/OpenSearch operations with multi-cluster support
- **PVE** - for Proxmox Virtual Environment management with offline capabilities
- **Config** - for configuration management and validation

## Features

✨ **Professional Command-Line Interface**
- Rich help system with comprehensive examples
- Shell completion for bash, zsh, and fish
- Consistent error handling and user feedback
- Debug mode for troubleshooting (`--debug` flag)

🔧 **Multi-Environment Support**
- Configuration-based multi-server/cluster management
- Environment-specific settings (dev, staging, production)
- Secure credential storage

🛡️ **Robust Error Handling**
- Detailed error messages with context
- Graceful handling of connection failures
- Automatic retry mechanisms where appropriate

## Installation

To install `pyadm`, use the following command (soon!):

```shell
pip install pyadm-toolkit
```

For development installation:
```shell
git clone <repository-url>
cd pyadm
pip install -e .
```
## Usage

The general command structure for pyadm is as follows:
```shell
pyadm [--debug] MODULE SUBCOMMAND [OPTIONS]
```

**Global Options:**
- `--debug` - Enable detailed logging for troubleshooting
- `--help, -h` - Show help message

**Available modules:**
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

### Shell Completion

Enable shell completion for enhanced productivity:

**Bash:**
```shell
eval "$(_PYADM_COMPLETE=bash_source pyadm)"
# Or add to ~/.bashrc for persistence
```

**Zsh:**
```shell
eval "$(_PYADM_COMPLETE=zsh_source pyadm)"
# Or add to ~/.zshrc for persistence
```

**Fish:**
```shell
pyadm completion fish > ~/.config/fish/completions/pyadm.fish
```

## LDAP Module

The LDAP module provides comprehensive Active Directory and LDAP server management with advanced user and group operations, automatic DN format detection, and robust error handling.

### Key Features
- **Smart Authentication**: Automatic DN format conversion for email-style usernames
- **Multi-Server Support**: Switch between different LDAP servers using `--server/-s`
- **Comprehensive User Management**: Password management, account status, group membership
- **Group Operations**: Create, delete, modify groups and memberships
- **Flexible Output**: JSON, CSV, and formatted text output options

### User Management

**Basic User Operations:**
```shell
# Get user information
pyadm ldap user jdoe
pyadm ldap user jdoe@company.com --all
pyadm ldap user jdoe --json

# Check if user exists
pyadm ldap user-exists jdoe
```

**Group Membership Management:**
```shell
# Add user to group
pyadm ldap user jdoe --add-to-group "Developers"
pyadm ldap user jdoe --add-to-groups "HR,Finance,Management"

# Remove user from group  
pyadm ldap user jdoe --remove-from-group "Contractors"
pyadm ldap user jdoe --remove-from-groups "TempAccess,Consultants"
```

**Password Management:**
```shell
# Set new password (prompts securely)
pyadm ldap user jdoe --set-password

# Generate random password
pyadm ldap user jdoe --reset-password

# Force password change at next login
pyadm ldap user jdoe --force-password-change
```

**Account Management:**
```shell
# Enable/disable accounts
pyadm ldap user jdoe --enable
pyadm ldap user jdoe --disable

# Lock/unlock accounts  
pyadm ldap user jdoe --lock
pyadm ldap user jdoe --unlock

# Set account expiry
pyadm ldap user jdoe --set-expiry "2024-12-31"
```

**Attribute Management:**
```shell
# Set custom attributes
pyadm ldap user jdoe --set-attribute "department=Engineering"
pyadm ldap user jdoe --set-attribute "phone=555-1234"

# Show specific attributes
pyadm ldap user jdoe --attributes "mail,department,phone"
```

### Group Management

```shell
# List group information
pyadm ldap groups "Developers"
pyadm ldap groups "Developers" --json

# List group members
pyadm ldap members "Developers"
pyadm ldap members "Developers" --csv

# Check if group exists
pyadm ldap group-exists "TeamLead"
```

### Multi-Server Usage

```shell
# Use specific LDAP server
pyadm ldap --server LDAP_PROD user jdoe
pyadm ldap --server LDAP_STAGING groups "Developers"
```

## Elastic Module

The Elastic module allows you to interact with Elasticsearch or OpenSearch clusters and perform common operations such as retrieving cluster information, managing indices, searching documents, and reindexing data.

### Key Features
- **Multi-Cluster Support**: Manage multiple Elasticsearch/OpenSearch clusters
- **Comprehensive Index Management**: Create, delete, update indices and mappings
- **Advanced Search**: Complex query support with flexible output formats
- **Monitoring**: Health checks, performance metrics, and cluster status
- **Data Operations**: Reindexing, aliasing, and data migration tools

### Multi-cluster Support
The Elastic module supports multiple clusters via configuration sections. Use the `--cluster/-c` option to specify which cluster to use:

```shell
pyadm elastic --cluster ELASTIC_PROD info
```

### Examples

**Cluster Operations:**
```shell
# Get cluster information
pyadm elastic info

# Check cluster health
pyadm elastic health

# List all indices
pyadm elastic indices

# List indices with formatting options
pyadm elastic indices --limit 10 --output json
```

**Index Management:**
```shell
# Get index mappings
pyadm elastic mapping INDEX_NAME

# Get index settings
pyadm elastic settings INDEX_NAME

# Update index settings
pyadm elastic update-settings INDEX_NAME --settings '{"index.number_of_replicas": 2}'

# Create a new index
pyadm elastic create-index INDEX_NAME --body '{"settings": {"number_of_shards": 3}}'

# Get aliases
pyadm elastic aliases [INDEX_NAME]
```

**Search and Data Operations:**
```shell
# Search documents
pyadm elastic search INDEX_NAME --query '{"query": {"match_all": {}}}'

# Reindex data
pyadm elastic reindex --index "logstash-*" --suffix archived
```

## Proxmox VE Module

The Proxmox VE module provides comprehensive management of Proxmox Virtual Environment clusters, supporting both VMs and containers with advanced filtering, status management, and resource monitoring.

### Key Features
- **Multi-Server Support**: Manage multiple Proxmox clusters and nodes
- **Unified VM/Container Management**: Support for both VMs and containers with name/ID resolution
- **Offline Mode**: Work with sample data when servers are unavailable
- **Advanced Filtering**: Filter resources by node, status, name, or custom criteria
- **Resource Management**: Storage, network, and node configuration management

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

**Listing and Filtering:**
```shell
# List all VMs
pyadm pve vm list

# Filter VMs by node
pyadm pve vm list --node nodename

# Filter VMs by status
pyadm pve vm list --status running

# Filter by name pattern
pyadm pve vm list --name "*web*"
```

**VM Operations:**
```shell
# Get VM status (works with VM ID or name)
pyadm pve vm status VM_ID
pyadm pve vm status "web-server-01"

# Start, stop, or restart VMs
pyadm pve vm start VM_ID
pyadm pve vm stop "database-server"
pyadm pve vm restart 101

# Configure VMs
pyadm pve vm config 100 --show                    # Show current config
pyadm pve vm config web-server --show --json      # Show as JSON
pyadm pve vm config 100 --set "memory=4096"       # Set 4GB RAM
pyadm pve vm config 100 --set "cores=4"           # Set 4 CPU cores
pyadm pve vm config 100 --set "memory=8192" --set "cores=8"  # Multiple settings
pyadm pve vm config 100 --delete "net1"           # Remove network interface

# Migrate VMs between nodes
pyadm pve vm migrate 100 --target node2              # Offline migration
pyadm pve vm migrate web-server --target node2       # Migrate by name
pyadm pve vm migrate 100 --target node2 --online     # Live migration
pyadm pve vm migrate 100 --target node2 --with-local-disks  # Include local storage
```

### Container Management

**Container Operations:**
```shell
# List all containers
pyadm pve ct list

# Filter containers by node
pyadm pve ct list --node pve-node-01

# Start, stop, or restart containers (works with CT ID or name)
pyadm pve ct start CONTAINER_ID
pyadm pve ct stop "monitoring-ct"
pyadm pve ct restart 201

# Migrate containers between nodes
pyadm pve ct migrate 200 --target node2           # Offline migration
pyadm pve ct migrate web-ct --target node2        # Migrate by name
pyadm pve ct migrate 200 --target node2 --online  # Online migration
pyadm pve ct migrate 200 --target node2 --restart # Restart after migration
```

### Infrastructure Management

**Storage Management:**
```shell
# List storage information
pyadm pve storage list

# Show storage details
pyadm pve storage list --node nodename
```

**Network Management:**
```shell
# List network configurations
pyadm pve network list

# Show network details by node
pyadm pve network list --node nodename
```

**Node Management:**
```shell
# List all nodes in cluster
pyadm pve node list

# Get node status and information
pyadm pve node status nodename
```

## Configuration

The pyadm tool allows you to customize its behavior through a configuration file. By default, the configuration file is located at `~/.config/pyadm/pyadm.conf`.

### Configuration Management

```shell
# Generate a configuration template
pyadm config generate 

# Edit the existing config with your default editor
pyadm config edit

# Show current configuration
pyadm config show

# Validate configuration
pyadm config validate
```

### Configuration File Format

The configuration uses standard INI format with sections for different environments and services.

### Example Configuration

```ini
# Default LDAP server
[LDAP]
server = ldaps://dc.example.org
base_dn = dc=example,dc=org
bind_username = cn=admin,dc=example,dc=org
bind_password = s3cr3t-p455w0rd!
use_ssl = true
skip_tls_verify = false

# Production LDAP server
[LDAP_PROD]
server = ldaps://dc-prod.example.org
base_dn = dc=example,dc=org
bind_username = cn=admin,dc=example,dc=org
bind_password = prod-p455w0rd!
use_ssl = true

# Development LDAP server
[LDAP_DEV]
server = ldap://dc-dev.example.org
base_dn = dc=dev,dc=example,dc=org
bind_username = cn=admin,dc=dev,dc=example,dc=org
bind_password = dev-p455w0rd!
use_starttls = true
skip_tls_verify = true

# Default Elasticsearch cluster
[ELASTIC]
url = https://elasticsearch.example.org:9200
username = elastic
password = changeme
verify_certs = true

# Production Elasticsearch cluster
[ELASTIC_PROD]
url = https://es-prod.example.org:9200
username = elastic
password = prod-changeme
verify_certs = true

# Default Proxmox server
[PVE]
host = pve.example.org
username = root@pam
password = s3cr3t-p455w0rd!
verify_ssl = true

# Production Proxmox cluster
[PVE_PROD]
host = pve-prod.example.org
username = automation@pve
# Token-based authentication (recommended for production)
token_name = automation@pve!api-token
token_value = secret-token-value
verify_ssl = true
```

### Configuration Options

**LDAP Settings:**
- `server` - LDAP server URL (ldap:// or ldaps://)
- `base_dn` - Base Distinguished Name for searches
- `bind_username` - Username for authentication (DN format recommended)
- `bind_password` - Password for authentication
- `use_ssl` - Force SSL connection (true/false)
- `use_starttls` - Use STARTTLS for encryption (true/false)
- `skip_tls_verify` - Skip TLS certificate verification (true/false)

**Elasticsearch Settings:**
- `url` - Elasticsearch cluster URL
- `username` - Username for authentication
- `password` - Password for authentication
- `verify_certs` - Verify SSL certificates (true/false)

**Proxmox Settings:**
- `host` - Proxmox server hostname or IP
- `username` - Username for authentication
- `password` - Password for authentication (if not using tokens)
- `token_name` - API token name (format: user@realm!tokenname)
- `token_value` - API token value
- `verify_ssl` - Verify SSL certificates (true/false)

### Multi-Environment Usage

You can specify different sections in the configuration file to manage multiple environments:

```shell
# Use production LDAP server
pyadm ldap --server LDAP_PROD user jdoe

# Use staging Elasticsearch cluster
pyadm elastic --cluster ELASTIC_STAGING indices

# Use production Proxmox cluster
pyadm pve --server PVE_PROD vm list
```

## Troubleshooting

### Debug Mode

Enable debug mode for detailed logging and troubleshooting:

```shell
pyadm --debug ldap user jdoe --add-to-group "developers"
```

This will show:
- Connection attempts and results
- DN resolution process
- API call details
- Error details with context

### Common Issues

**LDAP Authentication Issues:**
- Ensure bind username is in DN format: `cn=admin,dc=example,dc=org`
- Check SSL/TLS settings match your server configuration
- Verify base_dn is correct for your directory structure

**Proxmox Connection Issues:**
- Use token-based authentication for better security
- Check SSL certificate settings
- Verify user permissions for required operations

**Elasticsearch Connection Issues:**
- Check URL format and port numbers
- Verify SSL certificate settings
- Ensure user has required cluster privileges

## Development

### Project Structure

```
pyadm/
├── src/pyadm/
│   ├── main.py              # Main CLI entry point
│   ├── config.py            # Configuration management
│   ├── config_commands.py   # Config CLI commands
│   ├── ldapcli/            # LDAP module
│   │   ├── ldap.py         # LDAP client implementation
│   │   ├── click_commands.py # LDAP CLI group
│   │   ├── user_commands.py  # User management commands
│   │   ├── group_commands.py # Group management commands
│   │   └── member_commands.py # Member listing commands
│   ├── elastic/            # Elasticsearch module
│   │   ├── elastic.py      # Elasticsearch client
│   │   └── click_commands.py # Elastic CLI commands
│   └── pvecli/            # Proxmox VE module
│       ├── pve.py         # Proxmox client
│       ├── pve_commands.py # Main PVE CLI group
│       ├── vm_commands.py  # VM management
│       ├── container_commands.py # Container management
│       ├── node_commands.py # Node management
│       ├── storage_commands.py # Storage management
│       └── network_commands.py # Network management
├── README.md
├── setup.cfg
├── pyproject.toml
└── requirements.txt
```

### Contributing Guidelines

1. **Code Style**: Follow PEP 8 conventions
2. **Documentation**: Update help text and README for new features
3. **Error Handling**: Provide meaningful error messages with context
4. **Testing**: Test with real and mock data when possible
5. **Compatibility**: Maintain backward compatibility when possible

### Adding New Features

When adding new commands or features:

1. **Follow the existing pattern**: Each module has its own directory with command files
2. **Add comprehensive help**: Include examples in docstrings using Click's `\b` formatting
3. **Implement error handling**: Use try/catch with meaningful error messages
4. **Support debug mode**: Add logging for troubleshooting
5. **Update documentation**: Add examples to README

### Example: Adding a New Command

```python
import click
import logging
from pyadm.ldapcli.click_commands import ldapcli, get_ldap_client

@ldapcli.command("new-command")
@click.argument("target")
@click.option("--option", "-o", help="Description of option")
def new_command(target, option):
    """Brief description of what this command does.
    
    TARGET: Description of the target argument
    
    Longer description with more details about the command's functionality.
    
    \b
    Examples:
        pyadm ldap new-command target1                    # Basic usage
        pyadm ldap new-command target2 --option value    # With option
    """
    try:
        ldap_client = get_ldap_client()
        logging.info(f"Executing new command on {target}")
        
        # Implementation here
        result = ldap_client.some_method(target, option)
        
        if result:
            click.echo(f"Successfully processed {target}")
        else:
            raise click.ClickException(f"Failed to process {target}")
            
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise click.ClickException(f"An error occurred: {e}")
```

## Contributing

Contributions are welcome! If you encounter any issues, have suggestions, or would like to add new features, please submit an issue or a pull request.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** following the development guidelines
4. **Add tests** if applicable
5. **Update documentation** including README and help text
6. **Commit your changes** (`git commit -m 'Add amazing feature'`)
7. **Push to the branch** (`git push origin feature/amazing-feature`)
8. **Open a Pull Request**

### Reporting Issues

When reporting issues, please include:
- **Command executed** and expected vs actual behavior
- **Configuration details** (sanitized, no passwords)
- **Error messages** with full traceback
- **Environment details** (OS, Python version, etc.)
- **Debug output** if available (`--debug` flag)

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

## Changelog

### Recent Improvements

- ✅ **Fixed LDAP Group Operations**: Resolved issues with adding/removing users to/from groups
- ✅ **Enhanced Error Handling**: Added detailed LDAP error codes and descriptions
- ✅ **Improved SSL/TLS Support**: Better handling of LDAPS connections and certificate validation
- ✅ **Smart Authentication**: Automatic DN format conversion for email-style usernames
- ✅ **Added Debug Mode**: `--debug` flag for troubleshooting and verbose logging
- ✅ **Shell Completion**: Comprehensive shell completion for bash, zsh, and fish
- ✅ **Professional Help System**: Rich help text with practical examples for all commands
- ✅ **Unified Resource Resolution**: VM and container commands work with both names and IDs
- ✅ **Migration Support**: Added VM and container migration between Proxmox nodes with online/offline options

---

*Feel free to copy and use this markdown source as needed for your README.md file.*
