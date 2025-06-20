import click
import logging

from pyadm.ldapcli.click_commands import ldapcli
from pyadm.elastic.click_commands import elastic
from pyadm.pvecli import pvecli
from pyadm.config_commands import config_cli

# Default logging level - will be changed if --debug is passed
logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(name)s:%(message)s')


@click.group(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--debug', is_flag=True, help='Enable debug logging')
def cli(debug):
    """pyadm - Swiss Army Knife for Engineers and Administrators

    This tool provides modular functionality to perform various tasks efficiently.
    Currently, the available modules are 'ldap', 'elastic', and 'pve'.

    Usage: pyadm <module> SUBCOMMAND [OPTIONS]

    For more information on a particular subcommand, run 'pyadm <module> SUBCOMMAND --help'.

    \b
    Examples:
        pyadm ldap user jdoe             # Retrieve information for a user in the LDAP directory
        pyadm ldap groups jdoe           # Show groups associated with a user in the LDAP directory
        pyadm ldap members "Developers"  # Show members of a group in the LDAP directory
        pyadm elastic indices            # List all indices in the elastic cluster
        pyadm pve vm list                # List all VMs on Proxmox VE
        pyadm pve ct start mycontainer   # Start a container by name
    """
    # Configure logging level based on debug flag
    if debug:
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Debug logging enabled")
    pass

@click.command()
def version():
    """Display version information."""
    with open("VERSION", "r") as version_file:
        version = version_file.read().strip()
    click.echo(f"Version: {version}")


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument('shell', type=click.Choice(['bash', 'zsh', 'fish']), required=True)
def completion(shell):
    """Generate shell completion script for pyadm.
    
    SHELL: The shell to generate completion for (bash, zsh, fish)
    
    \b
    Setup Instructions:
    
    \b
    BASH:
        pyadm completion bash > ~/.pyadm-complete.bash
        echo 'source ~/.pyadm-complete.bash' >> ~/.bashrc
        source ~/.bashrc
    
    \b
    ZSH:
        pyadm completion zsh > ~/.pyadm-complete.zsh
        echo 'source ~/.pyadm-complete.zsh' >> ~/.zshrc
        source ~/.zshrc
    
    \b
    FISH:
        pyadm completion fish > ~/.config/fish/completions/pyadm.fish
        # Restart your fish shell or run:
        source ~/.config/fish/completions/pyadm.fish
    """
    
    if shell == 'bash':
        completion_script = """
_pyadm_completion() {
    local cur prev words cword
    _init_completion || return

    local subcommands="config elastic ldap pve version completion"
    local pve_commands="vm ct node storage network"
    local vm_commands="list status start stop shutdown create clone list-templates"
    local ct_commands="list status start stop create list-templates"
    local node_commands="list status"
    local storage_commands="list"

    case "${words[1]}" in
        pve)
            case "${words[2]}" in
                vm)
                    COMPREPLY=($(compgen -W "$vm_commands" -- "$cur"))
                    ;;
                ct)
                    COMPREPLY=($(compgen -W "$ct_commands" -- "$cur"))
                    ;;
                node)
                    COMPREPLY=($(compgen -W "$node_commands" -- "$cur"))
                    ;;
                storage)
                    COMPREPLY=($(compgen -W "$storage_commands" -- "$cur"))
                    ;;
                *)
                    COMPREPLY=($(compgen -W "$pve_commands" -- "$cur"))
                    ;;
            esac
            ;;
        completion)
            COMPREPLY=($(compgen -W "bash zsh fish" -- "$cur"))
            ;;
        *)
            COMPREPLY=($(compgen -W "$subcommands" -- "$cur"))
            ;;
    esac
}

complete -F _pyadm_completion pyadm
"""

    elif shell == 'zsh':
        completion_script = """
#compdef pyadm

_pyadm() {
    local context state line
    typeset -A opt_args

    _arguments -C \\
        '1: :->command' \\
        '*: :->args'

    case $state in
        command)
            _values 'pyadm commands' \\
                'config[Manage pyadm configuration]' \\
                'elastic[Elastic/OpenSearch management]' \\
                'ldap[Query LDAP/Active Directory]' \\
                'pve[Manage Proxmox Virtual Environment]' \\
                'version[Display version information]' \\
                'completion[Generate shell completion]'
            ;;
        args)
            case $words[2] in
                pve)
                    case $words[3] in
                        vm)
                            _values 'vm commands' \\
                                'list[List virtual machines]' \\
                                'status[Get VM status]' \\
                                'start[Start VM]' \\
                                'stop[Stop VM]' \\
                                'shutdown[Shutdown VM]' \\
                                'create[Create VM]' \\
                                'clone[Clone VM]' \\
                                'list-templates[List VM templates]'
                            ;;
                        ct)
                            _values 'container commands' \\
                                'list[List containers]' \\
                                'status[Get container status]' \\
                                'start[Start container]' \\
                                'stop[Stop container]' \\
                                'create[Create container]' \\
                                'list-templates[List container templates]'
                            ;;
                        node)
                            _values 'node commands' \\
                                'list[List nodes]' \\
                                'status[Get node status]'
                            ;;
                        storage)
                            _values 'storage commands' \\
                                'list[List storage]'
                            ;;
                        *)
                            _values 'pve commands' \\
                                'vm[Manage virtual machines]' \\
                                'ct[Manage containers]' \\
                                'node[Manage nodes]' \\
                                'storage[Manage storage]' \\
                                'network[Manage network]'
                            ;;
                    esac
                    ;;
                completion)
                    _values 'shells' 'bash' 'zsh' 'fish'
                    ;;
            esac
            ;;
    esac
}

_pyadm "$@"
"""

    elif shell == 'fish':
        completion_script = """
# pyadm Fish shell completions

# Main commands
complete -c pyadm -f -n '__fish_use_subcommand' -a 'config' -d 'Manage pyadm configuration'
complete -c pyadm -f -n '__fish_use_subcommand' -a 'elastic' -d 'Elastic/OpenSearch management'
complete -c pyadm -f -n '__fish_use_subcommand' -a 'ldap' -d 'Query LDAP/Active Directory'
complete -c pyadm -f -n '__fish_use_subcommand' -a 'pve' -d 'Manage Proxmox Virtual Environment'
complete -c pyadm -f -n '__fish_use_subcommand' -a 'version' -d 'Display version information'
complete -c pyadm -f -n '__fish_use_subcommand' -a 'completion' -d 'Generate shell completion'

# PVE subcommands
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and not __fish_seen_subcommand_from vm ct node storage network' -a 'vm' -d 'Manage virtual machines'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and not __fish_seen_subcommand_from vm ct node storage network' -a 'ct' -d 'Manage containers'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and not __fish_seen_subcommand_from vm ct node storage network' -a 'node' -d 'Manage nodes'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and not __fish_seen_subcommand_from vm ct node storage network' -a 'storage' -d 'Manage storage'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and not __fish_seen_subcommand_from vm ct node storage network' -a 'network' -d 'Manage network'

# PVE VM commands
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'list' -d 'List virtual machines'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'status' -d 'Get VM status'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'start' -d 'Start VM'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'stop' -d 'Stop VM'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'shutdown' -d 'Shutdown VM'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'create' -d 'Create VM'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'clone' -d 'Clone VM'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from vm' -a 'list-templates' -d 'List VM templates'

# PVE Container commands
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'list' -d 'List containers'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'status' -d 'Get container status'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'start' -d 'Start container'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'stop' -d 'Stop container'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'create' -d 'Create container'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from ct' -a 'list-templates' -d 'List container templates'

# PVE Node commands
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from node' -a 'list' -d 'List nodes'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from node' -a 'status' -d 'Get node status'

# PVE Storage commands
complete -c pyadm -f -n '__fish_seen_subcommand_from pve; and __fish_seen_subcommand_from storage' -a 'list' -d 'List storage'

# Completion command shells
complete -c pyadm -f -n '__fish_seen_subcommand_from completion' -a 'bash zsh fish' -d 'Shell type'

# Common options
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -s s -l server -d 'Select Proxmox VE server'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -s d -l debug -d 'Enable debug output'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -l dry-run -d 'Show what would be done'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -l offline -d 'Work in offline mode'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -s n -l node -d 'Node name'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -s j -l json -d 'Output as JSON'
complete -c pyadm -f -n '__fish_seen_subcommand_from pve' -s o -l output -d 'Comma-separated list of fields'
"""

    click.echo(completion_script.strip())


# Register the config command group
cli.add_command(config_cli)
cli.add_command(ldapcli)
cli.add_command(elastic)
cli.add_command(version)
cli.add_command(completion)
cli.add_command(pvecli)



if __name__ == "__main__":
    cli()
