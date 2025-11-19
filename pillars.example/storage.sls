incus:
  # ======================================================================
  # Storage Pools Configuration
  # ======================================================================
  storage_pools:
    # Directory-based storage pool
    local:
      ensure: present  # present or absent
      driver: dir
      config:
        source: /var/lib/incus/storage-pools/local
      description: Local directory storage pool

    # ZFS storage pool
    zfs-pool:
      ensure: present
      driver: zfs
      config:
        source: tank/incus
        volume.zfs.remove_snapshots: "true"
        volume.zfs.use_refquota: "true"
      description: ZFS storage pool
      # Optional: update config after creation
      update_config:
        volume.size: 10GiB
      update_description: Updated ZFS pool

    # LVM storage pool
    lvm-pool:
      ensure: present
      driver: lvm
      config:
        source: /dev/sdb
        lvm.vg_name: incus-vg
        volume.block.filesystem: ext4
        volume.block.mount_options: discard
      description: LVM storage pool

    # Btrfs storage pool
    btrfs-pool:
      ensure: present
      driver: btrfs
      config:
        source: /var/lib/incus/storage-pools/btrfs
      description: Btrfs storage pool

    # Ceph/RBD storage pool
    ceph-pool:
      ensure: present
      driver: ceph
      config:
        source: incus
        ceph.cluster_name: ceph
        ceph.osd.pg_num: "32"
        ceph.rbd.clone_copy: "true"
        ceph.user.name: admin
      description: Ceph RBD storage pool

    # Pool to be removed
    old-pool:
      ensure: absent

  # ======================================================================
  # Storage Volumes Configuration
  # ======================================================================
  storage_volumes:
    # Simple volume with default settings
    data-volume:
      name: data
      pool: local
      ensure: present  # present or absent
      config:
        size: 10GiB
      description: Data storage volume

    # Volume with custom type and config
    database-volume:
      name: postgres-data
      pool: zfs-pool
      ensure: present
      volume_type: custom  # custom, image, container, virtual-machine
      config:
        size: 50GiB
        snapshots.expiry: 7d
        snapshots.schedule: "@daily"
      description: PostgreSQL database storage
      # Optional: update config after creation
      update_config:
        size: 100GiB
      update_description: Expanded database storage

    # Block volume for VM
    vm-disk:
      name: vm-root
      pool: lvm-pool
      ensure: present
      volume_type: custom
      config:
        size: 20GiB
        block.filesystem: ext4
      description: VM root disk

    # Volume with ZFS-specific options
    backup-volume:
      name: backups
      pool: zfs-pool
      ensure: present
      config:
        size: 100GiB
        zfs.blocksize: 128K
        zfs.compression: lz4
      description: Backup storage with compression

    # Ceph volume
    ceph-volume:
      name: shared-data
      pool: ceph-pool
      ensure: present
      config:
        size: 200GiB
        ceph.rbd.features: layering,exclusive-lock
      description: Shared Ceph volume

    # Volume to be removed
    old-volume:
      name: temp
      pool: local
      ensure: absent

  # ======================================================================
  # Volume Snapshots Configuration
  # ======================================================================
  volume_snapshots:
    # Simple snapshot
    data-snap1:
      name: snap-before-update
      pool: local
      volume: data
      ensure: present  # present or absent
      description: Snapshot before system update

    # ZFS volume snapshot
    db-backup-snap:
      name: daily-backup
      pool: zfs-pool
      volume: postgres-data
      ensure: present
      volume_type: custom
      description: Daily database backup snapshot

    # Multiple snapshots for the same volume
    db-snap-1:
      name: pre-migration
      pool: zfs-pool
      volume: postgres-data
      ensure: present
      description: Before database migration

    db-snap-2:
      name: post-migration
      pool: zfs-pool
      volume: postgres-data
      ensure: present
      description: After database migration

    # Snapshot to be removed
    old-snapshot:
      name: obsolete-snap
      pool: local
      volume: data
      ensure: absent

  # ======================================================================
  # Volume Attachments Configuration
  # ======================================================================
  volume_attachments:
    # Attach data volume to container
    data-to-web:
      volume: data
      pool: local
      instance: web-container
      ensure: attached  # attached or detached
      path: /mnt/data
      device_name: data-disk

    # Attach database volume
    db-to-postgres:
      volume: postgres-data
      pool: zfs-pool
      instance: postgres-container
      ensure: attached
      path: /var/lib/postgresql/data
      device_name: pgdata

    # Attach backup volume (read-only possible via instance config)
    backup-to-backup-container:
      volume: backups
      pool: zfs-pool
      instance: backup-container
      ensure: attached
      path: /backups
      device_name: backup-storage

    # Attach shared Ceph volume to multiple instances
    shared-to-app1:
      volume: shared-data
      pool: ceph-pool
      instance: app-container-1
      ensure: attached
      path: /shared
      device_name: shared

    shared-to-app2:
      volume: shared-data
      pool: ceph-pool
      instance: app-container-2
      ensure: attached
      path: /shared
      device_name: shared

    # Detach volume from instance
    detach-old-volume:
      volume: temp
      pool: local
      instance: old-container
      ensure: detached
      device_name: temp-disk

  # ======================================================================
  # Complete Storage Configuration Example
  # ======================================================================

  # Example: Complete setup for a web application with database
  #
  # This creates:
  # - ZFS storage pool for performance
  # - Separate volumes for web data and database
  # - Daily snapshots for backup
  # - Attached volumes to respective containers
  #
  # Storage hierarchy:
  # zfs-pool (ZFS pool)
  # ├── webapp-data (10GiB) -> attached to webapp-container:/var/www
  # │   └── snap-daily (snapshot)
  # └── webapp-db (20GiB) -> attached to db-container:/var/lib/mysql
  #     └── snap-daily (snapshot)

  # Full example (commented out):
  # storage_pools:
  #   production:
  #     driver: zfs
  #     config:
  #       source: tank/production
  #       volume.zfs.use_refquota: "true"
  #     description: Production ZFS pool
  #
  # storage_volumes:
  #   webapp-data:
  #     pool: production
  #     config:
  #       size: 10GiB
  #       snapshots.schedule: "@daily"
  #       snapshots.expiry: 7d
  #   webapp-db:
  #     pool: production
  #     config:
  #       size: 20GiB
  #       snapshots.schedule: "@daily"
  #       snapshots.expiry: 14d
  #
  # volume_snapshots:
  #   webapp-data-manual:
  #     name: pre-deployment
  #     pool: production
  #     volume: webapp-data
  #     description: Before deployment
  #   webapp-db-manual:
  #     name: pre-migration
  #     pool: production
  #     volume: webapp-db
  #     description: Before schema migration
  #
  # volume_attachments:
  #   webapp-data-mount:
  #     volume: webapp-data
  #     pool: production
  #     instance: webapp-container
  #     path: /var/www
  #   webapp-db-mount:
  #     volume: webapp-db
  #     pool: production
  #     instance: db-container
  #     path: /var/lib/mysql
