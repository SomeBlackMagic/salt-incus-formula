# ======================================================================
# Incus Cluster Configuration Example
# ======================================================================
# This pillar file demonstrates cluster management in Incus.
#
# Incus clustering allows you to:
# - Manage multiple Incus servers as a single system
# - Distribute instances across cluster members
# - Share storage and networks
# - Provide high availability
# - Scale resources horizontally
#
# Usage:
#   1. Copy this file to your pillar directory
#   2. Customize cluster configuration per node
#   3. Include in your top.sls or node-specific pillars
#   4. Apply with: salt '*' state.apply incus.cluster
#
# IMPORTANT: Cluster setup requires careful planning and coordination
# ======================================================================

incus:
  # ====================================================================
  # Cluster Members
  # ====================================================================
  cluster_members:
    # Primary/Bootstrap node (first node in cluster)
    # NOTE: First node initializes the cluster, others join it
    node1:
      address: 192.168.1.101
      cluster_password: "{{ pillar.get('incus_cluster_password', 'changeme') }}"
      description: Primary cluster node

    # Additional cluster members
    node2:
      address: 192.168.1.102
      cluster_password: "{{ pillar.get('incus_cluster_password', 'changeme') }}"
      description: Secondary cluster node

    node3:
      address: 192.168.1.103
      cluster_password: "{{ pillar.get('incus_cluster_password', 'changeme') }}"
      description: Tertiary cluster node

# ======================================================================
# Cluster Configuration Patterns
# ======================================================================

# Pattern 1: Three-Node Production Cluster
incus_production_cluster:
  cluster_members:
    prod-node1:
      address: 10.0.1.10
      cluster_password: "{{ pillar.get('prod_cluster_password') }}"
      description: Production cluster node 1 - Primary

    prod-node2:
      address: 10.0.1.11
      cluster_password: "{{ pillar.get('prod_cluster_password') }}"
      description: Production cluster node 2

    prod-node3:
      address: 10.0.1.12
      cluster_password: "{{ pillar.get('prod_cluster_password') }}"
      description: Production cluster node 3

# Pattern 2: Large Cluster (5+ nodes)
incus_large_cluster:
  cluster_members:
    cluster-node-01:
      address: 172.16.0.101
      cluster_password: "{{ pillar.get('cluster_secret') }}"
      description: Cluster node 01 - Bootstrap node

    cluster-node-02:
      address: 172.16.0.102
      cluster_password: "{{ pillar.get('cluster_secret') }}"
      description: Cluster node 02

    cluster-node-03:
      address: 172.16.0.103
      cluster_password: "{{ pillar.get('cluster_secret') }}"
      description: Cluster node 03

    cluster-node-04:
      address: 172.16.0.104
      cluster_password: "{{ pillar.get('cluster_secret') }}"
      description: Cluster node 04

    cluster-node-05:
      address: 172.16.0.105
      cluster_password: "{{ pillar.get('cluster_secret') }}"
      description: Cluster node 05

# Pattern 3: Development Cluster
incus_dev_cluster:
  cluster_members:
    dev-node1:
      address: 192.168.100.10
      cluster_password: dev-cluster-pass
      description: Development cluster node 1

    dev-node2:
      address: 192.168.100.11
      cluster_password: dev-cluster-pass
      description: Development cluster node 2

# Pattern 4: Hybrid Cluster (Mixed roles)
incus_hybrid_cluster:
  cluster_members:
    # Compute-focused nodes
    compute-01:
      address: 10.10.10.101
      cluster_password: "{{ pillar.get('cluster_pass') }}"
      description: Compute node 01 - High CPU/RAM

    compute-02:
      address: 10.10.10.102
      cluster_password: "{{ pillar.get('cluster_pass') }}"
      description: Compute node 02 - High CPU/RAM

    # Storage-focused nodes
    storage-01:
      address: 10.10.10.111
      cluster_password: "{{ pillar.get('cluster_pass') }}"
      description: Storage node 01 - Ceph OSD

    storage-02:
      address: 10.10.10.112
      cluster_password: "{{ pillar.get('cluster_pass') }}"
      description: Storage node 02 - Ceph OSD

    # Network-focused node
    network-01:
      address: 10.10.10.121
      cluster_password: "{{ pillar.get('cluster_pass') }}"
      description: Network node 01 - OVN gateway

# ======================================================================
# Per-Node Cluster Configuration
# ======================================================================
# Use grains or pillar targeting to configure each node appropriately

# Bootstrap node (first node) - Run first
{% if grains['id'] == 'incus-node1' %}
incus_bootstrap:
  server_settings:
    config:
      cluster.https_address: "{{ grains['ipv4'][0] }}:8443"
      core.https_address: "[::]:8443"
{% endif %}

# Joining nodes - Run after bootstrap
{% if grains['id'] in ['incus-node2', 'incus-node3'] %}
incus_join_cluster:
  cluster_members:
    {{ grains['id'] }}:
      address: "{{ grains['ipv4'][0] }}"
      cluster_password: "{{ pillar.get('cluster_password') }}"
      description: Cluster member {{ grains['id'] }}
{% endif %}

# ======================================================================
# Cluster Server Settings
# ======================================================================
# These settings should be consistent across all cluster nodes

incus_cluster_settings:
  server_settings:
    config:
      # Cluster communication
      cluster.https_address: "{{ grains['ipv4'][0] }}:8443"
      cluster.offline_threshold: "120"  # Seconds before offline

      # Image replication in cluster
      cluster.images_minimal_replica: "3"  # Minimum image copies

      # Cluster healing
      cluster.healing_threshold: "0"  # Auto-healing threshold

      # Database configuration
      cluster.max_voters: "3"  # Raft voters
      cluster.max_standby: "2"  # Standby members

      # HTTPS API
      core.https_address: "[::]:8443"

# ======================================================================
# Cluster Storage Configuration
# ======================================================================
# Cluster storage can be local or shared

incus_cluster_storage:
  storage_pools:
    # Local storage on each node
    local:
      driver: dir
      config:
        source: /var/lib/incus/storage-pools/local
      description: Local storage pool (node-specific)

    # Ceph storage (shared across cluster)
    ceph-pool:
      driver: ceph
      config:
        source: incus
        ceph.cluster_name: ceph
        ceph.osd.pg_num: "32"
        ceph.rbd.clone_copy: "true"
        ceph.user.name: admin
      description: Shared Ceph storage pool

    # ZFS storage (local per node, but with same name)
    zfs-pool:
      driver: zfs
      config:
        source: tank/incus
        volume.zfs.remove_snapshots: "true"
      description: Local ZFS storage pool

# ======================================================================
# Cluster Network Configuration
# ======================================================================
# Networks can be cluster-aware (OVN) or local

incus_cluster_networks:
  networks:
    # OVN network (spans entire cluster)
    ovn-cluster:
      network_type: ovn
      config:
        network: ovn-uplink
        ipv4.address: 10.200.0.1/16
        ipv4.nat: "true"
        ipv6.address: none
        dns.domain: cluster.local
      description: Cluster-wide OVN network

    # Local bridge (per-node)
    lxdbr0:
      network_type: bridge
      config:
        ipv4.address: 10.0.0.1/24
        ipv4.nat: "true"
        ipv6.address: none
      description: Local bridge network

# ======================================================================
# Cluster Member Removal
# ======================================================================
# Example of removing members from cluster

incus_remove_members:
  cluster_members:
    old-node:
      ensure: absent
      force: true  # Force removal if node is offline

# ======================================================================
# Important Notes
# ======================================================================
#
# Cluster Setup Process:
#   1. Bootstrap first node:
#      - Initialize cluster on first node
#      - Configure cluster.https_address
#      - Set cluster password
#
#   2. Join additional nodes:
#      - Configure cluster.https_address on joining node
#      - Provide bootstrap node address
#      - Use same cluster password
#      - Node will download cluster state
#
#   3. Verify cluster:
#      - Check cluster status
#      - Verify all nodes are online
#      - Test instance creation/migration
#
# Network Requirements:
#   - All nodes must be able to reach each other
#   - Port 8443 must be open between nodes
#   - Low latency network recommended
#   - Reliable network connection critical
#
# Storage Considerations:
#   - Use shared storage (Ceph) for HA
#   - Or use local storage with live migration
#   - Storage pools must be configured cluster-wide
#   - Consider I/O requirements per node
#
# High Availability:
#   - Minimum 3 nodes recommended for HA
#   - Use odd number of nodes (3, 5, 7)
#   - Configure instance placement policies
#   - Test failover scenarios
#
# Cluster State:
#   - Cluster uses Raft consensus (like etcd)
#   - Requires majority of nodes online
#   - 3-node cluster can survive 1 node failure
#   - 5-node cluster can survive 2 node failures
#
# Database:
#   - Cluster state stored in distributed database
#   - max_voters controls Raft voters (3-7 recommended)
#   - max_standby controls non-voting members
#   - Database backed up automatically
#
# Monitoring:
#   - Monitor cluster member status
#   - Watch for offline members
#   - Alert on cluster health issues
#   - Monitor network latency between nodes
#
# Maintenance:
#   - Plan rolling updates
#   - Test updates in dev/staging first
#   - One node at a time for updates
#   - Verify cluster health after each update
#
# Security:
#   - Use strong cluster password
#   - Rotate cluster password periodically
#   - Use TLS for all cluster communication
#   - Firewall rules between nodes
#   - Consider VPN/private network
#
# Troubleshooting:
#   - Check cluster status: incus cluster list
#   - View member details: incus cluster show <member>
#   - Check database: incus admin sql
#   - Review logs: journalctl -u incus
#   - Force evacuate: incus cluster evacuate <member>
#
# Cluster Limitations:
#   - Maximum recommended: 50 nodes
#   - Network latency important (< 50ms)
#   - All nodes must run same Incus version
#   - Cluster password required for all operations
#
# ======================================================================
