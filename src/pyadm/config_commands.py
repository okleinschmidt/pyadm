import click
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from pyadm.config import cluster_config


@click.group("config")
def config_cli():
    """
    Manage pyadm configuration.
    """
    pass


def get_config_path():
    """Get the path to the configuration file."""
    return os.path.expanduser("~/.config/pyadm/pyadm.conf")


def ensure_config_dir():
    """Ensure the config directory exists."""
    config_dir = os.path.dirname(get_config_path())
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    return config_dir


@config_cli.command("edit")
@click.option("--editor", "-e", default=None, help="Specify editor to use")
def edit_config(editor):
    """
    Edit configuration file with your default editor.
    """
    # Get config path
    config_path = get_config_path()
    
    # Check if config file exists
    if not os.path.exists(config_path):
        ensure_config_dir()
        if click.confirm(f"Configuration file {config_path} does not exist. Create it?"):
            with open(config_path, 'w') as f:
                f.write("# pyadm configuration file\n\n")
        else:
            click.echo("Aborting.")
            return

    # Determine which editor to use
    editor_cmd = editor or os.environ.get('EDITOR') or os.environ.get('VISUAL')
    
    if not editor_cmd:
        if sys.platform == 'darwin':  # macOS
            editor_cmd = 'open -t'
        elif os.name == 'nt':  # Windows
            editor_cmd = 'notepad'
        else:  # Linux and others
            for ed in ['nano', 'vim', 'vi', 'emacs']:
                if subprocess.call(['which', ed], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0:
                    editor_cmd = ed
                    break
            if not editor_cmd:
                editor_cmd = 'nano'  # Fallback

    # Open the editor
    try:
        cmd = f'{editor_cmd} {config_path}'
        subprocess.call(cmd, shell=True)
        click.echo(f"Configuration file edited: {config_path}")
    except Exception as e:
        click.echo(f"Error opening editor: {e}")


@config_cli.command("generate")
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
def generate_config(output):
    """
    Generate example configuration.
    """
    example_config = """
# pyadm configuration example

# Example LDAP configuration - Default section
[LDAP]
server = ldap://ldap.example.org:389
base_dn = dc=example,dc=org
bind_username = cn=admin,dc=example,dc=org
bind_password = secret
skip_tls_verify = false
use_starttls = false
timeout = 10

# Example LDAP configuration - Production environment
[LDAP_PROD]
server = ldaps://ldap-prod.example.org:636
base_dn = dc=example,dc=org
bind_username = cn=readonly,dc=example,dc=org
bind_password = secret
skip_tls_verify = true
use_starttls = false
timeout = 30

# Example Elastic configuration - Default section
[ELASTIC]
hosts = https://elastic.example.org:9200
username = elastic
password = secret
verify_certs = true
ca_certs = /path/to/ca.crt
timeout = 30

# Example Elastic configuration - Production environment
[ELASTIC_PROD]
hosts = https://elastic-prod.example.org:9200,https://elastic-prod-2.example.org:9200
username = elastic_ro
password = secret
verify_certs = false
timeout = 60

# Example PVE configuration - Default section
[PVE]
host = pve.example.org
port = 8006
user = root@pam
password = secret
verify_ssl = true

# Example PVE configuration with API token
[PVE_PROD]
host = pve-prod.example.org
port = 8006
user = api@pam
token_name = pyadm
token_value = xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
verify_ssl = false
"""

    if output:
        with open(output, 'w') as f:
            f.write(example_config)
        click.echo(f"Example configuration written to {output}")
    else:
        click.echo(example_config)


@config_cli.command("path")
def config_path():
    """
    Show path to configuration file.
    """
    config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
    click.echo(f"Configuration file path: {config_path}")


@config_cli.command("show")
@click.option("--section", "-s", default=None, help="Show only specified section")
def show_config(section):
    """
    Show current configuration.
    """
    config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
    
    if not os.path.exists(config_path):
        click.echo(f"Configuration file not found: {config_path}")
        return
    
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    if section:
        # Find and extract the specified section
        import re
        pattern = rf"\[{re.escape(section)}\](.*?)(?=\[\w+\]|$)"
        match = re.search(pattern, config_content, re.DOTALL)
        
        if match:
            click.echo(f"[{section}]{match.group(1)}")
        else:
            click.echo(f"Section [{section}] not found in configuration.")
    else:
        click.echo(config_content)


@config_cli.command("validate")
def validate_config():
    """
    Validate configuration file syntax.
    """
    config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
    
    if not os.path.exists(config_path):
        click.echo(f"Configuration file not found: {config_path}")
        return
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Check if there's at least one section
        if len(config.sections()) == 0:
            click.echo("Warning: Configuration file contains no sections.")
        else:
            click.echo(f"Configuration file is valid. Found {len(config.sections())} sections:")
            for section in config.sections():
                click.echo(f"  - [{section}] with {len(config[section])} options")
        
    except Exception as e:
        click.echo(f"Error validating configuration: {e}")


@config_cli.command("get")
@click.argument("key_path")
def get_config_value(key_path):
    """
    Get configuration value by section.key path.
    
    Example: pyadm config get LDAP.server
    """
    try:
        if "." not in key_path:
            raise ValueError("Key path must be in format section.key")
        
        section, key = key_path.split(".", 1)
        cfg = cluster_config.get_cluster(section)
        
        if key in cfg:
            click.echo(f"{key_path} = {cfg[key]}")
        else:
            click.echo(f"Key '{key}' not found in section '{section}'")
            
    except Exception as e:
        click.echo(f"Error accessing configuration: {e}")


@config_cli.command("set")
@click.argument("key_value")
def set_config_value(key_value):
    """
    Set configuration value by section.key=value path.
    
    Example: pyadm config set LDAP.server=ldap://new-server:389
    """
    try:
        if "=" not in key_value:
            raise ValueError("Format must be section.key=value")
            
        key_path, value = key_value.split("=", 1)
        
        if "." not in key_path:
            raise ValueError("Key path must be in format section.key")
            
        section, key = key_path.split(".", 1)
        
        # Read current config
        config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
        import configparser
        config = configparser.ConfigParser()
        
        if os.path.exists(config_path):
            config.read(config_path)
        
        # Ensure section exists
        if section not in config:
            config[section] = {}
            
        # Set the new value
        config[section][key] = value
        
        # Write back to file
        with open(config_path, 'w') as f:
            config.write(f)
            
        click.echo(f"Set {section}.{key} = {value}")
        
    except Exception as e:
        click.echo(f"Error setting configuration: {e}")


@config_cli.command("list")
def list_sections():
    """
    List available configuration sections.
    """
    config_path = os.path.expanduser("~/.config/pyadm/pyadm.conf")
    
    if not os.path.exists(config_path):
        click.echo(f"Configuration file not found: {config_path}")
        return
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        
        if len(config.sections()) == 0:
            click.echo("No sections found in configuration.")
        else:
            click.echo("Available configuration sections:")
            for section in config.sections():
                prefix = section.split("_")[0] if "_" in section else section
                click.echo(f"  - {section} (type: {prefix})")
        
    except Exception as e:
        click.echo(f"Error listing sections: {e}")