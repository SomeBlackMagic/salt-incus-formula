"""
Salt state module for managing Incus resources declaratively.

This module provides state functions for managing:
- Instances (containers and VMs)
- Instance snapshots with rotation policies
- Storage pools and volumes
- Networks
- Profiles
- Cluster members
- Images (basic presence/absence and public flag)

All state functions support test=True mode for dry-run.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "incus"


def __virtual__():
    """
    Only load if incus execution module is available.
    We check for the presence of the base instance_list function.
    """
    if "incus.instance_list" in __salt__:
        return __virtualname__
    return (False, "incus execution module is not available")


# ======================================================================
# Helpers
# ======================================================================

def _format_error_message(operation, resource_name, result, extra_info=None):
    """
    Format enhanced error message with troubleshooting information.

    :param operation: Operation being performed (e.g., "create", "update", "delete")
    :param resource_name: Name of the resource
    :param result: Result dict from execution module
    :param extra_info: Additional information dict (config, params, etc.)
    :return: Formatted error message string
    """
    error_msg = result.get('error', 'Unknown error')
    error_code = result.get('error_code')

    msg = f"Failed to {operation} {resource_name}: {error_msg}"

    # Add enhanced details for server errors (5xx)
    if error_code and 500 <= error_code < 600:
        msg += (
            f"\n\nServer Error (HTTP {error_code}). "
            f"Check Salt minion logs for detailed request/response information."
        )

        if extra_info:
            msg += "\n\nConfiguration sent:"
            for key, value in extra_info.items():
                msg += f"\n  - {key}: {value}"

        msg += (
            f"\n\nTroubleshooting:"
            f"\n  1. Verify all configuration values are valid for Incus"
            f"\n  2. Remove optional parameters one by one to isolate the issue"
            f"\n  3. Check detailed logs: /var/log/salt/minion"
            f"\n  4. Check Incus server logs: journalctl -u incus -n 50"
            f"\n  5. Test the API directly: incus query -X POST /1.0/... --data '{{}}'"
        )

    return msg


def _get_alias_info(alias_name):
    """
    Get alias information using incus.image_alias_get.
    Returns alias dict or None if not found.
    """
    result = __salt__["incus.image_alias_get"](alias_name)
    if result.get("success"):
        return result.get("alias")
    return None


def _find_image_by_alias(alias_name):
    """
    Find image fingerprint by alias using incus.image_alias_get.
    Returns fingerprint or None if not found.
    """
    alias_info = _get_alias_info(alias_name)
    if alias_info:
        return alias_info.get("target")
    return None


# ======================================================================
# Instance States
# ======================================================================

def instance_present(
    name,
    source=None,
    instance_type="container",
    config=None,
    devices=None,
    profiles=None,
    ephemeral=False,
):
    """
    Ensure an instance exists and optionally matches given config.

    :param name: Instance name
    :param source: Source configuration for creating instance
                   (see exec-module incus.instance_create)
    :param instance_type: "container" or "virtual-machine"
    :param config: Instance config (dict)
    :param devices: Devices dict
    :param profiles: List of profiles
    :param ephemeral: Whether instance is ephemeral

    Example:

    .. code-block:: yaml

        mycontainer:
          incus.instance_present:
            - source:
                type: image
                alias: ubuntu/22.04
            - config:
                limits.cpu: "2"
                limits.memory: 2GB
            - profiles:
                - default
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    instance_info = __salt__["incus.instance_get"](name)

    if instance_info.get("success"):
        # Instance exists, check if update is needed
        instance = instance_info.get("instance", {})
        changes = {}

        # Config changes
        if config:
            current_config = instance.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Profiles
        if profiles is not None:
            current_profiles = instance.get("profiles", []) or []
            if set(current_profiles) != set(profiles):
                changes["profiles"] = {
                    "old": current_profiles,
                    "new": profiles,
                }

        # Devices
        if devices:
            current_devices = instance.get("devices", {}) or {}
            device_changes = {}
            for dev_name, dev_conf in devices.items():
                if current_devices.get(dev_name) != dev_conf:
                    device_changes[dev_name] = {
                        "old": current_devices.get(dev_name),
                        "new": dev_conf,
                    }
            if device_changes:
                changes["devices"] = device_changes

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Instance {name} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.instance_update"](
                    name,
                    config=config,
                    devices=devices,
                    profiles=profiles,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Instance {name} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update instance {name}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Instance {name} already in desired state"
    else:
        # Instance doesn't exist, create it
        new_desc = {
            "name": name,
            "type": instance_type,
            "config": config,
            "devices": devices,
            "profiles": profiles,
            "ephemeral": ephemeral,
            "source": source,
        }

        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Instance {name} would be created"
            ret["changes"] = {"instance": {"old": None, "new": new_desc}}
        else:
            create_result = __salt__["incus.instance_create"](
                name,
                source=source,
                instance_type=instance_type,
                config=config,
                devices=devices,
                profiles=profiles,
                ephemeral=ephemeral,
            )

            if create_result.get("success"):
                ret["comment"] = f"Instance {name} created"
                ret["changes"] = {
                    "instance": {
                        "old": None,
                        "new": name,
                    }
                }
            else:
                ret["result"] = False
                ret["comment"] = (
                    f"Failed to create instance {name}: "
                    f"{create_result.get('error')}"
                )

    return ret


def instance_absent(name, force=False):
    """
    Ensure an instance does not exist.

    :param name: Instance name
    :param force: Force deletion even if running

    Example:

    .. code-block:: yaml

        old_container:
          incus.instance_absent:
            - force: True
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    instance_info = __salt__["incus.instance_get"](name)

    if instance_info.get("success"):
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Instance {name} would be deleted"
            ret["changes"] = {
                "instance": {
                    "old": name,
                    "new": None,
                }
            }
        else:
            delete_result = __salt__["incus.instance_delete"](name, force=force)
            if delete_result.get("success"):
                ret["comment"] = f"Instance {name} deleted"
                ret["changes"] = {
                    "instance": {
                        "old": name,
                        "new": None,
                    }
                }
            else:
                ret["result"] = False
                ret["comment"] = (
                    f"Failed to delete instance {name}: "
                    f"{delete_result.get('error')}"
                )
    else:
        ret["comment"] = f"Instance {name} already absent"

    return ret


def instance_running(name):
    """
    Ensure an instance is running.

    :param name: Instance name

    Example:

    .. code-block:: yaml

        mycontainer:
          incus.instance_running
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    instance_info = __salt__["incus.instance_get"](name)

    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {name} does not exist"
        return ret

    instance = instance_info.get("instance", {}) or {}
    status = instance.get("status", "")

    if status == "Running":
        ret["comment"] = f"Instance {name} is already running"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Instance {name} would be started"
        ret["changes"] = {
            "state": {
                "old": status,
                "new": "Running",
            }
        }
        return ret

    start_result = __salt__["incus.instance_start"](name)
    if start_result.get("success"):
        ret["comment"] = f"Instance {name} started"
        ret["changes"] = {
            "state": {
                "old": status,
                "new": "Running",
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to start instance {name}: "
            f"{start_result.get('error')}"
        )

    return ret


def instance_stopped(name, force=False):
    """
    Ensure an instance is stopped.

    :param name: Instance name
    :param force: Force stop

    Example:

    .. code-block:: yaml

        mycontainer:
          incus.instance_stopped:
            - force: True
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    instance_info = __salt__["incus.instance_get"](name)

    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {name} does not exist"
        return ret

    instance = instance_info.get("instance", {}) or {}
    status = instance.get("status", "")

    if status == "Stopped":
        ret["comment"] = f"Instance {name} is already stopped"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Instance {name} would be stopped"
        ret["changes"] = {
            "state": {
                "old": status,
                "new": "Stopped",
            }
        }
        return ret

    stop_result = __salt__["incus.instance_stop"](name, force=force)

    if stop_result.get("success"):
        ret["comment"] = f"Instance {name} stopped"
        ret["changes"] = {
            "state": {
                "old": status,
                "new": "Stopped",
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to stop instance {name}: "
            f"{stop_result.get('error')}"
        )

    return ret


# ======================================================================
# Instance Snapshot States
# ======================================================================

def instance_snapshot_present(instance, name, stateful=False, description=""):
    """
    Ensure an instance snapshot exists.

    :param instance: Instance name
    :param name: Snapshot name
    :param stateful: Whether to create a stateful snapshot (includes memory/runtime state)
    :param description: Snapshot description

    Example:

    .. code-block:: yaml

        before-update-snap:
          incus.instance_snapshot_present:
            - instance: mycontainer
            - name: before-update
            - stateful: False
            - description: Snapshot before system update

        vm-stateful-snap:
          incus.instance_snapshot_present:
            - instance: myvm
            - name: running-state
            - stateful: True
            - description: Snapshot with VM running state
    """
    ret = {
        "name": f"{instance}/{name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if instance exists
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {instance} does not exist"
        return ret

    # Check if snapshot exists
    snapshots = __salt__["incus.instance_snapshot_list"](instance, recursion=1)
    if not snapshots.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots.get('error')}"
        return ret

    snapshot_list = snapshots.get("snapshots", []) or []
    snapshot_exists = any(s.get("name") == name for s in snapshot_list)

    if snapshot_exists:
        ret["comment"] = f"Snapshot {name} already exists for instance {instance}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Snapshot {name} would be created for instance {instance}"
        ret["changes"] = {"snapshot": {"old": None, "new": name}}
        return ret

    # Create snapshot
    create_result = __salt__["incus.instance_snapshot_create"](
        instance, name, stateful=stateful, description=description
    )

    if create_result.get("success"):
        ret["comment"] = f"Snapshot {name} created for instance {instance}"
        ret["changes"] = {"snapshot": {"old": None, "new": name}}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to create snapshot {name}: {create_result.get('error')}"

    return ret


def instance_snapshot_absent(instance, name):
    """
    Ensure an instance snapshot does not exist.

    :param instance: Instance name
    :param name: Snapshot name

    Example:

    .. code-block:: yaml

        old-snapshot:
          incus.instance_snapshot_absent:
            - instance: mycontainer
            - name: old-snap
    """
    ret = {
        "name": f"{instance}/{name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if instance exists
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {instance} does not exist"
        return ret

    # Check if snapshot exists
    snapshots = __salt__["incus.instance_snapshot_list"](instance, recursion=1)
    if not snapshots.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots.get('error')}"
        return ret

    snapshot_list = snapshots.get("snapshots", []) or []
    snapshot_exists = any(s.get("name") == name for s in snapshot_list)

    if not snapshot_exists:
        ret["comment"] = f"Snapshot {name} already absent from instance {instance}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Snapshot {name} would be deleted from instance {instance}"
        ret["changes"] = {"snapshot": {"old": name, "new": None}}
        return ret

    # Delete snapshot
    delete_result = __salt__["incus.instance_snapshot_delete"](instance, name)

    if delete_result.get("success"):
        ret["comment"] = f"Snapshot {name} deleted from instance {instance}"
        ret["changes"] = {"snapshot": {"old": name, "new": None}}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to delete snapshot {name}: {delete_result.get('error')}"

    return ret


def instance_snapshot_restored(instance, name):
    """
    Ensure an instance is restored to a specific snapshot state.

    WARNING: This will restore the instance to the snapshot state,
    losing any changes made after the snapshot was created.

    :param instance: Instance name
    :param name: Snapshot name to restore

    Example:

    .. code-block:: yaml

        restore-before-update:
          incus.instance_snapshot_restored:
            - instance: mycontainer
            - name: before-update
    """
    ret = {
        "name": f"{instance}/{name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if instance exists
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {instance} does not exist"
        return ret

    # Check if snapshot exists
    snapshots = __salt__["incus.instance_snapshot_list"](instance, recursion=1)
    if not snapshots.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots.get('error')}"
        return ret

    snapshot_list = snapshots.get("snapshots", []) or []
    snapshot_exists = any(s.get("name") == name for s in snapshot_list)

    if not snapshot_exists:
        ret["result"] = False
        ret["comment"] = f"Snapshot {name} does not exist for instance {instance}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Instance {instance} would be restored to snapshot {name}"
        ret["changes"] = {
            "restored": {
                "old": "current state",
                "new": f"snapshot {name}",
            }
        }
        return ret

    # Restore snapshot
    restore_result = __salt__["incus.instance_snapshot_restore"](instance, name)

    if restore_result.get("success"):
        ret["comment"] = f"Instance {instance} restored to snapshot {name}"
        ret["changes"] = {
            "restored": {
                "old": "current state",
                "new": f"snapshot {name}",
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to restore snapshot {name}: {restore_result.get('error')}"

    return ret


def instance_snapshots_managed(instance, snapshots_config):
    """
    Manage multiple snapshots for an instance with rotation policy.

    This state ensures that specified snapshots exist and automatically
    rotates old snapshots based on retention policies. It supports:
    - Creating multiple snapshots with different configurations
    - Automatic snapshot rotation based on keep count
    - Pattern-based snapshot management (e.g., daily-*, weekly-*)
    - Expiry date management

    :param instance: Instance name
    :param snapshots_config: Dictionary of snapshot configurations

    Each snapshot configuration can include:
    - name: Snapshot name (required)
    - stateful: Whether to create stateful snapshot (default: False)
    - description: Snapshot description
    - keep: Number of snapshots to keep for this pattern (rotation)
    - pattern: Name pattern for rotation (e.g., "daily-*")
    - expires_at: Expiry date in ISO format

    Example:

    .. code-block:: yaml

        web-container-snapshots:
          incus.instance_snapshots_managed:
            - instance: web-container
            - snapshots_config:
                daily:
                  name: daily-{{ salt['cmd.run']('date +%Y%m%d') }}
                  stateful: False
                  description: Daily automated snapshot
                  pattern: daily-*
                  keep: 7
                weekly:
                  name: weekly-{{ salt['cmd.run']('date +%YW%V') }}
                  stateful: False
                  description: Weekly automated snapshot
                  pattern: weekly-*
                  keep: 4
                before-update:
                  name: before-update
                  stateful: False
                  description: Pre-update snapshot
                  keep: 3
    """
    ret = {
        "name": f"{instance}_snapshots",
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if instance exists
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {instance} does not exist"
        return ret

    # Get current snapshots
    snapshots_result = __salt__["incus.instance_snapshot_list"](instance, recursion=1)
    if not snapshots_result.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots_result.get('error')}"
        return ret

    current_snapshots = snapshots_result.get("snapshots", []) or []
    current_snapshot_names = [s.get("name") for s in current_snapshots]

    changes = {}
    snapshots_created = []
    snapshots_rotated = []

    # Process each snapshot configuration
    for snap_id, snap_config in (snapshots_config or {}).items():
        snap_name = snap_config.get("name")
        if not snap_name:
            ret["result"] = False
            ret["comment"] = f"Snapshot configuration '{snap_id}' missing 'name' field"
            return ret

        stateful = snap_config.get("stateful", False)
        description = snap_config.get("description", "")
        keep = snap_config.get("keep")
        pattern = snap_config.get("pattern")
        expires_at = snap_config.get("expires_at")

        # Check if snapshot needs to be created
        if snap_name not in current_snapshot_names:
            if __opts__.get("test"):
                snapshots_created.append(snap_name)
            else:
                # Create snapshot
                create_result = __salt__["incus.instance_snapshot_create"](
                    instance, snap_name, stateful=stateful, description=description
                )
                if not create_result.get("success"):
                    ret["result"] = False
                    ret["comment"] = f"Failed to create snapshot {snap_name}: {create_result.get('error')}"
                    return ret

                snapshots_created.append(snap_name)

                # Update expires_at if specified
                if expires_at:
                    update_result = __salt__["incus.instance_snapshot_update"](
                        instance, snap_name, expires_at=expires_at
                    )
                    if not update_result.get("success"):
                        log.warning(f"Failed to set expiry for snapshot {snap_name}: {update_result.get('error')}")

        # Handle rotation if pattern and keep are specified
        if pattern and keep is not None:
            import fnmatch

            # Find all snapshots matching the pattern
            matching_snapshots = [
                s for s in current_snapshots
                if fnmatch.fnmatch(s.get("name", ""), pattern)
            ]

            # Sort by creation time (oldest first)
            matching_snapshots.sort(key=lambda s: s.get("created_at", ""))

            # If we have more than 'keep' snapshots, delete the oldest ones
            if len(matching_snapshots) > keep:
                to_delete = matching_snapshots[:len(matching_snapshots) - keep]

                for snap_to_delete in to_delete:
                    del_name = snap_to_delete.get("name")
                    if __opts__.get("test"):
                        snapshots_rotated.append(del_name)
                    else:
                        delete_result = __salt__["incus.instance_snapshot_delete"](instance, del_name)
                        if delete_result.get("success"):
                            snapshots_rotated.append(del_name)
                        else:
                            log.warning(f"Failed to delete snapshot {del_name} during rotation: {delete_result.get('error')}")

    # Build changes dict
    if snapshots_created:
        changes["created"] = {"old": None, "new": snapshots_created}

    if snapshots_rotated:
        changes["rotated"] = {"old": snapshots_rotated, "new": None}

    if changes:
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Instance {instance} snapshots would be managed"
        else:
            ret["comment"] = f"Instance {instance} snapshots managed successfully"
        ret["changes"] = changes
    else:
        ret["comment"] = f"Instance {instance} snapshots already in desired state"

    return ret


def instance_snapshots_rotated(instance, pattern, keep):
    """
    Ensure snapshots matching a pattern are rotated, keeping only the newest N.

    This state is useful for implementing snapshot retention policies.
    It will delete the oldest snapshots that match the specified pattern,
    keeping only the specified number of the most recent ones.

    :param instance: Instance name
    :param pattern: Snapshot name pattern (supports wildcards like "daily-*")
    :param keep: Number of snapshots to keep

    Example:

    .. code-block:: yaml

        rotate-daily-snapshots:
          incus.instance_snapshots_rotated:
            - instance: web-container
            - pattern: daily-*
            - keep: 7

        rotate-weekly-snapshots:
          incus.instance_snapshots_rotated:
            - instance: web-container
            - pattern: weekly-*
            - keep: 4

        rotate-backup-snapshots:
          incus.instance_snapshots_rotated:
            - instance: database
            - pattern: backup-*
            - keep: 10
    """
    import fnmatch

    ret = {
        "name": f"{instance}_rotate_{pattern}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if instance exists
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Instance {instance} does not exist"
        return ret

    # Get current snapshots
    snapshots_result = __salt__["incus.instance_snapshot_list"](instance, recursion=1)
    if not snapshots_result.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots_result.get('error')}"
        return ret

    current_snapshots = snapshots_result.get("snapshots", []) or []

    # Find all snapshots matching the pattern
    matching_snapshots = [
        s for s in current_snapshots
        if fnmatch.fnmatch(s.get("name", ""), pattern)
    ]

    # Sort by creation time (oldest first)
    matching_snapshots.sort(key=lambda s: s.get("created_at", ""))

    # Check if rotation is needed
    if len(matching_snapshots) <= keep:
        ret["comment"] = f"Snapshot rotation not needed: {len(matching_snapshots)} snapshots (keeping {keep})"
        return ret

    # Calculate which snapshots to delete
    to_delete = matching_snapshots[:len(matching_snapshots) - keep]
    to_delete_names = [s.get("name") for s in to_delete]

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Would delete {len(to_delete)} old snapshots matching pattern '{pattern}'"
        ret["changes"] = {
            "deleted": {
                "old": to_delete_names,
                "new": None,
            }
        }
        return ret

    # Delete old snapshots
    deleted = []
    failed = []

    for snap in to_delete:
        snap_name = snap.get("name")
        delete_result = __salt__["incus.instance_snapshot_delete"](instance, snap_name)
        if delete_result.get("success"):
            deleted.append(snap_name)
        else:
            failed.append({
                "name": snap_name,
                "error": delete_result.get("error")
            })

    # Build result
    if deleted:
        ret["changes"] = {
            "deleted": {
                "old": deleted,
                "new": None,
            }
        }

    if failed:
        ret["result"] = False
        ret["comment"] = f"Failed to delete some snapshots: {failed}"
    else:
        ret["comment"] = f"Deleted {len(deleted)} old snapshots matching pattern '{pattern}'"

    return ret


# ======================================================================
# Image States
# ======================================================================

def image_present(
    name,
    fingerprint=None,
    source=None,
    public=None,
    auto_update=None,
    aliases=None,
    properties=None,
    expires_at=None,
    compression_algorithm=None,
):
    """
    Ensure an Incus image exists and matches all specified parameters.

    The state name (name parameter) is ALWAYS used as the primary alias for the image.
    Additional aliases can be specified via the 'aliases' parameter.

    :param name: State name - ALWAYS becomes an alias for the image
    :param fingerprint: Image fingerprint for exact search
    :param source: Import source (dict with server/alias or file path)
    :param public: Public access to image
    :param auto_update: Automatic image update
    :param aliases: List of additional aliases (name is always included)
    :param properties: Image properties
    :param expires_at: Expiration time (ISO 8601)
    :param compression_algorithm: Compression algorithm

    Image search logic:
      1. By fingerprint (if specified) - most accurate method
      2. By name alias (via API)
      3. By any alias in the aliases list
      4. By source.alias (for remote imports)

    Fields supported for reconciliation:
      - public
      - auto_update
      - aliases (name + additional aliases)
      - properties
      - expires_at
      - compression_algorithm

    Example:

    .. code-block:: yaml

        ubuntu2204:
          incus.image_present:
            - source:
                server: https://images.linuxcontainers.org
                alias: ubuntu/22.04
                protocol: simplestreams
            - auto_update: True
            - aliases:
                - ubuntu-latest
                - ubuntu-lts

        my-custom-image:
          incus.image_present:
            - source: /tmp/rootfs.tar.xz
            - public: True
            - aliases:
                - custom-base
                - app-template
    """

    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # ============================
    # 1. Build complete alias list
    # ============================
    # Name is ALWAYS the primary alias
    desired_aliases = [name]

    # Add additional aliases if provided
    if aliases:
        for a in aliases:
            if a not in desired_aliases:
                desired_aliases.append(a)

    # ============================
    # 2. Search for existing image
    # ============================
    image_match = None

    # Get list of images
    images = __salt__["incus.image_list"](recursion=1)
    if not images.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list images: {images.get('error')}"
        return ret

    existing_images = images.get("images", [])

    # Search by fingerprint (highest priority)
    if fingerprint:
        for img in existing_images:
            if img.get("fingerprint") == fingerprint:
                image_match = img
                break

    # Search by name alias via API
    if not image_match:
        fp = _find_image_by_alias(name)
        if fp:
            for img in existing_images:
                if img.get("fingerprint") == fp:
                    image_match = img
                    break

    # Search by additional aliases
    if not image_match and aliases:
        for search_alias in aliases:
            fp = _find_image_by_alias(search_alias)
            if fp:
                for img in existing_images:
                    if img.get("fingerprint") == fp:
                        image_match = img
                        break
                if image_match:
                    break

    # Search by source.alias if provided
    if not image_match and isinstance(source, dict) and source.get("alias"):
        fp = _find_image_by_alias(source["alias"])
        if fp:
            for img in existing_images:
                if img.get("fingerprint") == fp:
                    image_match = img
                    break

    # ========================================================
    # 3. Image is absent → import
    # ========================================================
    if not image_match:
        if not source:
            ret["result"] = False
            ret["comment"] = "Image not found and no source specified for import"
            return ret

        if __opts__.get("test"):
            ret["result"] = None
            ret["changes"]["image"] = {"old": None, "new": source}
            ret["changes"]["aliases"] = {"old": None, "new": desired_aliases}
            ret["comment"] = "Image would be imported"
            return ret

        # Remote import
        if isinstance(source, dict) and source.get("server"):
            imp = __salt__["incus.image_create_from_remote"](
                source["server"],
                alias=source.get("alias"),
                protocol=source.get("protocol", "simplestreams"),
                auto_update=auto_update if auto_update is not None else False,
                public=public if public is not None else False,
                aliases=desired_aliases,
                properties=properties,
            )

            if not imp.get("success"):
                ret["result"] = False
                ret["comment"] = f"Failed to import image: {imp.get('error', 'Unknown error')}"
                return ret

            fingerprint = imp.get("fingerprint")

        # Local import from file
        elif isinstance(source, str):
            imp = __salt__["incus.image_create_from_file"](
                source,
                public=public if public is not None else False,
                properties=properties,
                aliases=desired_aliases,
                auto_update=auto_update if auto_update is not None else False,
            )

            if not imp.get("success"):
                ret["result"] = False
                ret["comment"] = f"Failed to import image: {imp.get('error', 'Unknown error')}"
                return ret

            fingerprint = imp.get("fingerprint")

        else:
            ret["result"] = False
            ret["comment"] = "Invalid source for image import (must be dict with 'server' or file path string)"
            return ret

        # Refresh image list
        updated = __salt__["incus.image_list"](recursion=1)
        if not updated.get("success"):
            ret["result"] = False
            ret["comment"] = f"Failed to refresh image list: {updated.get('error')}"
            return ret

        for img in updated.get("images", []):
            if img.get("fingerprint") == fingerprint:
                image_match = img
                break

        ret["changes"]["imported"] = {"old": None, "new": fingerprint}
        ret["changes"]["aliases"] = {"old": None, "new": desired_aliases}
        ret["comment"] = f"Image imported with fingerprint {fingerprint}"
        return ret

    # ========================================================
    # 4. Image exists → compare and update fields
    # ========================================================
    current = image_match
    diff = {}

    # Check public flag
    if public is not None:
        cur = bool(current.get("public"))
        if cur != bool(public):
            diff["public"] = {"old": cur, "new": public}

    # Check auto_update
    if auto_update is not None:
        cur = bool(current.get("auto_update", False))
        if cur != bool(auto_update):
            diff["auto_update"] = {"old": cur, "new": auto_update}

    # Check aliases
    # Get current aliases via API
    all_aliases_result = __salt__["incus.image_alias_list"](recursion=1)
    if all_aliases_result.get("success"):
        all_aliases = all_aliases_result.get("aliases", [])
        # Filter only aliases for current image
        current_aliases = []
        for alias_obj in all_aliases:
            if isinstance(alias_obj, dict):
                if alias_obj.get("target") == current.get("fingerprint"):
                    alias_name = alias_obj.get("name")
                    if alias_name:
                        current_aliases.append(alias_name)
    else:
        current_aliases = []

    cur_sorted = sorted(current_aliases)
    new_sorted = sorted(desired_aliases)

    if cur_sorted != new_sorted:
        diff["aliases"] = {"old": cur_sorted, "new": new_sorted}

    # Check properties
    if properties is not None:
        cur = current.get("properties", {})
        if cur != properties:
            diff["properties"] = {"old": cur, "new": properties}

    # Check expires_at
    if expires_at is not None:
        cur = current.get("expires_at")
        if cur != expires_at:
            diff["expires_at"] = {"old": cur, "new": expires_at}

    # Check compression_algorithm
    if compression_algorithm is not None:
        cur = current.get("compression_algorithm")
        if cur != compression_algorithm:
            diff["compression_algorithm"] = {"old": cur, "new": compression_algorithm}

    # ========================================================
    # 5. Apply updates if needed
    # ========================================================
    if not diff:
        ret["comment"] = f"Image already present with alias {name} and up-to-date"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["changes"] = diff
        ret["comment"] = "Image would be updated"
        return ret

    # Apply updates
    update_body = {k: v["new"] for k, v in diff.items()}

    upd = __salt__["incus.image_update"](current["fingerprint"], update_body)
    if not upd.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to update image: {upd.get('error', 'Unknown error')}"
        return ret

    ret["changes"] = diff
    ret["comment"] = f"Image updated with alias {name}"

    return ret

def image_absent(fingerprint=None, alias=None):
    """
    Ensure an image is absent locally.

    :param fingerprint: Optional fingerprint
    :param alias: Optional alias (search via API)

    Example:

    .. code-block:: yaml

        remove_old_image:
          incus.image_absent:
            - alias: old-template
    """
    ret = {
        "name": alias or fingerprint or "image",
        "result": True,
        "changes": {},
        "comment": "",
    }

    fp = None

    # Search by alias via API
    if alias:
        fp = _find_image_by_alias(alias)

    # Search by fingerprint
    if not fp and fingerprint:
        fp = fingerprint

    if not fp:
        ret["comment"] = "Image already absent"
        return ret

    # Check that image exists
    image_info = __salt__["incus.image_get"](fp)
    if not image_info.get("success"):
        ret["comment"] = "Image already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["changes"] = {"old": fp, "new": None}
        ret["comment"] = "Image would be removed"
        return ret

    delete = __salt__["incus.image_delete"](fp)

    if delete.get("success"):
        ret["comment"] = "Image removed"
        ret["changes"] = {"old": fp, "new": None}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to delete image: {delete.get('error')}"

    return ret


def image_installed(
    name,
    fingerprint=None,
    source=None,
    auto_update=False,
    public=False,
    aliases=None,
    properties=None,
):
    """
    Ensure a single Incus image is imported and configured.

    This is a thin-wrapper over image_present, which allows convenient
    iteration over pillars. The state name becomes the primary alias.

    .. code-block:: yaml

        {% for img_name, img in pillar.get('incus_images', {}).items() %}
        {{ img_name }}:
          incus.image_installed:
            - fingerprint: {{ img.get('fingerprint') }}
            - source: {{ img.get('source') }}
            - auto_update: {{ img.get('auto_update', False) }}
            - public: {{ img.get('public', False) }}
            - aliases: {{ img.get('aliases', []) }}
        {% endfor %}
    """
    return image_present(
        name=name,
        fingerprint=fingerprint,
        source=source,
        auto_update=auto_update,
        public=public,
        aliases=aliases,
        properties=properties,
    )


# ======================================================================
# Storage States
# ======================================================================
# Storage Pools: storage_pool_present, storage_pool_absent, storage_pool_config
# Storage Volumes: volume_present, volume_absent, volume_config
# Volume Snapshots: volume_snapshot_present, volume_snapshot_absent
# Volume Attachment: volume_attached, volume_detached

def storage_pool_present(name, driver, config=None, description=""):
    """
    Ensure a storage pool exists.

    :param name: Pool name
    :param driver: Storage driver (dir, zfs, btrfs, lvm, ceph)
    :param config: Pool configuration (dict)
    :param description: Pool description

    Example:

    .. code-block:: yaml

        mypool:
          incus.storage_pool_present:
            - driver: dir
            - config:
                source: /var/lib/incus/storage-pools/mypool
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    pools = __salt__["incus.storage_pool_list"](recursion=1)
    if not pools.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list storage pools: {pools.get('error')}"
        return ret

    pool_list = pools.get("pools", []) or []
    pool_exists = any(p.get("name") == name for p in pool_list)

    if pool_exists:
        ret["comment"] = f"Storage pool {name} already exists"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Storage pool {name} would be created"
        ret["changes"] = {
            "pool": {"old": None, "new": name},
        }
        return ret

    create_result = __salt__["incus.storage_pool_create"](
        name,
        driver,
        config=config,
        description=description,
    )

    if create_result.get("success"):
        ret["comment"] = f"Storage pool {name} created"
        ret["changes"] = {
            "pool": {"old": None, "new": name},
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to create storage pool {name}: "
            f"{create_result.get('error')}"
        )

    return ret


def storage_pool_absent(name):
    """
    Ensure a storage pool does not exist.

    :param name: Pool name

    Example:

    .. code-block:: yaml

        old_pool:
          incus.storage_pool_absent
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    pools = __salt__["incus.storage_pool_list"](recursion=1)
    if not pools.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list storage pools: {pools.get('error')}"
        return ret

    pool_list = pools.get("pools", []) or []
    pool_exists = any(p.get("name") == name for p in pool_list)

    if not pool_exists:
        ret["comment"] = f"Storage pool {name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Storage pool {name} would be deleted"
        ret["changes"] = {
            "pool": {
                "old": name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.storage_pool_delete"](name)

    if delete_result.get("success"):
        ret["comment"] = f"Storage pool {name} deleted"
        ret["changes"] = {
            "pool": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete storage pool {name}: "
            f"{delete_result.get('error')}"
        )

    return ret


def volume_present(name, pool, volume_type="custom", config=None, description=""):
    """
    Ensure a storage volume exists.

    :param name: Volume name
    :param pool: Pool name
    :param volume_type: Volume type (custom, image, container, virtual-machine)
    :param config: Volume configuration
    :param description: Volume description

    Example:

    .. code-block:: yaml

        myvolume:
          incus.volume_present:
            - pool: default
            - config:
                size: 10GB
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    volumes = __salt__["incus.volume_list"](pool, recursion=1)
    if not volumes.get("success"):
        ret["result"] = False
        ret["comment"] = (
            f"Failed to list volumes in pool {pool}: "
            f"{volumes.get('error')}"
        )
        return ret

    volume_list = volumes.get("volumes", []) or []
    volume_exists = any(
        v.get("name") == name and v.get("type") == volume_type
        for v in volume_list
    )

    if volume_exists:
        ret["comment"] = f"Volume {name} already exists in pool {pool}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Volume {name} would be created in pool {pool}"
        ret["changes"] = {
            "volume": {
                "old": None,
                "new": name,
            }
        }
        return ret

    create_result = __salt__["incus.volume_create"](
        pool,
        name,
        volume_type=volume_type,
        config=config,
        description=description,
    )

    if create_result.get("success"):
        ret["comment"] = f"Volume {name} created in pool {pool}"
        ret["changes"] = {
            "volume": {
                "old": None,
                "new": name,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to create volume {name}: "
            f"{create_result.get('error')}"
        )

    return ret


def volume_absent(name, pool, volume_type="custom"):
    """
    Ensure a storage volume does not exist.

    :param name: Volume name
    :param pool: Pool name
    :param volume_type: Volume type

    Example:

    .. code-block:: yaml

        old_volume:
          incus.volume_absent:
            - pool: default
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    volumes = __salt__["incus.volume_list"](pool, recursion=1)
    if not volumes.get("success"):
        ret["result"] = False
        ret["comment"] = (
            f"Failed to list volumes in pool {pool}: "
            f"{volumes.get('error')}"
        )
        return ret

    volume_list = volumes.get("volumes", []) or []
    volume_exists = any(
        v.get("name") == name and v.get("type") == volume_type
        for v in volume_list
    )

    if not volume_exists:
        ret["comment"] = f"Volume {name} already absent from pool {pool}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = (
            f"Volume {name} would be deleted from pool {pool}"
        )
        ret["changes"] = {
            "volume": {
                "old": name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.volume_delete"](pool, name, volume_type)

    if delete_result.get("success"):
        ret["comment"] = f"Volume {name} deleted from pool {pool}"
        ret["changes"] = {
            "volume": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete volume {name}: "
            f"{delete_result.get('error')}"
        )

    return ret


def storage_pool_config(name, config, description=None):
    """
    Ensure a storage pool has specific configuration.

    :param name: Pool name
    :param config: Configuration dict to apply
    :param description: Pool description to update (optional)

    Example:

    .. code-block:: yaml

        mypool:
          incus.storage_pool_config:
            - config:
                rsync.bwlimit: "100"
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current pool info
    pool_info = __salt__["incus.storage_pool_get"](name)
    if not pool_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get pool {name}: {pool_info.get('error')}"
        return ret

    current_pool = pool_info.get("pool", {})
    current_config = current_pool.get("config", {})
    current_description = current_pool.get("description", "")

    # Check what needs to be updated
    config_changes = {}
    for key, value in (config or {}).items():
        if current_config.get(key) != value:
            config_changes[key] = {"old": current_config.get(key), "new": value}

    description_changed = description is not None and current_description != description

    if not config_changes and not description_changed:
        ret["comment"] = f"Storage pool {name} already has desired configuration"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Storage pool {name} configuration would be updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
        return ret

    # Apply updates
    update_result = __salt__["incus.storage_pool_update"](
        name, config=config, description=description
    )

    if update_result.get("success"):
        ret["comment"] = f"Storage pool {name} configuration updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update pool {name}: {update_result.get('error')}"

    return ret


def volume_config(name, pool, volume_type="custom", config=None, description=None):
    """
    Ensure a storage volume has specific configuration.

    :param name: Volume name
    :param pool: Pool name
    :param volume_type: Volume type
    :param config: Configuration dict to apply
    :param description: Volume description to update (optional)

    Example:

    .. code-block:: yaml

        myvolume:
          incus.volume_config:
            - pool: default
            - config:
                size: 20GiB
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current volume info
    volume_info = __salt__["incus.volume_get"](pool, name, volume_type)
    if not volume_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get volume {name}: {volume_info.get('error')}"
        return ret

    current_volume = volume_info.get("volume", {})
    current_config = current_volume.get("config", {})
    current_description = current_volume.get("description", "")

    # Check what needs to be updated
    config_changes = {}
    for key, value in (config or {}).items():
        if current_config.get(key) != value:
            config_changes[key] = {"old": current_config.get(key), "new": value}

    description_changed = description is not None and current_description != description

    if not config_changes and not description_changed:
        ret["comment"] = f"Volume {name} already has desired configuration"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Volume {name} configuration would be updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
        return ret

    # Apply updates
    update_result = __salt__["incus.volume_update"](
        pool, name, volume_type=volume_type, config=config, description=description
    )

    if update_result.get("success"):
        ret["comment"] = f"Volume {name} configuration updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update volume {name}: {update_result.get('error')}"

    return ret


def volume_snapshot_present(name, pool, volume, volume_type="custom", description=""):
    """
    Ensure a volume snapshot exists.

    :param name: Snapshot name
    :param pool: Pool name
    :param volume: Volume name
    :param volume_type: Volume type
    :param description: Snapshot description

    Example:

    .. code-block:: yaml

        snap1:
          incus.volume_snapshot_present:
            - pool: default
            - volume: myvolume
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if snapshot exists
    snapshots = __salt__["incus.volume_snapshot_list"](pool, volume, volume_type, recursion=1)
    if not snapshots.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots.get('error')}"
        return ret

    snapshot_list = snapshots.get("snapshots", []) or []
    snapshot_exists = any(s.get("name") == name for s in snapshot_list)

    if snapshot_exists:
        ret["comment"] = f"Snapshot {name} already exists for volume {volume}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Snapshot {name} would be created for volume {volume}"
        ret["changes"] = {"snapshot": {"old": None, "new": name}}
        return ret

    # Create snapshot
    create_result = __salt__["incus.volume_snapshot_create"](
        pool, volume, name, volume_type=volume_type, description=description
    )

    if create_result.get("success"):
        ret["comment"] = f"Snapshot {name} created for volume {volume}"
        ret["changes"] = {"snapshot": {"old": None, "new": name}}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to create snapshot {name}: {create_result.get('error')}"

    return ret


def volume_snapshot_absent(name, pool, volume, volume_type="custom"):
    """
    Ensure a volume snapshot does not exist.

    :param name: Snapshot name
    :param pool: Pool name
    :param volume: Volume name
    :param volume_type: Volume type

    Example:

    .. code-block:: yaml

        old_snap:
          incus.volume_snapshot_absent:
            - pool: default
            - volume: myvolume
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Check if snapshot exists
    snapshots = __salt__["incus.volume_snapshot_list"](pool, volume, volume_type, recursion=1)
    if not snapshots.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list snapshots: {snapshots.get('error')}"
        return ret

    snapshot_list = snapshots.get("snapshots", []) or []
    snapshot_exists = any(s.get("name") == name for s in snapshot_list)

    if not snapshot_exists:
        ret["comment"] = f"Snapshot {name} already absent from volume {volume}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Snapshot {name} would be deleted from volume {volume}"
        ret["changes"] = {"snapshot": {"old": name, "new": None}}
        return ret

    # Delete snapshot
    delete_result = __salt__["incus.volume_snapshot_delete"](pool, volume, name, volume_type)

    if delete_result.get("success"):
        ret["comment"] = f"Snapshot {name} deleted from volume {volume}"
        ret["changes"] = {"snapshot": {"old": name, "new": None}}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to delete snapshot {name}: {delete_result.get('error')}"

    return ret


def volume_attached(name, pool, instance, device_name=None, path=None, volume_type="custom"):
    """
    Ensure a volume is attached to an instance.

    :param name: Volume name
    :param pool: Pool name
    :param instance: Instance name
    :param device_name: Device name (defaults to volume name)
    :param path: Mount path inside instance
    :param volume_type: Volume type

    Example:

    .. code-block:: yaml

        myvolume:
          incus.volume_attached:
            - pool: default
            - instance: mycontainer
            - path: /mnt/data
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    device_name = device_name or name

    # Get instance info
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get instance {instance}: {instance_info.get('error')}"
        return ret

    current_devices = instance_info.get("instance", {}).get("devices", {})

    # Check if device already attached
    if device_name in current_devices:
        device = current_devices[device_name]
        if (
            device.get("type") == "disk"
            and device.get("pool") == pool
            and device.get("source") == name
        ):
            ret["comment"] = f"Volume {name} already attached to instance {instance}"
            return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Volume {name} would be attached to instance {instance}"
        ret["changes"] = {
            "device": {
                "old": current_devices.get(device_name),
                "new": {
                    "type": "disk",
                    "pool": pool,
                    "source": name,
                    "path": path,
                },
            }
        }
        return ret

    # Attach volume
    new_devices = {
        device_name: {
            "type": "disk",
            "pool": pool,
            "source": name,
        }
    }
    if path:
        new_devices[device_name]["path"] = path

    update_result = __salt__["incus.instance_update"](instance, devices=new_devices)

    if update_result.get("success"):
        ret["comment"] = f"Volume {name} attached to instance {instance}"
        ret["changes"] = {
            "device": {
                "old": current_devices.get(device_name),
                "new": new_devices[device_name],
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to attach volume {name}: {update_result.get('error')}"

    return ret


def volume_detached(name, pool, instance, device_name=None):
    """
    Ensure a volume is detached from an instance.

    :param name: Volume name
    :param pool: Pool name
    :param instance: Instance name
    :param device_name: Device name (defaults to volume name)

    Example:

    .. code-block:: yaml

        myvolume:
          incus.volume_detached:
            - pool: default
            - instance: mycontainer
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    device_name = device_name or name

    # Get instance info
    instance_info = __salt__["incus.instance_get"](instance)
    if not instance_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get instance {instance}: {instance_info.get('error')}"
        return ret

    current_devices = instance_info.get("instance", {}).get("devices", {})

    # Check if device is attached
    if device_name not in current_devices:
        ret["comment"] = f"Volume {name} already detached from instance {instance}"
        return ret

    device = current_devices[device_name]
    if device.get("pool") != pool or device.get("source") != name:
        ret["comment"] = f"Device {device_name} is not volume {name} from pool {pool}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Volume {name} would be detached from instance {instance}"
        ret["changes"] = {"device": {"old": device, "new": None}}
        return ret

    # Detach volume by updating instance without this device
    remaining_devices = {k: v for k, v in current_devices.items() if k != device_name}

    # Get full instance config to update
    instance_data = instance_info.get("instance", {})
    instance_data["devices"] = remaining_devices

    # We need to use a different approach - remove the device
    # Using instance_update with empty devices dict for the specific device
    update_result = __salt__["incus.instance_update"](
        instance,
        devices={device_name: {}}  # Empty dict removes the device
    )

    if update_result.get("success"):
        ret["comment"] = f"Volume {name} detached from instance {instance}"
        ret["changes"] = {"device": {"old": device, "new": None}}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to detach volume {name}: {update_result.get('error')}"

    return ret


# ======================================================================
# Network States
# ======================================================================

def network_present(name, network_type="bridge", config=None, description=""):
    """
    Ensure a network exists with all specified parameters.

    :param name: Network name
    :param network_type: Network type (bridge, macvlan, sriov, ovn, physical)
    :param config: Network configuration (dict)
    :param description: Network description

    Supports all network configuration parameters including:
    - ipv4.address, ipv4.nat, ipv4.dhcp, ipv4.routing
    - ipv6.address, ipv6.nat, ipv6.dhcp, ipv6.routing
    - dns.domain, dns.mode, dns.search
    - bridge.driver, bridge.external_interfaces, bridge.hwaddr, bridge.mtu
    - network, parent, mtu, vlan
    - And many other network-specific parameters

    Example:

    .. code-block:: yaml

        mybr0:
          incus.network_present:
            - network_type: bridge
            - config:
                ipv4.address: 10.0.0.1/24
                ipv4.nat: "true"
                ipv4.dhcp: "true"
                ipv4.dhcp.ranges: 10.0.0.100-10.0.0.200
                ipv6.address: none
                dns.domain: incus
                dns.mode: managed
            - description: Main bridge network
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    network_info = __salt__["incus.network_get"](name)

    if network_info.get("success"):
        # Network exists, check for updates
        current_network = network_info.get("network", {}) or {}
        changes = {}

        # Check config changes
        if config:
            current_config = current_network.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description changes
        if description is not None:
            current_desc = current_network.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network {name} would be updated"
                ret["changes"] = changes
            else:
                # Update config if needed
                if "config" in changes:
                    update_result = __salt__["incus.network_update"](name, config)
                    if not update_result.get("success"):
                        ret["result"] = False
                        ret["comment"] = (
                            f"Failed to update network {name}: "
                            f"{update_result.get('error')}"
                        )
                        return ret

                ret["comment"] = f"Network {name} updated"
                ret["changes"] = changes
        else:
            ret["comment"] = f"Network {name} already in desired state"
    else:
        # Network doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network {name} would be created"
            ret["changes"] = {
                "network": {
                    "old": None,
                    "new": {
                        "name": name,
                        "type": network_type,
                        "config": config,
                        "description": description,
                    },
                }
            }
            return ret

        create_result = __salt__["incus.network_create"](
            name,
            network_type=network_type,
            config=config,
            description=description,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network {name} created"
            ret["changes"] = {
                "network": {
                    "old": None,
                    "new": name,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = _format_error_message(
                "create",
                f"network {name}",
                create_result,
                extra_info={
                    "type": network_type,
                    "description": description or "(empty)",
                    "config": config or {}
                }
            )

    return ret


def network_absent(name):
    """
    Ensure a network does not exist.

    :param name: Network name

    Example:

    .. code-block:: yaml

        old_network:
          incus.network_absent
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    network_info = __salt__["incus.network_get"](name)

    if not network_info.get("success"):
        ret["comment"] = f"Network {name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network {name} would be deleted"
        ret["changes"] = {
            "network": {
                "old": name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_delete"](name)

    if delete_result.get("success"):
        ret["comment"] = f"Network {name} deleted"
        ret["changes"] = {
            "network": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network {name}: "
            f"{delete_result.get('error')}"
        )

    return ret


# ======================================================================
# Network ACL States
# ======================================================================

def network_acl_present(name, config=None, description="", egress=None, ingress=None):
    """
    Ensure a network ACL exists and matches configuration.

    :param name: ACL name
    :param config: ACL configuration (dict)
    :param description: ACL description
    :param egress: List of egress rules
    :param ingress: List of ingress rules

    Example:

    .. code-block:: yaml

        myacl:
          incus.network_acl_present:
            - ingress:
                - action: allow
                  source: 10.0.0.0/24
                  destination: ""
                  protocol: tcp
                  destination_port: "22"
                - action: drop
                  source: ""
            - egress:
                - action: allow
            - description: SSH access from internal network
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    acl_info = __salt__["incus.network_acl_get"](name)

    if acl_info.get("success"):
        # ACL exists, check for updates
        current_acl = acl_info.get("acl", {}) or {}
        changes = {}

        # Check config
        if config:
            current_config = current_acl.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description
        if description is not None:
            current_desc = current_acl.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        # Check egress rules
        if egress is not None:
            current_egress = current_acl.get("egress", [])
            if current_egress != egress:
                changes["egress"] = {
                    "old": current_egress,
                    "new": egress,
                }

        # Check ingress rules
        if ingress is not None:
            current_ingress = current_acl.get("ingress", [])
            if current_ingress != ingress:
                changes["ingress"] = {
                    "old": current_ingress,
                    "new": ingress,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network ACL {name} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.network_acl_update"](
                    name,
                    config=config,
                    description=description,
                    egress=egress,
                    ingress=ingress,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Network ACL {name} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update network ACL {name}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Network ACL {name} already in desired state"
    else:
        # ACL doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network ACL {name} would be created"
            ret["changes"] = {
                "acl": {
                    "old": None,
                    "new": name,
                }
            }
            return ret

        create_result = __salt__["incus.network_acl_create"](
            name,
            config=config,
            description=description,
            egress=egress,
            ingress=ingress,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network ACL {name} created"
            ret["changes"] = {
                "acl": {
                    "old": None,
                    "new": name,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create network ACL {name}: "
                f"{create_result.get('error')}"
            )

    return ret


def network_acl_absent(name):
    """
    Ensure a network ACL does not exist.

    :param name: ACL name

    Example:

    .. code-block:: yaml

        old_acl:
          incus.network_acl_absent
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    acl_info = __salt__["incus.network_acl_get"](name)

    if not acl_info.get("success"):
        ret["comment"] = f"Network ACL {name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network ACL {name} would be deleted"
        ret["changes"] = {
            "acl": {
                "old": name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_acl_delete"](name)

    if delete_result.get("success"):
        ret["comment"] = f"Network ACL {name} deleted"
        ret["changes"] = {
            "acl": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network ACL {name}: "
            f"{delete_result.get('error')}"
        )

    return ret


# ======================================================================
# Network Forward States
# ======================================================================

def network_forward_present(network, listen_address, config=None, description="", ports=None):
    """
    Ensure a network forward exists and matches configuration.

    :param network: Network name
    :param listen_address: Listen address
    :param config: Forward configuration (dict)
    :param description: Forward description
    :param ports: List of port forwards

    Example:

    .. code-block:: yaml

        mybr0_forward:
          incus.network_forward_present:
            - network: mybr0
            - listen_address: 10.0.0.1
            - ports:
                - listen_port: "80"
                  protocol: tcp
                  target_address: 10.0.0.2
                  target_port: "8080"
                - listen_port: "443"
                  protocol: tcp
                  target_address: 10.0.0.2
                  target_port: "8443"
            - description: Web traffic forward
    """
    ret = {
        "name": f"{network}_{listen_address}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    forward_info = __salt__["incus.network_forward_get"](network, listen_address)

    if forward_info.get("success"):
        # Forward exists, check for updates
        current_forward = forward_info.get("forward", {}) or {}
        changes = {}

        # Check config
        if config:
            current_config = current_forward.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description
        if description is not None:
            current_desc = current_forward.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        # Check ports
        if ports is not None:
            current_ports = current_forward.get("ports", [])
            if current_ports != ports:
                changes["ports"] = {
                    "old": current_ports,
                    "new": ports,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network forward {listen_address} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.network_forward_update"](
                    network,
                    listen_address,
                    config=config,
                    description=description,
                    ports=ports,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Network forward {listen_address} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update network forward {listen_address}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Network forward {listen_address} already in desired state"
    else:
        # Forward doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network forward {listen_address} would be created"
            ret["changes"] = {
                "forward": {
                    "old": None,
                    "new": listen_address,
                }
            }
            return ret

        create_result = __salt__["incus.network_forward_create"](
            network,
            listen_address,
            config=config,
            description=description,
            ports=ports,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network forward {listen_address} created"
            ret["changes"] = {
                "forward": {
                    "old": None,
                    "new": listen_address,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create network forward {listen_address}: "
                f"{create_result.get('error')}"
            )

    return ret


def network_forward_absent(network, listen_address):
    """
    Ensure a network forward does not exist.

    :param network: Network name
    :param listen_address: Listen address

    Example:

    .. code-block:: yaml

        mybr0_forward:
          incus.network_forward_absent:
            - network: mybr0
            - listen_address: 10.0.0.1
    """
    ret = {
        "name": f"{network}_{listen_address}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    forward_info = __salt__["incus.network_forward_get"](network, listen_address)

    if not forward_info.get("success"):
        ret["comment"] = f"Network forward {listen_address} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network forward {listen_address} would be deleted"
        ret["changes"] = {
            "forward": {
                "old": listen_address,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_forward_delete"](network, listen_address)

    if delete_result.get("success"):
        ret["comment"] = f"Network forward {listen_address} deleted"
        ret["changes"] = {
            "forward": {
                "old": listen_address,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network forward {listen_address}: "
            f"{delete_result.get('error')}"
        )

    return ret


# ======================================================================
# Network Peer States
# ======================================================================

def network_peer_present(network, peer_name, config=None, description="", target_network=None, target_project=None):
    """
    Ensure a network peer exists and matches configuration.

    :param network: Network name
    :param peer_name: Peer name
    :param config: Peer configuration (dict)
    :param description: Peer description
    :param target_network: Target network name
    :param target_project: Target project name

    Example:

    .. code-block:: yaml

        mybr0_peer:
          incus.network_peer_present:
            - network: mybr0
            - peer_name: peer1
            - target_network: othernet
            - target_project: otherproject
            - description: Peer to other network
    """
    ret = {
        "name": f"{network}_{peer_name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    peer_info = __salt__["incus.network_peer_get"](network, peer_name)

    if peer_info.get("success"):
        # Peer exists, check for updates
        current_peer = peer_info.get("peer", {}) or {}
        changes = {}

        # Check config
        if config:
            current_config = current_peer.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description
        if description is not None:
            current_desc = current_peer.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        # Check target_network
        if target_network is not None:
            current_target = current_peer.get("target_network", "")
            if current_target != target_network:
                changes["target_network"] = {
                    "old": current_target,
                    "new": target_network,
                }

        # Check target_project
        if target_project is not None:
            current_project = current_peer.get("target_project", "")
            if current_project != target_project:
                changes["target_project"] = {
                    "old": current_project,
                    "new": target_project,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network peer {peer_name} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.network_peer_update"](
                    network,
                    peer_name,
                    config=config,
                    description=description,
                    target_network=target_network,
                    target_project=target_project,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Network peer {peer_name} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update network peer {peer_name}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Network peer {peer_name} already in desired state"
    else:
        # Peer doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network peer {peer_name} would be created"
            ret["changes"] = {
                "peer": {
                    "old": None,
                    "new": peer_name,
                }
            }
            return ret

        create_result = __salt__["incus.network_peer_create"](
            network,
            peer_name,
            config=config,
            description=description,
            target_network=target_network,
            target_project=target_project,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network peer {peer_name} created"
            ret["changes"] = {
                "peer": {
                    "old": None,
                    "new": peer_name,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create network peer {peer_name}: "
                f"{create_result.get('error')}"
            )

    return ret


def network_peer_absent(network, peer_name):
    """
    Ensure a network peer does not exist.

    :param network: Network name
    :param peer_name: Peer name

    Example:

    .. code-block:: yaml

        mybr0_peer:
          incus.network_peer_absent:
            - network: mybr0
            - peer_name: peer1
    """
    ret = {
        "name": f"{network}_{peer_name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    peer_info = __salt__["incus.network_peer_get"](network, peer_name)

    if not peer_info.get("success"):
        ret["comment"] = f"Network peer {peer_name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network peer {peer_name} would be deleted"
        ret["changes"] = {
            "peer": {
                "old": peer_name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_peer_delete"](network, peer_name)

    if delete_result.get("success"):
        ret["comment"] = f"Network peer {peer_name} deleted"
        ret["changes"] = {
            "peer": {
                "old": peer_name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network peer {peer_name}: "
            f"{delete_result.get('error')}"
        )

    return ret


# ======================================================================
# Network Zone States
# ======================================================================

def network_zone_present(zone, config=None, description=""):
    """
    Ensure a network zone exists and matches configuration.

    :param zone: Zone name (e.g., example.com)
    :param config: Zone configuration (dict)
    :param description: Zone description

    Example:

    .. code-block:: yaml

        example.com:
          incus.network_zone_present:
            - config:
                dns.nameservers: ns1.example.com
            - description: Main DNS zone
    """
    ret = {
        "name": zone,
        "result": True,
        "changes": {},
        "comment": "",
    }

    zone_info = __salt__["incus.network_zone_get"](zone)

    if zone_info.get("success"):
        # Zone exists, check for updates
        current_zone = zone_info.get("zone", {}) or {}
        changes = {}

        # Check config
        if config:
            current_config = current_zone.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description
        if description is not None:
            current_desc = current_zone.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network zone {zone} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.network_zone_update"](
                    zone,
                    config=config,
                    description=description,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Network zone {zone} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update network zone {zone}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Network zone {zone} already in desired state"
    else:
        # Zone doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network zone {zone} would be created"
            ret["changes"] = {
                "zone": {
                    "old": None,
                    "new": zone,
                }
            }
            return ret

        create_result = __salt__["incus.network_zone_create"](
            zone,
            config=config,
            description=description,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network zone {zone} created"
            ret["changes"] = {
                "zone": {
                    "old": None,
                    "new": zone,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create network zone {zone}: "
                f"{create_result.get('error')}"
            )

    return ret


def network_zone_absent(zone):
    """
    Ensure a network zone does not exist.

    :param zone: Zone name

    Example:

    .. code-block:: yaml

        old-zone.com:
          incus.network_zone_absent
    """
    ret = {
        "name": zone,
        "result": True,
        "changes": {},
        "comment": "",
    }

    zone_info = __salt__["incus.network_zone_get"](zone)

    if not zone_info.get("success"):
        ret["comment"] = f"Network zone {zone} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network zone {zone} would be deleted"
        ret["changes"] = {
            "zone": {
                "old": zone,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_zone_delete"](zone)

    if delete_result.get("success"):
        ret["comment"] = f"Network zone {zone} deleted"
        ret["changes"] = {
            "zone": {
                "old": zone,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network zone {zone}: "
            f"{delete_result.get('error')}"
        )

    return ret


def network_zone_record_present(zone, record_name, config=None, description="", entries=None):
    """
    Ensure a network zone record exists and matches configuration.

    :param zone: Zone name
    :param record_name: Record name
    :param config: Record configuration (dict)
    :param description: Record description
    :param entries: List of DNS entries

    Example:

    .. code-block:: yaml

        www_record:
          incus.network_zone_record_present:
            - zone: example.com
            - record_name: www
            - entries:
                - type: A
                  value: 192.168.1.1
                - type: AAAA
                  value: "2001:db8::1"
            - description: Web server record
    """
    ret = {
        "name": f"{zone}_{record_name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    record_info = __salt__["incus.network_zone_record_get"](zone, record_name)

    if record_info.get("success"):
        # Record exists, check for updates
        current_record = record_info.get("record", {}) or {}
        changes = {}

        # Check config
        if config:
            current_config = current_record.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check description
        if description is not None:
            current_desc = current_record.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        # Check entries
        if entries is not None:
            current_entries = current_record.get("entries", [])
            if current_entries != entries:
                changes["entries"] = {
                    "old": current_entries,
                    "new": entries,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Network zone record {record_name} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.network_zone_record_update"](
                    zone,
                    record_name,
                    config=config,
                    description=description,
                    entries=entries,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Network zone record {record_name} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update network zone record {record_name}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Network zone record {record_name} already in desired state"
    else:
        # Record doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Network zone record {record_name} would be created"
            ret["changes"] = {
                "record": {
                    "old": None,
                    "new": record_name,
                }
            }
            return ret

        create_result = __salt__["incus.network_zone_record_create"](
            zone,
            record_name,
            config=config,
            description=description,
            entries=entries,
        )

        if create_result.get("success"):
            ret["comment"] = f"Network zone record {record_name} created"
            ret["changes"] = {
                "record": {
                    "old": None,
                    "new": record_name,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create network zone record {record_name}: "
                f"{create_result.get('error')}"
            )

    return ret


def network_zone_record_absent(zone, record_name):
    """
    Ensure a network zone record does not exist.

    :param zone: Zone name
    :param record_name: Record name

    Example:

    .. code-block:: yaml

        old_record:
          incus.network_zone_record_absent:
            - zone: example.com
            - record_name: old
    """
    ret = {
        "name": f"{zone}_{record_name}",
        "result": True,
        "changes": {},
        "comment": "",
    }

    record_info = __salt__["incus.network_zone_record_get"](zone, record_name)

    if not record_info.get("success"):
        ret["comment"] = f"Network zone record {record_name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Network zone record {record_name} would be deleted"
        ret["changes"] = {
            "record": {
                "old": record_name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.network_zone_record_delete"](zone, record_name)

    if delete_result.get("success"):
        ret["comment"] = f"Network zone record {record_name} deleted"
        ret["changes"] = {
            "record": {
                "old": record_name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete network zone record {record_name}: "
            f"{delete_result.get('error')}"
        )

    return ret


# ======================================================================
# Profile States
# ======================================================================

def profile_present(name, config=None, devices=None, description=""):
    """
    Ensure a profile exists and matches all specified parameters.

    Profiles are used to store configuration that can be applied to instances
    at creation time. They can contain both configuration options and devices.

    :param name: Profile name
    :param config: Profile configuration (dict) - CPU limits, memory limits, etc.
    :param devices: Device configuration (dict) - NICs, disks, etc.
    :param description: Profile description

    Supports all profile configuration parameters including:
    - limits.cpu, limits.memory, limits.processes
    - security.nesting, security.privileged, security.idmap
    - boot.autostart, boot.host_shutdown_timeout
    - linux.kernel_modules
    - And many other profile-specific parameters

    The state will:
    1. Create the profile if it doesn't exist
    2. Update existing profiles to match the specified configuration
    3. Track all changes in config, devices, and description

    Example:

    .. code-block:: yaml

        webserver:
          incus.profile_present:
            - config:
                limits.cpu: "4"
                limits.memory: 4GB
                security.nesting: "true"
            - devices:
                eth0:
                  name: eth0
                  type: nic
                  nictype: bridged
                  parent: lxdbr0
                root:
                  path: /
                  pool: default
                  type: disk
            - description: Web server profile with resource limits

        database:
          incus.profile_present:
            - config:
                limits.cpu: "8"
                limits.memory: 16GB
                boot.autostart: "true"
            - devices:
                eth0:
                  name: eth0
                  type: nic
                  network: mybr0
                data:
                  path: /var/lib/mysql
                  pool: default
                  source: mysql-data
                  type: disk
            - description: Database server profile

        minimal:
          incus.profile_present:
            - config:
                limits.cpu: "1"
                limits.memory: 512MB
            - description: Minimal resources profile
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    profile_info = __salt__["incus.profile_get"](name)

    if profile_info.get("success"):
        # Profile exists, check for updates
        current_profile = profile_info.get("profile", {}) or {}
        changes = {}

        # Check config changes
        if config:
            current_config = current_profile.get("config", {}) or {}
            config_changes = {}
            for key, value in config.items():
                new_val = str(value)
                if current_config.get(key) != new_val:
                    config_changes[key] = {
                        "old": current_config.get(key),
                        "new": new_val,
                    }
            if config_changes:
                changes["config"] = config_changes

        # Check device changes
        if devices:
            current_devices = current_profile.get("devices", {}) or {}
            device_changes = {}
            for dev_name, dev_conf in devices.items():
                if current_devices.get(dev_name) != dev_conf:
                    device_changes[dev_name] = {
                        "old": current_devices.get(dev_name),
                        "new": dev_conf,
                    }
            if device_changes:
                changes["devices"] = device_changes

        # Check description changes
        if description is not None:
            current_desc = current_profile.get("description", "")
            if current_desc != description:
                changes["description"] = {
                    "old": current_desc,
                    "new": description,
                }

        if changes:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = f"Profile {name} would be updated"
                ret["changes"] = changes
            else:
                update_result = __salt__["incus.profile_update"](
                    name,
                    config=config,
                    devices=devices,
                    description=description,
                )
                if update_result.get("success"):
                    ret["comment"] = f"Profile {name} updated"
                    ret["changes"] = changes
                else:
                    ret["result"] = False
                    ret["comment"] = (
                        f"Failed to update profile {name}: "
                        f"{update_result.get('error')}"
                    )
        else:
            ret["comment"] = f"Profile {name} already in desired state"

    else:
        # Profile doesn't exist, create it
        if __opts__.get("test"):
            ret["result"] = None
            ret["comment"] = f"Profile {name} would be created"
            ret["changes"] = {
                "profile": {
                    "old": None,
                    "new": {
                        "name": name,
                        "config": config,
                        "devices": devices,
                        "description": description,
                    },
                }
            }
            return ret

        create_result = __salt__["incus.profile_create"](
            name,
            config=config,
            devices=devices,
            description=description,
        )

        if create_result.get("success"):
            ret["comment"] = f"Profile {name} created"
            ret["changes"] = {
                "profile": {
                    "old": None,
                    "new": name,
                }
            }
        else:
            ret["result"] = False
            ret["comment"] = (
                f"Failed to create profile {name}: "
                f"{create_result.get('error')}"
            )

    return ret


def profile_absent(name):
    """
    Ensure a profile does not exist.

    The profile must not be in use by any instances before deletion.
    If the profile is in use, the state will fail.

    :param name: Profile name

    Example:

    .. code-block:: yaml

        old_profile:
          incus.profile_absent

        temporary_profile:
          incus.profile_absent
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    profile_info = __salt__["incus.profile_get"](name)

    if not profile_info.get("success"):
        ret["comment"] = f"Profile {name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Profile {name} would be deleted"
        ret["changes"] = {
            "profile": {
                "old": name,
                "new": None,
            }
        }
        return ret

    delete_result = __salt__["incus.profile_delete"](name)

    if delete_result.get("success"):
        ret["comment"] = f"Profile {name} deleted"
        ret["changes"] = {
            "profile": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to delete profile {name}: "
            f"{delete_result.get('error')}"
        )

    return ret


def profile_config(name, config, description=None):
    """
    Ensure a profile has specific configuration.

    This state function allows you to manage only the configuration
    of an existing profile without affecting its devices.

    :param name: Profile name
    :param config: Configuration dict to apply (merged with existing)
    :param description: Profile description to update (optional)

    Example:

    .. code-block:: yaml

        webserver:
          incus.profile_config:
            - config:
                limits.cpu: "4"
                limits.memory: 4GB
            - description: Updated web server profile

        database:
          incus.profile_config:
            - config:
                limits.memory: 16GB
                boot.autostart: "true"
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current profile info
    profile_info = __salt__["incus.profile_get"](name)
    if not profile_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get profile {name}: {profile_info.get('error')}"
        return ret

    current_profile = profile_info.get("profile", {})
    current_config = current_profile.get("config", {})
    current_description = current_profile.get("description", "")

    # Check what needs to be updated
    config_changes = {}
    for key, value in (config or {}).items():
        new_val = str(value)
        if current_config.get(key) != new_val:
            config_changes[key] = {"old": current_config.get(key), "new": new_val}

    description_changed = description is not None and current_description != description

    if not config_changes and not description_changed:
        ret["comment"] = f"Profile {name} already has desired configuration"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Profile {name} configuration would be updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
        return ret

    # Apply updates
    update_result = __salt__["incus.profile_update"](
        name, config=config, description=description
    )

    if update_result.get("success"):
        ret["comment"] = f"Profile {name} configuration updated"
        if config_changes:
            ret["changes"]["config"] = config_changes
        if description_changed:
            ret["changes"]["description"] = {"old": current_description, "new": description}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update profile {name}: {update_result.get('error')}"

    return ret


# ======================================================================
# Cluster States
# ======================================================================

def cluster_member_present(name, address, cluster_password=None):
    """
    Ensure a cluster member exists.

    :param name: Member name
    :param address: Member address
    :param cluster_password: Cluster password

    Example:

    .. code-block:: yaml

        node2:
          incus.cluster_member_present:
            - address: 192.168.1.101
            - cluster_password: secret123
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    members = __salt__["incus.cluster_member_list"](recursion=1)
    if not members.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list cluster members: {members.get('error')}"
        return ret

    member_list = members.get("members", []) or []
    member_exists = any(m.get("server_name") == name for m in member_list)

    if member_exists:
        ret["comment"] = f"Cluster member {name} already exists"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Cluster member {name} would be added"
        ret["changes"] = {
            "member": {
                "old": None,
                "new": name,
            }
        }
        return ret

    add_result = __salt__["incus.cluster_member_add"](
        name,
        address,
        cluster_password=cluster_password,
    )

    if add_result.get("success"):
        ret["comment"] = f"Cluster member {name} added"
        ret["changes"] = {
            "member": {
                "old": None,
                "new": name,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to add cluster member {name}: "
            f"{add_result.get('error')}"
        )

    return ret


def cluster_member_absent(name, force=False):
    """
    Ensure a cluster member does not exist.

    :param name: Member name
    :param force: Force removal

    Example:

    .. code-block:: yaml

        old_node:
          incus.cluster_member_absent:
            - force: True
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    members = __salt__["incus.cluster_member_list"](recursion=1)
    if not members.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to list cluster members: {members.get('error')}"
        return ret

    member_list = members.get("members", []) or []
    member_exists = any(m.get("server_name") == name for m in member_list)

    if not member_exists:
        ret["comment"] = f"Cluster member {name} already absent"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Cluster member {name} would be removed"
        ret["changes"] = {
            "member": {
                "old": name,
                "new": None,
            }
        }
        return ret

    remove_result = __salt__["incus.cluster_member_remove"](name, force=force)

    if remove_result.get("success"):
        ret["comment"] = f"Cluster member {name} removed"
        ret["changes"] = {
            "member": {
                "old": name,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = (
            f"Failed to remove cluster member {name}: "
            f"{remove_result.get('error')}"
        )

    return ret


# ======================================================================
# Server Settings States
# ======================================================================

def settings_present(name, config):
    """
    Ensure Incus server has specific global configuration settings.

    This state merges the provided configuration with existing settings,
    updating only the specified keys while preserving others.

    :param name: State name (descriptive identifier)
    :param config: Dictionary of configuration key-value pairs to apply

    Common configuration keys:
    - core.https_address: HTTPS address and port (e.g., '[::]:8443')
    - core.trust_password: Password for adding new clients
    - images.auto_update_cached: Enable/disable automatic image updates ('true'/'false')
    - images.auto_update_interval: Hours between image update checks
    - images.compression_algorithm: Compression for images (e.g., 'gzip', 'zstd')
    - cluster.https_address: Address for cluster communication
    - storage.backups_volume: Storage volume for backups
    - storage.images_volume: Storage volume for images

    Example:

    .. code-block:: yaml

        incus_basic_config:
          incus.settings_present:
            - config:
                images.auto_update_cached: "true"
                images.auto_update_interval: "12"

        incus_https_config:
          incus.settings_present:
            - config:
                core.https_address: "[::]:8443"
                core.trust_password: "mysecret"

        incus_image_compression:
          incus.settings_present:
            - config:
                images.compression_algorithm: "zstd"
                images.remote_cache_expiry: "10"

        incus_cluster_config:
          incus.settings_present:
            - config:
                cluster.https_address: "192.168.1.100:8443"
                cluster.offline_threshold: "120"
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current settings
    settings_info = __salt__["incus.settings_get"]()
    if not settings_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get server settings: {settings_info.get('error')}"
        return ret

    current_settings = settings_info.get("settings", {}) or {}
    current_config = current_settings.get("config", {}) or {}

    # Check what needs to be updated
    config_changes = {}
    for key, value in (config or {}).items():
        new_val = str(value)
        current_val = current_config.get(key)
        if current_val != new_val:
            config_changes[key] = {
                "old": current_val,
                "new": new_val,
            }

    if not config_changes:
        ret["comment"] = "Server settings already in desired state"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = "Server settings would be updated"
        ret["changes"] = {"config": config_changes}
        return ret

    # Apply updates
    update_result = __salt__["incus.settings_update"](config)

    if update_result.get("success"):
        ret["comment"] = "Server settings updated"
        ret["changes"] = {"config": config_changes}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update server settings: {update_result.get('error')}"

    return ret


def settings_config(name, key, value):
    """
    Ensure a single Incus server configuration setting has a specific value.

    This is a convenience state for managing individual configuration keys
    without needing to provide a full configuration dictionary.

    :param name: State name (descriptive identifier, typically the config key)
    :param key: Configuration key name
    :param value: Configuration value (will be converted to string)

    Example:

    .. code-block:: yaml

        https_address:
          incus.settings_config:
            - key: core.https_address
            - value: "[::]:8443"

        auto_update_interval:
          incus.settings_config:
            - key: images.auto_update_interval
            - value: "12"

        compression_algorithm:
          incus.settings_config:
            - key: images.compression_algorithm
            - value: "zstd"

        trust_password:
          incus.settings_config:
            - key: core.trust_password
            - value: "mysecret"
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current settings
    settings_info = __salt__["incus.settings_get"]()
    if not settings_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get server settings: {settings_info.get('error')}"
        return ret

    current_settings = settings_info.get("settings", {}) or {}
    current_config = current_settings.get("config", {}) or {}

    # Check current value
    new_val = str(value)
    current_val = current_config.get(key)

    if current_val == new_val:
        ret["comment"] = f"Setting {key} already has value {new_val}"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Setting {key} would be updated"
        ret["changes"] = {
            key: {
                "old": current_val,
                "new": new_val,
            }
        }
        return ret

    # Apply update
    update_result = __salt__["incus.settings_set"](key, value)

    if update_result.get("success"):
        ret["comment"] = f"Setting {key} updated to {new_val}"
        ret["changes"] = {
            key: {
                "old": current_val,
                "new": new_val,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update setting {key}: {update_result.get('error')}"

    return ret


def settings_absent(name, key):
    """
    Ensure a specific Incus server configuration setting is not present.

    This state removes a configuration key, reverting it to its default value.

    :param name: State name (descriptive identifier, typically the config key)
    :param key: Configuration key name to remove

    Example:

    .. code-block:: yaml

        remove_trust_password:
          incus.settings_absent:
            - key: core.trust_password

        reset_auto_update:
          incus.settings_absent:
            - key: images.auto_update_interval

        remove_https_address:
          incus.settings_absent:
            - key: core.https_address
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current settings
    settings_info = __salt__["incus.settings_get"]()
    if not settings_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get server settings: {settings_info.get('error')}"
        return ret

    current_settings = settings_info.get("settings", {}) or {}
    current_config = current_settings.get("config", {}) or {}

    # Check if key exists
    if key not in current_config:
        ret["comment"] = f"Setting {key} already absent"
        return ret

    current_val = current_config.get(key)

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = f"Setting {key} would be removed"
        ret["changes"] = {
            key: {
                "old": current_val,
                "new": None,
            }
        }
        return ret

    # Remove setting
    unset_result = __salt__["incus.settings_unset"](key)

    if unset_result.get("success"):
        ret["comment"] = f"Setting {key} removed"
        ret["changes"] = {
            key: {
                "old": current_val,
                "new": None,
            }
        }
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to remove setting {key}: {unset_result.get('error')}"

    return ret


def settings_managed(name, config):
    """
    Ensure Incus server configuration exactly matches the specified settings.

    Unlike settings_present which merges with existing settings, this state
    REPLACES the entire configuration. Any settings not specified will be
    removed and reverted to defaults.

    WARNING: This is a destructive operation. Use with caution!

    :param name: State name (descriptive identifier)
    :param config: Dictionary of ALL desired configuration key-value pairs

    Example:

    .. code-block:: yaml

        incus_exact_config:
          incus.settings_managed:
            - config:
                core.https_address: "[::]:8443"
                images.auto_update_cached: "true"
                images.auto_update_interval: "12"
                images.compression_algorithm: "zstd"

    Note:
        This state will remove ALL settings not specified in the config
        parameter. For incremental updates, use settings_present instead.
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    # Get current settings
    settings_info = __salt__["incus.settings_get"]()
    if not settings_info.get("success"):
        ret["result"] = False
        ret["comment"] = f"Failed to get server settings: {settings_info.get('error')}"
        return ret

    current_settings = settings_info.get("settings", {}) or {}
    current_config = current_settings.get("config", {}) or {}

    # Compare entire configuration
    desired_config = {str(k): str(v) for k, v in (config or {}).items()}

    # Find all changes
    all_changes = {}

    # Keys that need to be added or updated
    for key, value in desired_config.items():
        current_val = current_config.get(key)
        if current_val != value:
            all_changes[key] = {
                "old": current_val,
                "new": value,
            }

    # Keys that need to be removed
    for key, current_val in current_config.items():
        if key not in desired_config:
            all_changes[key] = {
                "old": current_val,
                "new": None,
            }

    if not all_changes:
        ret["comment"] = "Server settings already match desired state exactly"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = "Server settings would be replaced"
        ret["changes"] = {"config": all_changes}
        return ret

    # Replace configuration
    replace_result = __salt__["incus.settings_replace"](desired_config)

    if replace_result.get("success"):
        ret["comment"] = "Server settings replaced"
        ret["changes"] = {"config": all_changes}
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to replace server settings: {replace_result.get('error')}"

    return ret
