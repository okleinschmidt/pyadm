# pyadm - Swiss Army Knife for Engineers and Administrators

**pyadm** is a versatile command-line tool designed as a Swiss Army Knife for engineers and administrators. It provides modular functionality to perform various tasks efficiently with professional-grade features including robust error handling, shell completion, and multi-server support.

**Available modules include:**
- **LDAP** - for LDAP/Active Directory operations with advanced user and group management
- **Elastic** - for Elasticsearch/OpenSearch operations with multi-cluster support
- **PVE** - for Proxmox Virtual Environment management with offline capabilities
- **Kimai** - for Kimai time tracking, including recurring bookings
- **Uptime Kuma** - for monitors and scheduled downtimes
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

To install `pyadm`, use the following command:

```shell
pip install pyadm-toolkit
```

For development installation:
```shell
git clone https://github.com/okleinschmidt/pyadm.git
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
- `kimai` - For Kimai time tracking
- `uptime` - For Uptime Kuma monitors and maintenance windows
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
_PYADM_COMPLETE=fish_source pyadm > ~/.config/fish/completions/pyadm.fish
```

Completion is generated from the actual command tree, so it always covers every command and option. `pyadm completion <shell>` prints the line to use for your shell.

## LDAP Module

The LDAP module provides comprehensive Active Directory and LDAP server management with advanced user and group operations, automatic DN format detection, and robust error handling.

### Key Features
- **Smart Authentication**: Automatic DN format conversion for email-style usernames
- **Multi-Server Support**: Switch between different LDAP contexts using `--context/-c`
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
# Switch LDAP context (persistent)
pyadm ldap context list
pyadm ldap context use corp
pyadm ldap context current

# Override context only for one call
pyadm ldap --context staging groups "Developers"
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
The Elastic module supports named contexts. Use `context use` for persistent switching, or `--context/-c` for one-off overrides.

```shell
pyadm elastic context list
pyadm elastic context use prod
pyadm elastic context current
pyadm elastic --context ops info
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

# Limit the rows, pick the columns, or get raw JSON
pyadm elastic indices --limit 10
pyadm elastic indices -o index,docs.count,store.size
pyadm elastic indices --json
```

**Shard Capacity:**

A cluster refuses to create new shards once the number of open shards reaches `cluster.max_shards_per_node` times the number of data nodes — the familiar `this cluster currently has [X]/[Y] maximum shards open` error. Unassigned replicas count towards that budget as well. Running out of disk blocks writes in the same way, so `shards` reports both.

```shell
# Budget, headroom, and disk per node against the watermarks
pyadm elastic shards

# Which indices consume the budget
pyadm elastic shards --by-index
pyadm elastic shards --by-index --limit 0   # all indices

# Machine-readable
pyadm elastic shards --json
```

Example output:

```
Cluster status : yellow
Shard budget   : 380 / 1000 used (38.0%), 620 remaining
                 1000 max_shards_per_node x 1 data node(s)
Shards         : 349 primaries, 31 replicas, 31 unassigned

Disk per node (watermarks: low 85%, high 90%, flood 95%)
node      shards  used    avail    total    use%    state
------  --------  ------  -------  -------  ------  -------
node-1       349  44.8gb  22gb     66.8gb   66%     ok

! 31 unassigned shard(s) still consume budget. Reducing replicas frees it.
```

Nodes are listed fullest first, and the `state` column classifies each against the watermarks (`ok`/`low`/`high`/`flood`). Notes are collected at the end: one appears once the shard budget passes 80%, or a node reaches the low disk watermark. With `colors = yes` the status values are colourised.

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
The PVE module supports named contexts. Use `context use` for persistent switching, or `--context/-c` for one-off overrides.

```shell
pyadm pve context list
pyadm pve context use homelab
pyadm pve context current
pyadm pve --context prod vm list
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
```

**VM Operations:**
```shell
# Get VM status (works with VM ID or name)
pyadm pve vm status VM_ID
pyadm pve vm status "web-server-01"

# Start, stop, or shut down VMs
pyadm pve vm start VM_ID
pyadm pve vm stop "database-server"

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

**Snapshots:**
```shell
# Cluster-wide overview: every VM that has snapshots, oldest first
pyadm pve vm snapshots list
pyadm pve vm list-snapshots                    # Shortcut for the same command

# Only VMs whose newest snapshot is older than 30 days
pyadm pve vm snapshots list --older-than 30

# Restrict to one node, or show the full tree of every matching VM
pyadm pve vm snapshots list --node pve-node-01
pyadm pve vm snapshots list --tree

# Sort the overview (default: oldest snapshot first)
pyadm pve vm snapshots list --sort -snaps
pyadm pve vm snapshots list --sort name

# Snapshots of a single VM, as a tree
pyadm pve vm snapshots list 100
pyadm pve vm snapshots list web-server --json

# Create a snapshot (--vmstate also saves the memory of a running VM)
pyadm pve vm snapshots create 100 before-upgrade
pyadm pve vm snapshots create web-server before-upgrade -d "Ticket 4711"
pyadm pve vm snapshots create 100 hotfix --vmstate

# Delete snapshots (asks for confirmation unless --yes is given)
pyadm pve vm snapshots delete 100 kernel-test
pyadm pve vm snapshots delete web-server old-1 old-2 --yes
```

Deleting a snapshot leaves the running VM untouched and its child snapshots
intact — they are re-attached to the parent of the deleted one.

Without a VM ID every VM in the cluster is scanned and the ones that have
snapshots are listed, so forgotten snapshots become visible at a glance. VMs
without snapshots are left out. Ages older than 7 days are highlighted, older
than 30 days more strongly (see `warn_days` / `crit_days` below); the `ram`
column marks VMs whose snapshots also captured the memory state, which makes
them considerably more expensive to keep around.

```text
  vmid  name        node    status      snaps  oldest    newest    ram    snapshot names
------  ----------  ------  --------  -------  --------  --------  -----  --------------------------------------
   102  sample-vm3  node2   running         1  400d 0h   400d 0h          quick-test
   100  sample-vm1  node1   running         4  30d 0h    2d 0h     yes    base-install, before-upgrade, after-...
```

With a VM ID the snapshots of that VM are drawn as a tree, since every snapshot
descends from the one that was active when it was taken. The
`NOW (current state)` entry marks where the VM currently sits, which makes
abandoned branches obvious — `kernel-test` below was never returned to.

```text
name                          created           age     ram    description
----------------------------  ----------------  ------  -----  -------------------
base-install                  2026-08-21 08:35  30d 0h         Fresh install
└─ before-upgrade             2026-09-13 08:35  7d 0h   yes    Before dist-upgrade
   ├─ after-upgrade           2026-09-14 08:35  6d 0h          Upgrade went fine
   │  └─ NOW (current state)                                   You are here!
   └─ kernel-test             2026-09-18 08:35  2d 0h          Testing 6.8 kernel
```

### Container Management

**Container Operations:**
```shell
# List all containers
pyadm pve ct list

# Filter containers by node
pyadm pve ct list --node pve-node-01

# Start or stop containers (works with CT ID or name)
pyadm pve ct start CONTAINER_ID
pyadm pve ct stop "monitoring-ct"

# Migrate containers between nodes
pyadm pve ct migrate 200 --target node2           # Offline migration
pyadm pve ct migrate web-ct --target node2        # Migrate by name
pyadm pve ct migrate 200 --target node2 --online  # Online migration
pyadm pve ct migrate 200 --target node2 --restart # Restart after migration
```

**Container Snapshots:**
```shell
# Cluster-wide overview: every container that has snapshots, oldest first
pyadm pve ct snapshots list
pyadm pve ct list-snapshots                    # Shortcut for the same command

# Same filters as for VMs
pyadm pve ct snapshots list --older-than 30
pyadm pve ct snapshots list --node pve-node-01 --tree
pyadm pve ct snapshots list 200                # Tree of a single container

# Create and delete
pyadm pve ct snapshots create 200 before-upgrade -d "Ticket 4711"
pyadm pve ct snapshots delete 200 old-1 old-2 --yes
```

Containers work exactly like VMs here, with one difference: an LXC snapshot
never contains a memory state, so there is no `--vmstate` option and no `ram`
column.

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

## Kimai Module

The Kimai module talks to the REST API of a [Kimai](https://www.kimai.org/) time tracking instance. Besides the everyday timesheet operations it can book recurring tasks onto a project in one go — a whole quarter of Saturday shifts, a daily stand-up for the next month, or just today's block of work.

### Key Features
- **Names instead of IDs**: projects and activities can be given by name or numeric ID
- **Recurring bookings**: pick days by date, month, month range or date range, narrowed by weekday
- **Presets**: store a recurring set of slots in the configuration and book it with one flag
- **Idempotent**: identical entries that already exist are skipped, so a run can be repeated safely
- **Dry run**: `--dry-run` shows exactly what would be created before anything is written
- **Multi-instance support**: switch between instances with `--context/-c`

### Setup

Create an API token in Kimai (*Profile → API access*) and add a context:

```ini
[KIMAI_CONTEXT_work]
name = work
url = https://kimai.example.org
api_token = kimai_pat_xxxxxxxxxxxxxxxx
timezone = Europe/Berlin
```

```shell
# Verify URL and credentials
pyadm kimai ping

# Instance and account information
pyadm kimai version
pyadm kimai me
```

### Master Data

```shell
# Customers, projects and activities
pyadm kimai customers
pyadm kimai projects
pyadm kimai projects --customer ACME
pyadm kimai activities --project "Support"

# Tags and users
pyadm kimai tags
pyadm kimai users
```

Every listing takes `--json`/`-j` for raw API output and `--visibility visible|hidden|all`.

### Timesheet Management

```shell
# Recent entries (default: last 7 days)
pyadm kimai timesheet list
pyadm kimai timesheet list --days 30 --project "Support"
pyadm kimai timesheet list --from 2026-09-01 --to 2026-09-30

# A single entry
pyadm kimai timesheet show 4711

# Add a finished entry
pyadm kimai timesheet add -p "Support" -a "Maintenance" -b 09:00 -d 3h -m "Consulting"
pyadm kimai timesheet add -p 42 -a 7 --date 2026-09-18 -b 09:00 -e 12:30

# Live tracking
pyadm kimai timesheet start -p "Support" -a "Maintenance"
pyadm kimai timesheet active
pyadm kimai timesheet stop
pyadm kimai timesheet restart 4711

# Remove entries
pyadm kimai timesheet delete 4711 4712
```

### Recurring Bookings

`pyadm kimai book` creates one or more slots on every selected day.

**Slots** are given as `BEGIN-END` (`09:00-11:45`) or `BEGIN+DURATION` (`09:00+2h45m`), optionally followed by `|description`, and by `|project|activity` to override the command-wide project and activity for that slot. Durations accept `2h45m`, `90m`, `1.5h`, `2:45` or a plain number of minutes.

**Days** are chosen with exactly one of `--date`, `--month`, `--start-month`/`--end-month` or `--from`/`--to` (default: today), and are narrowed with `--weekday` (`sat`, `mon-fri`, `weekdays`, `weekend`, `all`).

```shell
# A single block today
pyadm kimai book -p "Support" -a "Maintenance" -b 09:00 -d 3h -m "Consulting"

# Two blocks on every Saturday of a quarter
pyadm kimai book -p "Support" -a "Maintenance" \
    -s "09:00-11:45|Weekend shift 1" \
    -s "11:45-14:30|Weekend shift 2" \
    --start-month 2026-01 --end-month 2026-03 -w sat

# A daily stand-up on working days of one month
pyadm kimai book -p "Internal" -a "Meetings" -s "09:00+15m|Daily stand-up" \
    --month 2026-10 -w weekdays

# Different projects within one day
pyadm kimai book -p "Support" -a "Maintenance" \
    -s "09:00-12:00" \
    -s "13:00-17:00|Rollout|Infrastructure|Deployment" \
    --date 2026-09-21

# Check first, book afterwards
pyadm kimai book --preset saturday --month 2026-10 --dry-run
pyadm kimai book --preset saturday --month 2026-10 -y
```

Useful flags: `--dry-run` (create nothing), `--yes/-y` (skip the confirmation), `--tags`, `--user-id` (book for someone else, needs permissions), `--timezone`, and `--no-duplicate-check` when an identical entry really should be created twice.

### Booking Presets

A recurring booking can be stored in the configuration as a `[BOOKING_<name>]` section and then booked by name. Command line options override the preset.

```ini
[BOOKING_saturday]
project = Support
activity = Maintenance
# One slot per line (or comma separated)
slots =
    09:00-11:45|Weekend shift 1
    11:45-14:30|Weekend shift 2
weekdays = sat
tags = maintenance,weekend

[BOOKING_standup]
project = Internal
activity = Meetings
slots = 09:00+15m|Daily stand-up
weekdays = mon-fri
```

```shell
# Show the configured presets
pyadm kimai presets

# Book all Saturdays of a quarter from the preset
pyadm kimai book --preset saturday --start-month 2026-01 --end-month 2026-03

# Same preset, but a different description for this run
pyadm kimai book --preset standup --month 2026-10 -m "Team sync"
```

### Multi-Instance Usage

```shell
pyadm kimai context list
pyadm kimai context use work
pyadm kimai -c freelance timesheet list
```

## Uptime Kuma Module

The Uptime Kuma module manages an [Uptime Kuma](https://uptime.kuma.pet/) instance: create monitors without clicking through the web UI, and schedule downtimes before a maintenance rather than muting alerts afterwards. Uptime Kuma has no REST API, so the module talks Socket.IO through the [`uptime-kuma-api`](https://github.com/lucasheld/uptime-kuma-api) package.

**Server versions**: the package targets Uptime Kuma 1.21 - 1.23. Uptime Kuma 2.x kept the protocol but added database columns that must not be `NULL`, so a monitor written by the unmodified package is rejected by the backend (`NOT NULL constraint failed: monitor.conditions`). pyadm detects the server version and completes the payload, so monitors can be created and changed on 2.x as well. Should a future version want yet another field, the error names it instead of printing the failed SQL statement; `pyadm --debug` shows the original message.

### Key Features
- **Names instead of IDs**: monitors, notifications, tags and status pages can be given by name
- **Quick downtimes**: `pyadm uptime downtime -m web -d 2h` silences monitors for a window
- **Recurring maintenance**: weekly, monthly, interval and cron windows
- **Dry run**: `--dry-run` shows what would be created before anything is written
- **Multi-instance support**: switch between instances with `--context/-c`

### Setup

Add a context with the credentials of an Uptime Kuma user:

```ini
[UPTIME_CONTEXT_prod]
name = prod
url = https://uptime.example.org
username = admin
password = secret
timezone = Europe/Berlin
```

```shell
# Verify URL and credentials
pyadm uptime ping

# Instance information, notification providers, tags and status pages
pyadm uptime info
pyadm uptime notifications
pyadm uptime tags
pyadm uptime status-pages
```

### Monitors

```shell
# List monitors, with their last heartbeat
pyadm uptime monitor list
pyadm uptime monitor list --down
pyadm uptime monitor list --type http --tag prod
pyadm uptime monitor list -o id,name,target,status
pyadm uptime monitor list --sort id --full

# Find monitors by name, target or type
pyadm uptime monitor search vpn
pyadm uptime monitor search datenreisende.org -o id,name,target

# One monitor in detail, and its recent heartbeats
pyadm uptime monitor show web
pyadm uptime monitor beats web --hours 6 --important

# Create monitors
pyadm uptime monitor add web --url https://example.org -N "Ops mail"
pyadm uptime monitor add api --type keyword --url https://api.example.org \
    --keyword '"status":"ok"' --interval 120
pyadm uptime monitor add db --type port --hostname db.example.org --port 5432
pyadm uptime monitor add gw --type ping --hostname 10.0.0.1 --tag network

# Change, pause and remove
pyadm uptime monitor edit web --interval 120 --retries 3
pyadm uptime monitor pause web
pyadm uptime monitor resume web
pyadm uptime monitor delete old-host
```

`monitor search TERM` is the same listing with the search term as an argument - `monitor list -s TERM` does the same thing - and takes all filters of the listing.

Monitors are sorted by name; `--sort id|name|type|status` changes that. Long targets are shortened to keep the columns aligned - `--full` prints them in full, and `--json`/`-j` is never shortened.

`monitor add` and `monitor edit` share their options; `--type` selects what is checked (`http`, `keyword`, `json-query`, `port`, `ping`, `dns`, `docker`, `push`, `group`, ...) and the type-specific options are `--url`, `--hostname`/`--port`, `--keyword`, `--json-path`/`--expected-value` and `--dns-resolve-server`/`--dns-resolve-type`. An edit only changes the options you actually pass.

### Downtimes

`pyadm uptime downtime` is the shortcut for the common case: take monitors out of alerting for a while. It creates a one-off maintenance window.

```shell
# Two hours from now
pyadm uptime downtime -m web -m api -d 2h

# Tonight at 22:00 for 90 minutes
pyadm uptime downtime -m web -s 22:00 -d 90m

# An explicit window, announced on a status page
pyadm uptime downtime -m db -s "2026-10-04 22:00" -e "2026-10-05 02:00" \
    --status-page status -D "Database upgrade"

# Check first
pyadm uptime downtime -m web -d 30m --dry-run
```

Times are given as `now`, `HH:MM` (today, or tomorrow when that time has passed), `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`. Durations accept `2h`, `90m`, `1h30m` or `1:30`.

### Maintenance Windows

Everything else about maintenance lives under `pyadm uptime maintenance`, including the recurring strategies.

```shell
# What is scheduled
pyadm uptime maintenance list
pyadm uptime maintenance list --monitors
pyadm uptime maintenance show "Patch night"

# Every Saturday between 02:00 and 04:00
pyadm uptime maintenance add "Patch night" -m web -m api \
    --strategy recurring-weekday -w sat --window 02:00-04:00

# First and last day of the month
pyadm uptime maintenance add "Billing run" -m shop \
    --strategy recurring-day-of-month --day 1 --day last --window 01:00-03:00

# Every third day, and a cron window of 45 minutes
pyadm uptime maintenance add "Backup" -m nas \
    --strategy recurring-interval --interval-day 3 --window 23:00-23:30
pyadm uptime maintenance add "Nightly" -m web \
    --strategy cron --cron "30 3 * * *" -d 45m

# A window that is ended by hand
pyadm uptime maintenance add "Ad hoc" -m web --strategy manual

# Pause, resume, remove
pyadm uptime maintenance pause "Patch night"
pyadm uptime maintenance resume "Patch night"
pyadm uptime maintenance delete "Ad hoc"
```

A maintenance always needs at least one monitor (`-m/--monitor`, repeatable) - without monitors it silences nothing. `--status-page` additionally announces the window on a status page. Times are interpreted in the timezone of the context, overridable per command with `--timezone`; without either, the server timezone applies.

### Multi-Instance Usage

```shell
pyadm uptime context list
pyadm uptime context use prod
pyadm uptime -c staging monitor list
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

The configuration uses INI format with named contexts per module and an active selection in `[CONTEXT]`.

### Example Configuration

```ini
[GENERAL]
colors = yes

# Active context per module
[CONTEXT]
elastic = prod
ldap = corp
pve = homelab
kimai = work
uptime = prod

[LDAP_CONTEXT_corp]
name = corp
server = ldaps://dc.example.org
base_dn = dc=example,dc=org
bind_username = cn=admin,dc=example,dc=org
bind_password = s3cr3t-p455w0rd!
use_starttls = false
skip_tls_verify = false

[LDAP_CONTEXT_staging]
name = staging
server = ldaps://dc-staging.example.org
base_dn = dc=example,dc=org
bind_username = cn=readonly,dc=example,dc=org
bind_password = staging-secret
use_starttls = false
skip_tls_verify = true
force_ipv4 = true

[ELASTIC_CONTEXT_prod]
name = prod
url = https://elasticsearch.example.org:9200
username = elastic
password = changeme
engine = elasticsearch
skip_tls_verify = false

[ELASTIC_CONTEXT_ops]
name = ops
url = https://es-ops.example.org:9200
username = elastic_ro
password = ops-secret
engine = opensearch
skip_tls_verify = true
force_ipv4 = true

[PVE_CONTEXT_homelab]
name = homelab
host = pve.example.org
user = root@pam
password = s3cr3t-p455w0rd!
verify_ssl = true

[PVE_CONTEXT_prod]
name = prod
host = pve-prod.example.org
user = automation@pve
token_name = pyadm
token_value = secret-token-value
verify_ssl = true
force_ipv4 = true

[KIMAI_CONTEXT_work]
name = work
url = https://kimai.example.org
api_token = kimai_pat_xxxxxxxxxxxxxxxx
timezone = Europe/Berlin

# Recurring booking preset for 'pyadm kimai book --preset saturday'
[BOOKING_saturday]
project = Support
activity = Maintenance
slots =
    09:00-11:45|Weekend shift 1
    11:45-14:30|Weekend shift 2
weekdays = sat
tags = maintenance,weekend
```

### Configuration Options

**Kimai Settings** (`[KIMAI_CONTEXT_<name>]` sections):
- `url` - Base URL of the Kimai instance (required)
- `api_token` - API token for bearer authentication (Kimai 2.x, preferred)
- `username` / `api_password` - Legacy authentication via the `X-AUTH-*` headers
- `timezone` - Timezone the given times are interpreted in (default: system timezone)
- `skip_tls_verify` - Skip TLS certificate verification (true/false, default: false)
- `timeout` - Request timeout in seconds (default: 30)
- `force_ipv4` - Only connect over IPv4 (true/false, default: false)

**Uptime Kuma Settings** (`[UPTIME_CONTEXT_<name>]` sections):
- `url` - Base URL of the Uptime Kuma instance (required)
- `username` / `password` - Credentials of an Uptime Kuma user
- `mfa_token` - Code of the authenticator app when the account uses 2FA
- `token` - Token of an earlier login, as an alternative to username/password
- `timezone` - Timezone maintenance windows are scheduled in (default: server timezone)
- `skip_tls_verify` - Skip TLS certificate verification (true/false, default: false)
- `timeout` - Connection timeout in seconds (default: 30)
- `force_ipv4` - Only connect over IPv4 (true/false, default: false)

**Booking Presets** (`[BOOKING_<name>]` sections, used by `pyadm kimai book --preset <name>`):
- `project` / `activity` - Default project and activity (ID or name)
- `slots` - Slot specifications, one per line or comma separated
- `weekdays` - Weekday filter, e.g. `sat`, `mon-fri`, `weekend`
- `description` - Description for slots that do not carry one
- `tags` - Comma-separated tags
- `timezone` - Timezone override for this preset
- `user_id` - Book for another user (needs permissions)

**General Settings** (`[GENERAL]` section):
- `colors` - Colourise status and usage values (true/false, default: false)
- `warn_percent` - Usage percentage that turns a value yellow (default: 80)
- `crit_percent` - Usage percentage that turns a value red (default: 90)
- `warn_days` - Snapshot age in days that turns it yellow (default: 7)
- `crit_days` - Snapshot age in days that turns it red (default: 30)

With `colors = yes`, three kinds of value are colourised:

- **States** — Elasticsearch cluster health as green/yellow/red, VM, container and node states as green (running, online), yellow (paused, suspended) or red (stopped, offline), and Uptime Kuma monitors as green (up), red (down), yellow (pending, paused) or blue (maintenance, because a planned window is not a fault). A state pyadm does not recognise is left uncoloured rather than guessed at.
- **Usage** — anything measured as a share of a maximum: the Elasticsearch shard budget, and CPU, memory and disk on Proxmox. Green below `warn_percent`, yellow from there, red from `crit_percent`.
- **Age** — how old a snapshot is. Uncoloured below `warn_days`, yellow from there, red from `crit_days`, so a forgotten snapshot stands out in a long list.

All four thresholds can also be set in an individual context section to override the global value, as can `colors` itself. Colours are suppressed when the `NO_COLOR` environment variable is set, and dropped automatically when output is piped or redirected, so `--json` and shell pipelines stay clean.

Proxmox list and status commands report memory as `used (NN%)` rather than only the configured maximum, which is what makes the colouring meaningful:

```
  vmid  name     status    node    cpu    mem              maxmem
------  -------  --------  ------  -----  ---------------  --------
   114  k3s-2    running   luna    13.5%  12.31 GB (103%)  12.00 GB
   111  boxvpn   running   luna    8.0%   4.97 GB (83%)    6.00 GB
   401  syno     running   gemma   9.1%   1.91 GB (48%)    4.00 GB
```

A guest can report slightly over 100% because the hypervisor counts its overhead towards the figure; the value is passed through from the API unchanged.

**LDAP Settings:**
- `server` - LDAP server URL (ldap:// or ldaps://)
- `base_dn` - Base Distinguished Name for searches
- `bind_username` - Username for authentication (DN format recommended)
- `bind_password` - Password for authentication
- `use_ssl` - Force SSL connection (true/false)
- `use_starttls` - Use STARTTLS for encryption (true/false)
- `skip_tls_verify` - Skip TLS certificate verification (true/false)
- `force_ipv4` - Only connect over IPv4 (true/false, see below)
- `group_base_dn` - Container new groups are created in (default: `base_dn`)
- `group_object_class` - Object classes for new groups, comma-separated (default: `top,groupOfNames`)
- `group_gid_min` - Lowest gidNumber to assign when the schema needs one (default: 20000)
- `user_uid_min` - Lowest uidNumber to assign when cloning a posixAccount (default: 20000)

**Elasticsearch Settings:**
- `url` - Elasticsearch cluster URL
- `username` - Username for authentication
- `password` - Password for authentication
- `engine` - `elasticsearch` or `opensearch` (optional)
- `skip_tls_verify` - Skip TLS certificate verification (true/false)
- `force_ipv4` - Only connect over IPv4 (true/false, see below)

**Proxmox Settings:**
- `host` - Proxmox server hostname or IP
- `user` - Username for authentication
- `password` - Password for authentication (if not using tokens)
- `token_name` - API token name (format: user@realm!tokenname)
- `token_value` - API token value
- `verify_ssl` - Verify SSL certificates (true/false)
- `force_ipv4` - Only connect over IPv4 (true/false, see below)

#### `force_ipv4`

Set `force_ipv4 = true` when a host has an AAAA record whose address is not
reachable from your client (dropped packets rather than a refused connection).
The underlying libraries do not implement Happy Eyeballs: they try the resolved
addresses strictly in order, so every new TCP connection blocks on the full
connect timeout for the dead IPv6 address before falling back to IPv4. With
several requests per command this easily adds tens of seconds.

Symptoms: commands such as `pyadm pve vm list` take a multiple of the connect
timeout, while `curl` against the same host is fast (curl does implement Happy
Eyeballs). Verify with:

```shell
python3 -c "import socket,time; t=time.time(); socket.create_connection(('myhost.example.org', 8006)); print(time.time()-t)"
```

Fixing DNS or the firewall on the target host is the better long-term solution;
`force_ipv4` is the client-side workaround.

### Multi-Environment Usage

Use context commands to switch persistently, or per-command overrides:

```shell
# Switch context persistently
pyadm ldap context use corp
pyadm elastic context use prod
pyadm pve context use homelab

# Override only this command
pyadm ldap --context staging user jdoe
pyadm elastic --context ops indices
pyadm pve --context prod vm list
```

Legacy section names (`[LDAP]`, `[LDAP_PROD]`, `[ELASTIC]`, `[ELASTIC_PROD]`, `[PVE]`, `[PVE_PROD]`) are still supported.

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
│   ├── table.py             # Shared list output (format, headers, JSON)
│   ├── output.py            # Shared colouring of states and usage values
│   ├── ldapcli/            # LDAP module
│   │   ├── ldap.py         # LDAP client implementation
│   │   ├── click_commands.py # LDAP CLI group
│   │   ├── user_commands.py  # User management commands
│   │   ├── group_commands.py # Group management commands
│   │   └── member_commands.py # Member listing commands
│   ├── elastic/            # Elasticsearch module
│   │   ├── elastic.py      # Elasticsearch client
│   │   └── click_commands.py # Elastic CLI commands
│   ├── kimaicli/           # Kimai module
│   │   ├── kimai.py        # Kimai REST API client
│   │   ├── click_commands.py # Kimai CLI group and master data
│   │   ├── timesheet_commands.py # Timesheet management
│   │   ├── booking.py      # Slot, date and preset logic
│   │   └── book_commands.py # Recurring booking command
│   ├── uptimecli/         # Uptime Kuma module
│   │   ├── uptime.py       # Uptime Kuma Socket.IO client
│   │   ├── click_commands.py # Uptime CLI group and instance data
│   │   ├── monitor_commands.py # Monitor management
│   │   └── maintenance_commands.py # Maintenance windows and downtimes
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

### Conventions

The repository conventions - module layout, list output, command options,
configuration contexts - are written down in [AGENTS.md](AGENTS.md). The most
visible one: **every listing goes through `pyadm.table`**, so all modules render
tables the same way (tabulate's `simple` format, lower-case field names as
headers, `--json`/`-j` for raw data, `--output`/`-o` to pick columns).

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
