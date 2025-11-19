# Incus Cluster Management

This document describes how to manage Incus clusters using Salt states.

## Table of Contents

- [Overview](#overview)
- [State Functions](#state-functions)
- [Cluster Setup](#cluster-setup)
- [Configuration Examples](#configuration-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Incus clustering allows you to manage multiple Incus servers as a single system, providing:

- **Unified Management**: Manage all nodes from a single interface
- **Resource Distribution**: Distribute instances across cluster members
- **High Availability**: Automatic failover and live migration
- **Shared Resources**: Share storage pools and networks across nodes
- **Horizontal Scaling**: Add nodes to increase capacity

### Architecture

- **Distributed Database**: Cluster state stored in Raft-based database
- **Leader Election**: Automatic leader election for coordination
- **Quorum Requirements**: Requires majority of nodes online
- **TLS Communication**: Secure communication between nodes

## State Functions

### cluster_member_present

Ensure a cluster member exists (add node to cluster).

**Parameters:**
- `name` (required): Member name
- `address` (required): Member address (IP:PORT)
- `cluster_password` (required): Cluster password

**Example:**

```yaml
node2:
  incus.cluster_member_present:
    - address: 192.168.1.102
    - cluster_password: secret123
```

### cluster_member_absent

Ensure a cluster member does not exist (remove from cluster).

**Parameters:**
- `name` (required): Member name
- `force` (optional): Force removal even if offline (default: `false`)

**Example:**

```yaml
old-node:
  incus.cluster_member_absent:
    - force: true
```

## Cluster Setup

### Prerequisites

1. **Network Requirements**:
   - All nodes must be able to reach each other
   - Port 8443 open between all nodes
   - Low latency network (< 50ms recommended)
   - Reliable network connection

2. **Software Requirements**:
   - Same Incus version on all nodes
   - Time synchronization (NTP)
   - DNS resolution between nodes

3. **Storage Requirements**:
   - Shared storage (Ceph) for HA, or
   - Local storage with migration capability
   - Sufficient disk space on all nodes

### Step 1: Bootstrap First Node

Configure the first (bootstrap) node:

```yaml
# On first node (e.g., node1)
incus:
  server_settings:
    config:
      core.https_address: "[::]:8443"
      cluster.https_address: "{{ grains['ipv4'][0] }}:8443"
      core.trust_password: "cluster-secret-password"
```

Apply configuration:
```bash
salt 'node1' state.apply incus.settings
```

Initialize cluster:
```bash
# On node1
incus cluster enable node1
```

### Step 2: Join Additional Nodes

Configure joining nodes:

```yaml
# On node2, node3, etc.
incus:
  cluster_members:
    node2:
      address: 192.168.1.102
      cluster_password: cluster-secret-password
```

Apply configuration:
```bash
salt 'node2' state.apply incus.cluster
salt 'node3' state.apply incus.cluster
```

### Step 3: Verify Cluster

Check cluster status:
```bash
incus cluster list
incus cluster show node1
```

## Configuration Examples

### Basic 3-Node Cluster

```yaml
# Bootstrap node (node1)
incus_bootstrap:
  server_settings:
    config:
      cluster.https_address: "192.168.1.101:8443"
      core.https_address: "[::]:8443"

# Joining nodes (node2, node3)
incus_cluster:
  cluster_members:
    node2:
      address: 192.168.1.102
      cluster_password: "{{ pillar['cluster_secret'] }}"
      description: Cluster node 2

    node3:
      address: 192.168.1.103
      cluster_password: "{{ pillar['cluster_secret'] }}"
      description: Cluster node 3
```

### Large Cluster (5+ Nodes)

```yaml
incus:
  server_settings:
    config:
      cluster.https_address: "{{ grains['ipv4'][0] }}:8443"
      cluster.offline_threshold: "120"        # 2 minutes
      cluster.images_minimal_replica: "3"     # 3 image copies
      cluster.max_voters: "5"                 # 5 Raft voters
      cluster.max_standby: "2"                # 2 standby members
      cluster.healing_threshold: "0"          # Auto-healing

  cluster_members:
    node-02:
      address: 172.16.0.102
      cluster_password: "{{ pillar['cluster_password'] }}"
    node-03:
      address: 172.16.0.103
      cluster_password: "{{ pillar['cluster_password'] }}"
    node-04:
      address: 172.16.0.104
      cluster_password: "{{ pillar['cluster_password'] }}"
    node-05:
      address: 172.16.0.105
      cluster_password: "{{ pillar['cluster_password'] }}"
```

### Hybrid Cluster (Specialized Roles)

```yaml
incus:
  cluster_members:
    # Compute nodes (high CPU/RAM)
    compute-01:
      address: 10.0.1.101
      cluster_password: "{{ pillar['cluster_password'] }}"
      description: Compute node - 64 cores, 256GB RAM

    compute-02:
      address: 10.0.1.102
      cluster_password: "{{ pillar['cluster_password'] }}"
      description: Compute node - 64 cores, 256GB RAM

    # Storage nodes (Ceph OSDs)
    storage-01:
      address: 10.0.1.111
      cluster_password: "{{ pillar['cluster_password'] }}"
      description: Storage node - Ceph OSD

    storage-02:
      address: 10.0.1.112
      cluster_password: "{{ pillar['cluster_password'] }}"
      description: Storage node - Ceph OSD

    # Network node (OVN gateway)
    network-01:
      address: 10.0.1.121
      cluster_password: "{{ pillar['cluster_password'] }}"
      description: Network node - OVN gateway
```

### Per-Node Configuration with Grains

```yaml
# Bootstrap node
{% if grains['id'] == 'incus-node1' %}
incus_bootstrap:
  server_settings:
    config:
      cluster.https_address: "{{ grains['ipv4'][0] }}:8443"
      core.https_address: "[::]:8443"
{% endif %}

# Joining nodes
{% if grains['id'] in ['incus-node2', 'incus-node3'] %}
incus_join:
  cluster_members:
    {{ grains['id'] }}:
      address: "{{ grains['ipv4'][0] }}"
      cluster_password: "{{ pillar['cluster_password'] }}"
{% endif %}
```

### Cluster Storage Configuration

```yaml
incus:
  storage_pools:
    # Local storage (per node)
    local:
      driver: dir
      config:
        source: /var/lib/incus/storage-pools/local
      description: Local storage pool

    # Shared Ceph storage (cluster-wide)
    ceph-pool:
      driver: ceph
      config:
        source: incus
        ceph.cluster_name: ceph
        ceph.osd.pg_num: "32"
        ceph.rbd.clone_copy: "true"
      description: Shared Ceph storage pool
```

### Cluster Networks

```yaml
incus:
  networks:
    # OVN network (spans entire cluster)
    ovn-cluster:
      network_type: ovn
      config:
        network: ovn-uplink
        ipv4.address: 10.200.0.1/16
        ipv4.nat: "true"
        dns.domain: cluster.local
      description: Cluster-wide OVN network

    # Local bridge (per-node)
    lxdbr0:
      network_type: bridge
      config:
        ipv4.address: 10.0.0.1/24
        ipv4.nat: "true"
      description: Local bridge network
```

## Best Practices

### Cluster Sizing

**Minimum**: 3 nodes
- Survives 1 node failure
- Maintains quorum with 2 nodes

**Recommended**: 5 nodes
- Survives 2 node failures
- Better resource distribution
- More redundancy

**Maximum**: 50 nodes
- Practical limit for most deployments
- Consider multiple clusters for larger scale

### Node Count (Odd Numbers)

Always use **odd number of nodes** for better quorum:

| Nodes | Failures Tolerated | Quorum Requires |
|-------|-------------------|-----------------|
| 3     | 1                 | 2               |
| 5     | 2                 | 3               |
| 7     | 3                 | 4               |

### High Availability

1. **Shared Storage Required**:
   ```yaml
   storage_pools:
     ceph-pool:
       driver: ceph  # or other shared storage
   ```

2. **Enable Stateful Migration**:
   ```yaml
   instances:
     ha-app:
       config:
         migration.stateful: "true"
   ```

3. **Use Multiple Replicas**:
   ```yaml
   server_settings:
     config:
       cluster.images_minimal_replica: "3"
   ```

### Security

1. **Strong Cluster Password**:
   ```yaml
   # Store in pillar with encryption
   cluster_password: "{{ pillar['encrypted_cluster_password'] }}"
   ```

2. **Network Isolation**:
   - Use private network for cluster traffic
   - Firewall rules between nodes
   - Consider VPN or private VLAN

3. **TLS Certificates**:
   - Verify TLS certificates
   - Rotate certificates regularly
   - Use proper CA infrastructure

### Monitoring

Monitor these metrics:
- Cluster member status
- Database replication lag
- Network latency between nodes
- Storage pool health
- Instance distribution

```bash
# Check cluster health
incus cluster list
incus cluster show <member>

# Check database status
incus admin sql "SELECT * FROM nodes"

# Monitor specific member
watch -n 5 incus cluster show node2
```

### Maintenance

**Rolling Updates**:
1. Update one node at a time
2. Verify cluster health after each update
3. Wait for stabilization before next node
4. Test in dev/staging first

```bash
# Update sequence
salt 'node1' pkg.upgrade
salt 'node1' service.restart incus
# Wait and verify
incus cluster list

salt 'node2' pkg.upgrade
# ... and so on
```

**Node Evacuation**:
```bash
# Before maintenance
incus cluster evacuate node2

# After maintenance
incus cluster restore node2
```

## Troubleshooting

### Node Won't Join Cluster

**Problem**: New node fails to join cluster

**Solutions**:
1. Verify network connectivity:
   ```bash
   ping <bootstrap-node>
   telnet <bootstrap-node> 8443
   ```

2. Check cluster password:
   ```bash
   # On bootstrap node
   incus config get core.trust_password
   ```

3. Verify Incus versions match:
   ```bash
   incus version
   ```

4. Check firewall rules:
   ```bash
   iptables -L | grep 8443
   ```

### Node Offline

**Problem**: Cluster member shows as offline

**Solutions**:
1. Check node status:
   ```bash
   systemctl status incus
   journalctl -u incus -n 100
   ```

2. Verify network connectivity:
   ```bash
   ping <offline-node>
   ```

3. Force remove if permanently offline:
   ```yaml
   old-node:
     incus.cluster_member_absent:
       - force: true
   ```

### Split Brain

**Problem**: Cluster split into multiple parts

**Prevention**:
- Use odd number of nodes
- Ensure reliable network
- Monitor quorum status

**Recovery**:
1. Stop Incus on minority nodes
2. Let majority partition continue
3. Re-join minority nodes

### Database Issues

**Problem**: Database corruption or sync issues

**Solutions**:
1. Check database status:
   ```bash
   incus admin sql ".tables"
   ```

2. Backup database:
   ```bash
   incus admin cluster recover-from-quorum-loss
   ```

3. Restore from backup if needed

### Performance Degradation

**Problem**: Cluster performance slow

**Solutions**:
1. Check network latency:
   ```bash
   ping -c 10 <node>
   ```

2. Monitor database load:
   ```bash
   incus admin sql "PRAGMA wal_checkpoint"
   ```

3. Review instance distribution:
   ```bash
   incus list --all-projects
   ```

4. Check storage pool performance:
   ```bash
   incus storage info <pool>
   ```

## Related Documentation

- [settings.md](settings.md) - Server settings configuration
- [storages.md](storages.md) - Cluster storage configuration
- [networks.md](networks.md) - Cluster networking
- [Incus Clustering Documentation](https://linuxcontainers.org/incus/docs/main/clustering/)

## See Also

- Pillar example: `pillars.example/cluster.sls`
- State module: `_states/incus.py` (lines 3123-3259)
- Settings state: `settings.sls`
