"""Snapshot commands for VMs and containers.

Proxmox treats snapshots of QEMU guests and LXC containers almost identically:
same fields, same parent chain, same 'current' pseudo-entry. The commands are
therefore built once here and registered on both the `vm` and the `ct` group.
"""

import json
import logging
import sys
import time

import click

from pyadm.pvecli.pve_commands import get_pve_client, resolve_resource_id, get_task_id
from pyadm.pvecli.list_utils import (
    CURRENT_SNAPSHOT,
    SortError,
    newest_snaptime,
    oldest_snaptime,
    render_snapshot_overview,
    render_snapshot_table,
    render_snapshot_tree,
    sort_items,
)

# What differs between the two guest types: wording, the client methods to call,
# and whether a snapshot can include the memory state (QEMU only).
GUEST_KINDS = {
    "vm": {
        "label": "VM",
        "title": "VM",
        "plural": "VMs",
        "id_label": "VM ID or name",
        "metavar": "VMID",
        "resource_type": "vm",
        "list_guests": "get_vms",
        "get_snapshots": "get_vm_snapshots",
        "create_snapshot": "create_vm_snapshot",
        "delete_snapshot": "delete_vm_snapshot",
        "command": "pyadm pve vm",
        "supports_vmstate": True,
    },
    "container": {
        "label": "container",
        "title": "Container",
        "plural": "containers",
        "id_label": "Container ID or name",
        "metavar": "CTID",
        "resource_type": "container",
        "list_guests": "get_containers",
        "get_snapshots": "get_container_snapshots",
        "create_snapshot": "create_container_snapshot",
        "delete_snapshot": "delete_container_snapshot",
        "command": "pyadm pve ct",
        "supports_vmstate": False,
    },
}


def split_snapshots(snapshots):
    """Split the API response into real snapshots and the 'current' pseudo entry."""
    real = [s for s in snapshots if s.get('name') != CURRENT_SNAPSHOT]
    live = next((s for s in snapshots if s.get('name') == CURRENT_SNAPSHOT), None)
    return real, live


def _collect_snapshots(client, kind, guests, show_progress):
    """Collect snapshots for every guest, keeping going when a single one fails.

    Returns:
        (entries, errors) where entries are {guest fields, 'snapshots': [...]}
        dicts for guests that have at least one snapshot
    """
    get_snapshots = getattr(client, kind["get_snapshots"])
    entries, errors = [], []

    def handle(guest):
        try:
            snapshots, live = split_snapshots(get_snapshots(guest['node'], guest['vmid']))
        except Exception as e:
            errors.append((guest, e))
            return
        if snapshots:
            entries.append({
                'vmid': guest.get('vmid'),
                'name': guest.get('name'),
                'node': guest.get('node'),
                'status': guest.get('status'),
                'template': bool(guest.get('template', 0)),
                'snapshots': snapshots,
                # Kept aside so it never counts as a snapshot, but can still be drawn in the tree
                'live': live,
            })

    if show_progress:
        # One API call per guest, so a large cluster takes a noticeable moment
        label = f"Scanning {kind['plural']} for snapshots"
        with click.progressbar(guests, label=label, file=sys.stderr) as bar:
            for guest in bar:
                handle(guest)
    else:
        for guest in guests:
            handle(guest)

    return entries, errors


def register_snapshot_commands(group, kind_name):
    """Add the 'snapshots' group and the 'list-snapshots' shortcut to *group*.

    Args:
        group: The Click group of the guest type (``vm`` or ``ct``)
        kind_name: Key into GUEST_KINDS selecting the guest type
    """
    kind = GUEST_KINDS[kind_name]
    label, plural, metavar, command = kind["label"], kind["plural"], kind["metavar"], kind["command"]
    id_label, title = kind["id_label"], kind["title"]
    # Only QEMU snapshots can carry a memory state, so the column is pointless for LXC
    ram_column = kind["supports_vmstate"]

    @group.group("snapshots", context_settings={'help_option_names': ['-h', '--help']})
    def snapshots():
        pass

    snapshots.help = f"Manage snapshots of {plural}."

    @snapshots.command("list")
    @click.argument("guest", metavar=f"[{metavar}]", required=False)
    @click.option("--node", "-n", default=None, help=f"Filter by node name (or the node of {metavar})")
    @click.option("--older-than", type=float, default=None, metavar="DAYS",
                  help=f"Only show {plural} whose newest snapshot is older than DAYS")
    @click.option("--json", "-j", "json_output", is_flag=True, help="Output as JSON")
    @click.option("--tree", is_flag=True, help=f"Show the snapshot tree of every matching {label}")
    @click.option("--sort", default=None, help="Sort by fields (e.g. 'name,-snaps'; default: oldest first)")
    def list_snapshots(guest, node, older_than, json_output, tree, sort):
        try:
            client = get_pve_client()

            if guest:
                guest_id, guest_node = resolve_resource_id(client, guest, node, kind["resource_type"])
                raw = getattr(client, kind["get_snapshots"])(guest_node, guest_id)
                found, _ = split_snapshots(raw)

                if json_output:
                    click.echo(json.dumps(found, indent=2))
                    return

                if not found:
                    click.echo(f"No snapshots found for {label} '{guest}' (ID: {guest_id}) "
                               f"on node '{guest_node}'.")
                    return

                click.echo(f"Snapshots for {label} '{guest}' (ID: {guest_id}) on node '{guest_node}':")
                # Drawn from the raw list, so the live-state entry shows where the guest sits
                click.echo(render_snapshot_tree(raw, ram_column=ram_column))
                return

            guests = getattr(client, kind["list_guests"])(node)
            if node and not guests:
                raise click.ClickException(f"No {plural} found on node '{node}'.")

            entries, errors = _collect_snapshots(client, kind, guests, show_progress=not json_output)

            for failed, error in errors:
                click.echo(f"Warning: could not read snapshots of {label} {failed.get('vmid')} "
                           f"on node '{failed.get('node')}': {error}", err=True)

            if older_than is not None:
                cutoff = time.time() - older_than * 86400
                # Judge by the newest snapshot: an old one is fine if the guest is snapshotted regularly
                entries = [e for e in entries if (newest_snaptime(e['snapshots']) or 0) < cutoff]

            if json_output:
                click.echo(json.dumps([{k: v for k, v in e.items() if k != 'live'} for e in entries], indent=2))
                return

            if not entries:
                scope = f" on node '{node}'" if node else ""
                extra = f" older than {older_than:g} days" if older_than is not None else ""
                click.echo(f"No {plural} with snapshots{extra} found{scope}.")
                return

            if sort:
                try:
                    entries = sort_items(
                        [dict(e, snapshots_count=len(e['snapshots']),
                              oldest=oldest_snaptime(e['snapshots']),
                              newest=newest_snaptime(e['snapshots'])) for e in entries],
                        sort,
                        allowed_fields={"vmid", "name", "node", "status", "snaps", "snapshots", "oldest", "newest"},
                        field_map={"snaps": "snapshots_count", "snapshots": "snapshots_count"},
                    )
                except SortError as e:
                    raise click.ClickException(str(e))
            else:
                # Oldest snapshot first: the most likely forgotten one is on top
                entries.sort(key=lambda e: oldest_snaptime(e['snapshots']) or 0)

            total = sum(len(e['snapshots']) for e in entries)
            scope = f" on node '{node}'" if node else ""
            click.echo(f"{total} snapshot(s) across {len(entries)} {label}(s){scope}:")

            if tree:
                for entry in entries:
                    click.echo()
                    click.echo(f"{title} {entry['vmid']} '{entry['name']}' on node '{entry['node']}':")
                    live = [entry['live']] if entry.get('live') else []
                    click.echo(render_snapshot_tree(entry['snapshots'] + live, ram_column=ram_column))
            else:
                click.echo(render_snapshot_overview(entries, ram_column=ram_column))

        except click.ClickException:
            raise
        except Exception as e:
            logging.error(f"Error listing {label} snapshots: {e}")
            raise click.ClickException(f"Error listing {label} snapshots: {e}")

    list_snapshots.help = f"""
    List snapshots of all {plural}, or of a single {label}.

    Without {metavar} every {label} in the cluster is scanned, so forgotten
    snapshots become visible at a glance: one row per {label} that has
    snapshots, with how many there are and how old the oldest and newest of
    them is. {plural.capitalize()} without snapshots are left out.

    With {metavar} the snapshots of that one {label} are drawn as a tree, since
    every snapshot descends from the one that was active when it was taken. The
    'NOW' entry marks where the running {label} currently sits, which makes
    abandoned branches obvious.

    \b
    Examples:
        {command} snapshots list                      # Cluster-wide overview
        {command} snapshots list --older-than 30      # Stale ones only
        {command} snapshots list --node pve1 --tree   # Trees for one node
        {command} snapshots list 100                  # Tree of a single {label}
        {command} snapshots list --json
        {command} list-snapshots                      # Same, as a shortcut
    """

    # The cluster-wide overview is the common case, so it stays reachable without the group
    group.add_command(list_snapshots, "list-snapshots")

    create_options = [
        click.argument("guest", metavar=metavar),
        click.argument("name"),
        click.option("--node", "-n", default=None,
                     help=f"Node name (not needed if {label} name is unique)"),
        click.option("--description", "-d", default=None, help="Description stored with the snapshot"),
    ]
    if kind["supports_vmstate"]:
        create_options.append(
            click.option("--vmstate", is_flag=True, help="Also save the memory state of a running VM"))

    def create_snapshot(guest, name, node, description, vmstate=False):
        try:
            client = get_pve_client()

            guest_id, guest_node = resolve_resource_id(client, guest, node, kind["resource_type"])
            extra = {'vmstate': vmstate} if kind["supports_vmstate"] else {}
            result = getattr(client, kind["create_snapshot"])(
                guest_node, guest_id, name, description=description, **extra)
            state = " (including memory state)" if vmstate else ""
            click.echo(f"Snapshot '{name}' of {label} '{guest}' (ID: {guest_id}){state} initiated. "
                       f"Task ID: {get_task_id(result)}")

        except Exception as e:
            logging.error(f"Error creating {label} snapshot: {e}")
            raise click.ClickException(f"Error creating {label} snapshot: {e}")

    vmstate_help = """
    Without --vmstate only the disks are snapshotted, so a rollback boots the VM
    fresh. With --vmstate the memory is written out as well, which takes longer
    and occupies extra storage, but a rollback resumes the VM mid-run.
""" if kind["supports_vmstate"] else """
    Container snapshots always cover the disks only; a rollback therefore starts
    the container from the snapshotted filesystem rather than resuming it.
"""

    create_snapshot.__doc__ = f"""
    Create a snapshot of a {label}.

    \b
    {metavar}: {id_label}
    NAME: Name of the new snapshot
{vmstate_help}
    \b
    Examples:
        {command} snapshots create 100 before-upgrade
        {command} snapshots create my-guest before-upgrade -d "Ticket 4711"
    """

    command_create = snapshots.command("create")(create_snapshot)
    # Applied to an existing Command the decorators append in order, unlike on a function
    for option in create_options:
        option(command_create)

    @snapshots.command("delete")
    @click.argument("guest", metavar=metavar)
    @click.argument("names", nargs=-1, required=True)
    @click.option("--node", "-n", default=None, help=f"Node name (not needed if {label} name is unique)")
    @click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
    @click.option("--force", is_flag=True, help="Remove from the config even if the removal itself fails")
    def delete_snapshot(guest, names, node, yes, force):
        try:
            client = get_pve_client()

            guest_id, guest_node = resolve_resource_id(client, guest, node, kind["resource_type"])
            existing, _ = split_snapshots(getattr(client, kind["get_snapshots"])(guest_node, guest_id))
            by_name = {s.get('name'): s for s in existing}

            unknown = [n for n in names if n not in by_name]
            if unknown:
                known = ", ".join(sorted(by_name)) or "none"
                raise click.ClickException(
                    f"{title} '{guest}' has no snapshot named "
                    f"{', '.join(repr(n) for n in unknown)}. Existing: {known}")

            if not yes:
                click.echo(f"The following snapshots of {label} '{guest}' (ID: {guest_id}) will be deleted:")
                click.echo(render_snapshot_table([by_name[n] for n in names], ram_column=ram_column))
                if not click.confirm("Proceed?"):
                    click.echo("Snapshot deletion cancelled.")
                    return

            for name in names:
                result = getattr(client, kind["delete_snapshot"])(guest_node, guest_id, name, force=force)
                click.echo(f"Snapshot '{name}' of {label} '{guest}' (ID: {guest_id}) delete initiated. "
                           f"Task ID: {get_task_id(result)}")

        except click.ClickException:
            raise
        except Exception as e:
            logging.error(f"Error deleting {label} snapshot: {e}")
            raise click.ClickException(f"Error deleting {label} snapshot: {e}")

    delete_snapshot.help = f"""
    Delete one or more snapshots of a {label}.

    \b
    {metavar}: {id_label}
    NAMES: One or more snapshot names

    Deleting a snapshot does not change the running {label}, it only drops the
    state it could have been rolled back to. Child snapshots survive: they are
    re-attached to the parent of the deleted one.

    Several snapshots are deleted one after another; should Proxmox still be
    busy with the previous deletion, the next one fails with a lock error.

    \b
    Examples:
        {command} snapshots delete 100 kernel-test
        {command} snapshots delete my-guest old-1 old-2 --yes
    """

    return snapshots
