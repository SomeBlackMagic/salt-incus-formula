# Incus Storage Management Documentation

This document describes the Salt execution module and state functions for managing Incus storage pools, volumes, snapshots, and attachments.

## Table of Contents

- [Execution Module Functions](#execution-module-functions)
  - [Storage Pools](#storage-pools)
  - [Storage Volumes](#storage-volumes)
  - [Volume Snapshots](#volume-snapshots)
- [State Functions](#state-functions)
  - [Storage Pool States](#storage-pool-states)
  - [Storage Volume States](#storage-volume-states)
  - [Volume Snapshot States](#volume-snapshot-states)
  - [Volume Attachment States](#volume-attachment-states)
- [Pillar Configuration](#pillar-configuration)
- [Usage Examples](#usage-examples)

---

## Execution Module Functions

### Storage Pools

#### `storage_pool_list(recursion=0)`

List all storage pools.

**Parameters:**
- `recursion` (int): Recursion level (0=URLs, 1=basic info, 2=full info)

**Returns:** Dict with `success` and `pools` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_list
salt '*' incus.storage_pool_list recursion=1
```

---

#### `storage_pool_get(name)`

Get storage pool information.

**Parameters:**
- `name` (str): Pool name

**Returns:** Dict with `success` and `pool` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_get mypool
```

---

#### `storage_pool_create(name, driver, config=None, description='')`

Create a storage pool.

**Parameters:**
- `name` (str): Pool name
- `driver` (str): Storage driver (dir, zfs, btrfs, lvm, ceph)
- `config` (dict): Pool configuration
- `description` (str): Pool description

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_create mypool dir config="{'source':'/var/lib/incus/storage-pools/mypool'}"
```

**Supported drivers and common config options:**

| Driver    | Config Options                                                                                                          |
|-----------|-------------------------------------------------------------------------------------------------------------------------|
| **dir**   | `source`: Directory path                                                                                                |
| **zfs**   | `source`: ZFS pool/dataset<br>`volume.zfs.use_refquota`: Use refquota<br>`volume.size`: Default volume size             |
| **btrfs** | `source`: Btrfs filesystem path<br>`volume.size`: Default volume size                                                   |
| **lvm**   | `source`: Block device or existing VG<br>`lvm.vg_name`: Volume group name<br>`volume.block.filesystem`: Filesystem type |
| **ceph**  | `source`: Ceph pool name<br>`ceph.cluster_name`: Cluster name<br>`ceph.user.name`: Ceph user                            |

---

#### `storage_pool_update(name, config=None, description=None)`

Update storage pool configuration.

**Parameters:**
- `name` (str): Pool name
- `config` (dict): Configuration to update
- `description` (str): Pool description to update

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_update mypool config="{'rsync.bwlimit':'100'}"
```

---

#### `storage_pool_rename(name, new_name)`

Rename a storage pool.

**Parameters:**
- `name` (str): Current pool name
- `new_name` (str): New pool name

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_rename mypool mynewpool
```

---

#### `storage_pool_resources(name)`

Get storage pool resource usage information.

**Parameters:**
- `name` (str): Pool name

**Returns:** Dict with `success` and `resources` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_resources mypool
```

---

#### `storage_pool_delete(name)`

Delete a storage pool.

**Parameters:**
- `name` (str): Pool name

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.storage_pool_delete mypool
```

---

### Storage Volumes

#### `volume_list(pool, recursion=0)`

List volumes in a storage pool.

**Parameters:**
- `pool` (str): Pool name
- `recursion` (int): Recursion level

**Returns:** Dict with `success` and `volumes` keys

**CLI Example:**
```bash
salt '*' incus.volume_list default
salt '*' incus.volume_list default recursion=1
```

---

#### `volume_get(pool, name, volume_type='custom')`

Get storage volume information.

**Parameters:**
- `pool` (str): Pool name
- `name` (str): Volume name
- `volume_type` (str): Volume type (custom, image, container, virtual-machine)

**Returns:** Dict with `success` and `volume` keys

**CLI Example:**
```bash
salt '*' incus.volume_get default myvolume
```

---

#### `volume_create(pool, name, volume_type='custom', config=None, description='')`

Create a storage volume.

**Parameters:**
- `pool` (str): Pool name
- `name` (str): Volume name
- `volume_type` (str): Volume type (custom, image, container, virtual-machine)
- `config` (dict): Volume configuration
- `description` (str): Volume description

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_create default myvolume
salt '*' incus.volume_create default myvolume config="{'size':'10GiB'}"
```

**Common volume config options:**

| Option                | Description                                        |
|-----------------------|----------------------------------------------------|
| `size`                | Volume size (e.g., "10GiB", "1TiB")                |
| `snapshots.expiry`    | Snapshot expiry time (e.g., "7d", "1m")            |
| `snapshots.schedule`  | Snapshot schedule (cron format or @daily, @hourly) |
| `snapshots.pattern`   | Snapshot name pattern                              |
| `block.filesystem`    | Filesystem for block volumes (ext4, xfs, btrfs)    |
| `block.mount_options` | Mount options for block volumes                    |
| `security.shifted`    | Enable idmap shifting for the volume               |
| `security.unmapped`   | Disable idmap for the volume                       |

**ZFS-specific options:**
- `zfs.blocksize`: ZFS block size
- `zfs.compression`: Compression algorithm (lz4, gzip, zstd)
- `zfs.delegate`: Delegate ZFS permissions

---

#### `volume_update(pool, name, volume_type='custom', config=None, description=None)`

Update storage volume configuration.

**Parameters:**
- `pool` (str): Pool name
- `name` (str): Volume name
- `volume_type` (str): Volume type
- `config` (dict): Configuration to update
- `description` (str): Volume description to update

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_update default myvolume config="{'size':'20GiB'}"
```

---

#### `volume_rename(pool, name, new_name, volume_type='custom')`

Rename a storage volume.

**Parameters:**
- `pool` (str): Pool name
- `name` (str): Current volume name
- `new_name` (str): New volume name
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_rename default myvolume mynewvolume
```

---

#### `volume_copy(source_pool, source_volume, target_pool=None, target_volume=None, volume_type='custom', config=None)`

Copy a storage volume.

**Parameters:**
- `source_pool` (str): Source pool name
- `source_volume` (str): Source volume name
- `target_pool` (str): Target pool name (defaults to source_pool)
- `target_volume` (str): Target volume name (defaults to source_volume)
- `volume_type` (str): Volume type
- `config` (dict): Volume configuration for the copy

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_copy default vol1 target_pool=default target_volume=vol2
```

---

#### `volume_create_from_snapshot(pool, volume, snapshot_name, new_volume_name, volume_type='custom', config=None)`

Create a new volume from a snapshot.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Source volume name
- `snapshot_name` (str): Snapshot name to create from
- `new_volume_name` (str): Name for the new volume
- `volume_type` (str): Volume type
- `config` (dict): Volume configuration for the new volume

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_create_from_snapshot default myvolume snap1 restored_volume
```

---

#### `volume_move(source_pool, source_volume, target_pool, target_volume=None, volume_type='custom')`

Move a storage volume to another pool.

**Parameters:**
- `source_pool` (str): Source pool name
- `source_volume` (str): Source volume name
- `target_pool` (str): Target pool name
- `target_volume` (str): Target volume name (defaults to source_volume)
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_move pool1 vol1 pool2
salt '*' incus.volume_move pool1 vol1 pool2 target_volume=vol2
```

---

#### `volume_delete(pool, name, volume_type='custom')`

Delete a storage volume.

**Parameters:**
- `pool` (str): Pool name
- `name` (str): Volume name
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_delete default myvolume
```

---

### Volume Snapshots

#### `volume_snapshot_list(pool, volume, volume_type='custom', recursion=0)`

List snapshots of a storage volume.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `volume_type` (str): Volume type
- `recursion` (int): Recursion level

**Returns:** Dict with `success` and `snapshots` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_list default myvolume
salt '*' incus.volume_snapshot_list default myvolume recursion=1
```

---

#### `volume_snapshot_get(pool, volume, snapshot_name, volume_type='custom')`

Get information about a volume snapshot.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `snapshot_name` (str): Snapshot name
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `snapshot` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_get default myvolume snap1
```

---

#### `volume_snapshot_create(pool, volume, snapshot_name, volume_type='custom', description='')`

Create a snapshot of a storage volume.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `snapshot_name` (str): Snapshot name
- `volume_type` (str): Volume type
- `description` (str): Snapshot description

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_create default myvolume snap1
salt '*' incus.volume_snapshot_create default myvolume backup1 description="Before upgrade"
```

---

#### `volume_snapshot_rename(pool, volume, snapshot_name, new_name, volume_type='custom')`

Rename a volume snapshot.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `snapshot_name` (str): Current snapshot name
- `new_name` (str): New snapshot name
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_rename default myvolume snap1 snap2
```

---

#### `volume_snapshot_restore(pool, volume, snapshot_name, volume_type='custom')`

Restore a volume to a previous snapshot state.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `snapshot_name` (str): Snapshot name to restore from
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_restore default myvolume snap1
```

**Note:** This will revert the volume to the state it was in when the snapshot was created.

---

#### `volume_snapshot_delete(pool, volume, snapshot_name, volume_type='custom')`

Delete a volume snapshot.

**Parameters:**
- `pool` (str): Pool name
- `volume` (str): Volume name
- `snapshot_name` (str): Snapshot name
- `volume_type` (str): Volume type

**Returns:** Dict with `success` and `message` keys

**CLI Example:**
```bash
salt '*' incus.volume_snapshot_delete default myvolume snap1
```

---

## State Functions

### Storage Pool States

#### `storage_pool_present`

Ensure a storage pool exists.

**Parameters:**
- `name` (str): Pool name
- `driver` (str): Storage driver (dir, zfs, btrfs, lvm, ceph)
- `config` (dict): Pool configuration
- `description` (str): Pool description

**Example:**
```yaml
mypool:
  incus.storage_pool_present:
    - driver: dir
    - config:
        source: /var/lib/incus/storage-pools/mypool
    - description: My storage pool
```

---

#### `storage_pool_absent`

Ensure a storage pool does not exist.

**Parameters:**
- `name` (str): Pool name

**Example:**
```yaml
old_pool:
  incus.storage_pool_absent
```

---

#### `storage_pool_config`

Ensure a storage pool has specific configuration.

**Parameters:**
- `name` (str): Pool name
- `config` (dict): Configuration dict to apply
- `description` (str): Pool description to update (optional)

**Example:**
```yaml
mypool:
  incus.storage_pool_config:
    - config:
        rsync.bwlimit: "100"
        volume.size: 10GiB
```

---

### Storage Volume States

#### `volume_present`

Ensure a storage volume exists.

**Parameters:**
- `name` (str): Volume name
- `pool` (str): Pool name
- `volume_type` (str): Volume type (custom, image, container, virtual-machine)
- `config` (dict): Volume configuration
- `description` (str): Volume description

**Example:**
```yaml
myvolume:
  incus.volume_present:
    - pool: default
    - config:
        size: 10GB
    - description: Data volume
```

---

#### `volume_absent`

Ensure a storage volume does not exist.

**Parameters:**
- `name` (str): Volume name
- `pool` (str): Pool name
- `volume_type` (str): Volume type

**Example:**
```yaml
old_volume:
  incus.volume_absent:
    - pool: default
```

---

#### `volume_config`

Ensure a storage volume has a specific configuration.

**Parameters:**
- `name` (str): Volume name
- `pool` (str): Pool name
- `volume_type` (str): Volume type
- `config` (dict): Configuration dict to apply
- `description` (str): Volume description to update (optional)

**Example:**
```yaml
myvolume:
  incus.volume_config:
    - pool: default
    - config:
        size: 20GiB
        snapshots.schedule: "@daily"
```

---

### Volume Snapshot States

#### `volume_snapshot_present`

Ensure a volume snapshot exists.

**Parameters:**
- `name` (str): Snapshot name
- `pool` (str): Pool name
- `volume` (str): Volume name
- `volume_type` (str): Volume type
- `description` (str): Snapshot description

**Example:**
```yaml
snap1:
  incus.volume_snapshot_present:
    - pool: default
    - volume: myvolume
    - description: Backup before update
```

---

#### `volume_snapshot_absent`

Ensure a volume snapshot does not exist.

**Parameters:**
- `name` (str): Snapshot name
- `pool` (str): Pool name
- `volume` (str): Volume name
- `volume_type` (str): Volume type

**Example:**
```yaml
old_snap:
  incus.volume_snapshot_absent:
    - pool: default
    - volume: myvolume
```

---

### Volume Attachment States

#### `volume_attached`

Ensure a volume is attached to an instance.

**Parameters:**
- `name` (str): Volume name
- `pool` (str): Pool name
- `instance` (str): Instance name
- `device_name` (str): Device name (defaults to volume name)
- `path` (str): Mount path inside instance
- `volume_type` (str): Volume type

**Example:**
```yaml
myvolume:
  incus.volume_attached:
    - pool: default
    - instance: mycontainer
    - path: /mnt/data
    - device_name: data-disk
```

---

#### `volume_detached`

Ensure a volume is detached from an instance.

**Parameters:**
- `name` (str): Volume name
- `pool` (str): Pool name
- `instance` (str): Instance name
- `device_name` (str): Device name (defaults to volume name)

**Example:**
```yaml
myvolume:
  incus.volume_detached:
    - pool: default
    - instance: mycontainer
```

---

## Pillar Configuration

Storage resources are configured through the `incus` pillar. See `pillars.example/storage.sls` for a complete example.

### Basic Structure

```yaml
incus:
  storage_pools:
    <pool_name>:
      ensure: present|absent
      driver: dir|zfs|btrfs|lvm|ceph
      config: {}
      description: ""

  storage_volumes:
    <volume_id>:
      name: <volume_name>
      pool: <pool_name>
      ensure: present|absent
      volume_type: custom
      config: {}
      description: ""

  volume_snapshots:
    <snapshot_id>:
      name: <snapshot_name>
      pool: <pool_name>
      volume: <volume_name>
      ensure: present|absent
      description: ""

  volume_attachments:
    <attachment_id>:
      volume: <volume_name>
      pool: <pool_name>
      instance: <instance_name>
      ensure: attached|detached
      path: <mount_path>
      device_name: <device_name>
```

---

## Usage Examples

### Example 1: Create ZFS Pool with Volume

```yaml
incus:
  storage_pools:
    production:
      driver: zfs
      config:
        source: tank/production
        volume.zfs.use_refquota: "true"
        volume.size: 10GiB
      description: Production ZFS pool

  storage_volumes:
    webapp-data:
      pool: production
      config:
        size: 50GiB
        snapshots.schedule: "@daily"
        snapshots.expiry: 7d
      description: Web application data
```

### Example 2: Attach Volume to Container

```yaml
incus:
  storage_volumes:
    database-volume:
      pool: default
      config:
        size: 100GiB
      description: Database storage

  volume_attachments:
    db-mount:
      volume: database-volume
      pool: default
      instance: postgres-container
      path: /var/lib/postgresql/data
      device_name: pgdata
```

### Example 3: Volume with Snapshots

```yaml
incus:
  storage_volumes:
    important-data:
      pool: default
      config:
        size: 20GiB
        snapshots.schedule: "0 2 * * *"  # Daily at 2 AM
        snapshots.expiry: 30d

  volume_snapshots:
    manual-backup:
      name: before-migration
      pool: default
      volume: important-data
      description: Manual backup before data migration
```

### Example 4: Shared Volume Across Multiple Instances (Ceph)

```yaml
incus:
  storage_pools:
    ceph-shared:
      driver: ceph
      config:
        source: shared-pool
        ceph.cluster_name: ceph
        ceph.user.name: admin

  storage_volumes:
    shared-storage:
      pool: ceph-shared
      config:
        size: 100GiB

  volume_attachments:
    shared-to-web1:
      volume: shared-storage
      pool: ceph-shared
      instance: web-1
      path: /shared

    shared-to-web2:
      volume: shared-storage
      pool: ceph-shared
      instance: web-2
      path: /shared
```

### Example 5: Directory Storage with LVM Backup Pool

```yaml
incus:
  storage_pools:
    local:
      driver: dir
      config:
        source: /var/lib/incus/storage-pools/local

    backups:
      driver: lvm
      config:
        source: /dev/sdb
        lvm.vg_name: backup-vg
        volume.block.filesystem: ext4

  storage_volumes:
    live-data:
      pool: local
      config:
        size: 50GiB

    backup-data:
      pool: backups
      config:
        size: 200GiB
```

---

## Best Practices

### Storage Pool Selection

- **dir**: Best for testing, development, simple setups
- **zfs**: Best for production, snapshots, compression
- **btrfs**: Good alternative to ZFS, built-in compression
- **lvm**: Good for block storage, thin provisioning
- **ceph**: Best for distributed, shared storage

### Volume Configuration

- Always set `size` explicitly for predictable storage allocation
- Use `snapshots.schedule` for automatic backups
- Set `snapshots.expiry` to prevent unlimited snapshot growth
- Consider using compression for ZFS/Btrfs pools

### Snapshot Management

- Use automatic snapshots via `snapshots.schedule` config
- Create manual snapshots before major changes
- Set appropriate `snapshots.expiry` times
- Use descriptive snapshot names and descriptions

### Performance Optimization

- For ZFS: tune `zfs.blocksize` based on workload
- Enable compression for better space utilization
- Use `volume.zfs.use_refquota` for accurate quota reporting
- Consider separate pools for different performance requirements

### Security

- Use `security.shifted` for container ID mapping
- Set appropriate filesystem permissions
- Consider encryption at the pool or disk level
- Restrict pool access via Incus RBAC if needed

---

## Troubleshooting

### Volume Won't Delete
```bash
# Check if volume is attached to instances
salt '*' incus.volume_list <pool> recursion=2

# Detach volume first
salt '*' incus.instance_get <instance>
```

### Pool Creation Fails
```bash
# Check if pool already exists
salt '*' incus.storage_pool_list recursion=1

# Verify storage driver availability
salt '*' cmd.run 'incus admin init --dump'

# Check disk/device availability for LVM/Ceph
salt '*' cmd.run 'lsblk'
```

### Snapshot Restore Issues
```bash
# Verify snapshot exists
salt '*' incus.volume_snapshot_list <pool> <volume>

# Check volume is not in use
salt '*' incus.volume_get <pool> <volume>
```

---

## See Also

- [Incus Storage Documentation](https://linuxcontainers.org/incus/docs/main/reference/storage/)
- [Salt States Reference](https://docs.saltproject.io/en/latest/ref/states/all/)
- Main Salt formula: `states/incus/storage.sls`
- Pillar examples: `pillars.example/storage.sls`
