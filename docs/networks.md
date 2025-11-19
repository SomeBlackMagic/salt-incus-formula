# Incus Network Management

Complete guide for managing Incus networks through Salt.

## Table of Contents

- [Overview](#overview)
- [Pillar Structure](#pillar-structure)
- [Networks](#networks)
- [ACL (Access Control Lists)](#acl-access-control-lists)
- [Forwards (Port Forwarding)](#forwards-port-forwarding)
- [Peering (Network Peers)](#peering-network-peers)
- [DNS Zones](#dns-zones)
- [Usage Examples](#usage-examples)

## Overview

Salt module for Incus supports complete network infrastructure management:

- **Networks**: Bridge, OVN, Physical, Macvlan, SR-IOV
- **ACL**: Firewall rules for networks
- **Forwards**: NAT and port forwarding
- **Peering**: Network connections between projects
- **DNS Zones**: Internal DNS for instances

## Pillar Structure

```yaml
incus:
  networks: {}           # Network definitions
  network_acls: {}       # ACL rules
  network_forwards: {}   # Port forwarding
  network_peers: {}      # Network peering
  network_zones: {}      # DNS zones and records
```

## Networks

### Network Types

#### 1. Bridge Network (Most Common)

```yaml
incus:
  networks:
    mybr0:
      network_type: bridge
      description: Main bridge network
      config:
        # IPv4
        ipv4.address: 10.0.0.1/24
        ipv4.nat: "true"
        ipv4.dhcp: "true"
        ipv4.dhcp.ranges: 10.0.0.100-10.0.0.200

        # IPv6
        ipv6.address: fd42::1/64
        ipv6.nat: "true"
        ipv6.dhcp: "true"

        # DNS
        dns.domain: incus.local
        dns.mode: managed
```

#### 2. OVN Network (Overlay Network)

```yaml
incus:
  networks:
    ovn-network:
      network_type: ovn
      description: OVN overlay network
      config:
        network: ovn-uplink          # Parent uplink network
        ipv4.address: 192.168.1.1/24
        ipv4.nat: "true"
```

#### 3. Physical Network (Direct Access to Physical Interface)

```yaml
incus:
  networks:
    external:
      network_type: physical
      description: Direct access to eth0
      config:
        parent: eth0
        mtu: "9000"
        vlan: "100"
```

#### 4. Macvlan Network

```yaml
incus:
  networks:
    macvlan-net:
      network_type: macvlan
      description: Macvlan for direct access
      config:
        parent: eth1
        vlan: "200"
```

### Network Configuration Parameters

#### IPv4/IPv6 Parameters:
- `ipv4.address` / `ipv6.address` - IP address and network mask
- `ipv4.nat` / `ipv6.nat` - Enable NAT (true/false)
- `ipv4.dhcp` / `ipv6.dhcp` - Enable DHCP (true/false)
- `ipv4.dhcp.ranges` - DHCP address range
- `ipv4.routing` / `ipv6.routing` - IP forwarding
- `ipv4.ovn.ranges` - Ranges for OVN

#### DNS Parameters:
- `dns.domain` - Domain name for the network
- `dns.mode` - DNS mode (managed/dynamic/none)
- `dns.search` - List of domains for search
- `dns.zone.forward` - Forward resolution zone
- `dns.zone.reverse.ipv4` - IPv4 reverse resolution zone

#### Bridge Parameters:
- `bridge.driver` - Bridge driver (native/openvswitch)
- `bridge.external_interfaces` - External interfaces
- `bridge.hwaddr` - Bridge MAC address
- `bridge.mtu` - Bridge MTU

#### Security:
- `security.acls` - Applied ACLs
- `security.acls.default.ingress` - Default action for incoming traffic
- `security.acls.default.egress` - Default action for outgoing traffic

## ACL (Access Control Lists)

ACLs allow controlling network traffic at the network level.

### Basic Structure

```yaml
incus:
  network_acls:
    acl_name:
      description: ACL description
      config: {}                    # Additional parameters
      ingress: []                   # Rules for incoming traffic
      egress: []                    # Rules for outgoing traffic
```

### Rule Structure

```yaml
- action: allow|reject|drop       # Action
  source: 10.0.0.0/24             # Source (CIDR or empty for any)
  destination: 192.168.1.0/24     # Destination
  protocol: tcp|udp|icmp4|icmp6   # Protocol
  source_port: "1024-65535"       # Source port
  destination_port: "80,443"      # Destination port
  icmp_type: "8"                  # ICMP type
  icmp_code: "0"                  # ICMP code
  description: Rule description
  state: enabled|disabled|logged  # Rule state
```

### ACL Examples

#### Allow Only HTTP/HTTPS

```yaml
incus:
  network_acls:
    web-only:
      description: Web traffic only
      ingress:
        - action: allow
          protocol: tcp
          destination_port: "80,443"
          description: HTTP and HTTPS
        - action: drop
          description: Block everything else
      egress:
        - action: allow
          description: Allow all outgoing traffic
```

#### Internal Network

```yaml
incus:
  network_acls:
    internal:
      description: Internal access only
      ingress:
        - action: allow
          source: 10.0.0.0/8
        - action: allow
          source: 172.16.0.0/12
        - action: allow
          source: 192.168.0.0/16
        - action: reject
          description: Reject external traffic
      egress:
        - action: allow
          destination: 10.0.0.0/8
        - action: allow
          destination: 172.16.0.0/12
        - action: allow
          destination: 192.168.0.0/16
        - action: drop
```

## Forwards (Port Forwarding)

Forwards allow forwarding traffic from a network IP address to specific instances.

### Structure

```yaml
incus:
  network_forwards:
    forward_id:
      network: network_name           # Network name
      listen_address: 10.0.0.1       # Listen address
      description: Description
      config: {}                      # Additional parameters
      ports:                          # Port list
        - listen_port: "80"           # Listen port
          protocol: tcp               # Protocol
          target_address: 10.0.0.10   # Target address
          target_port: "8080"         # Target port
```

### Examples

#### Web Server

```yaml
incus:
  network_forwards:
    web-forward:
      network: mybr0
      listen_address: 10.0.0.1
      description: Web traffic forwarding
      ports:
        - listen_port: "80"
          protocol: tcp
          target_address: 10.0.0.10
          target_port: "8080"
        - listen_port: "443"
          protocol: tcp
          target_address: 10.0.0.10
          target_port: "8443"
```

#### Multiple Services

```yaml
incus:
  network_forwards:
    services:
      network: mybr0
      listen_address: 10.0.0.1
      ports:
        # Web
        - listen_port: "80"
          protocol: tcp
          target_address: 10.0.0.10
          target_port: "80"
        # Database
        - listen_port: "5432"
          protocol: tcp
          target_address: 10.0.0.20
          target_port: "5432"
        # SSH Jump Host
        - listen_port: "2222"
          protocol: tcp
          target_address: 10.0.0.30
          target_port: "22"
```

## Peering (Network Peers)

Peering allows connecting OVN networks between different projects or cluster members.

### Structure

```yaml
incus:
  network_peers:
    peer_id:
      network: network_name           # Local network
      peer_name: peer_identifier      # Peer name
      description: Description
      config: {}                      # Additional parameters
      target_network: remote_network  # Remote network
      target_project: project_name    # Target project (optional)
```

### Examples

#### Connection to Another Project

```yaml
incus:
  network_peers:
    dev-peer:
      network: prod-network
      peer_name: to-development
      description: Connection to dev environment
      target_network: dev-network
      target_project: development
```

#### Cluster Peering

```yaml
incus:
  network_peers:
    cluster-peer:
      network: ovn-net
      peer_name: to-node2
      description: Peering with node2
      target_network: ovn-net
      # target_project not specified = same project
```

## DNS Zones

DNS zones provide automatic name resolution for instances.

### Structure

```yaml
incus:
  network_zones:
    zone.name:
      description: Zone description
      config:
        dns.nameservers: ns1.zone.name,ns2.zone.name
        peers.ns1.address: 10.0.0.1
      records:                        # DNS records
        record_name:
          description: Record description
          config: {}
          entries:                    # Entry list
            - type: A|AAAA|CNAME|MX|TXT|SRV
              value: value
              ttl: 3600               # TTL (optional)
              priority: 10            # Priority for MX/SRV
```

### Supported Record Types

- **A** - IPv4 address
- **AAAA** - IPv6 address
- **CNAME** - Canonical name (alias)
- **MX** - Mail exchanger
- **TXT** - Text record
- **SRV** - Service record
- **PTR** - Pointer record (reverse resolution)

### Examples

#### Basic Zone

```yaml
incus:
  network_zones:
    example.local:
      description: Local DNS zone
      config:
        dns.nameservers: ns1.example.local

      records:
        # A record
        web:
          description: Web server
          entries:
            - type: A
              value: 10.0.0.10

        # AAAA record
        web-ipv6:
          description: Web server IPv6
          entries:
            - type: AAAA
              value: "fd42::10"

        # CNAME
        www:
          description: Alias for web
          entries:
            - type: CNAME
              value: web.example.local.

        # MX record
        mail:
          description: Mail server
          entries:
            - type: A
              value: 10.0.0.20
            - type: MX
              value: "10 mail.example.local."
```

#### Wildcard Records

```yaml
incus:
  network_zones:
    dev.local:
      description: Development zone
      records:
        "*.apps":
          description: Wildcard for all applications
          entries:
            - type: A
              value: 10.0.0.100
```

#### Multiple Records

```yaml
incus:
  network_zones:
    app.local:
      records:
        api:
          description: API endpoints with load balancing
          entries:
            - type: A
              value: 10.0.0.10
            - type: A
              value: 10.0.0.11
            - type: A
              value: 10.0.0.12
```

## Usage Examples

### Simple Isolated Network

```yaml
incus:
  networks:
    isolated:
      network_type: bridge
      description: Isolated network without internet
      config:
        ipv4.address: 192.168.100.1/24
        ipv4.nat: "false"
        ipv4.dhcp: "true"
        ipv6.address: none
        dns.domain: isolated.local
```

### Production Environment with Full Security

```yaml
incus:
  networks:
    production:
      network_type: bridge
      description: Production network
      config:
        ipv4.address: 10.10.10.1/24
        ipv4.nat: "true"
        ipv4.dhcp: "true"
        dns.domain: prod.local
        dns.mode: managed
        security.acls: prod-acl
        security.acls.default.ingress: drop
        security.acls.default.egress: reject

  network_acls:
    prod-acl:
      description: Production ACL
      ingress:
        # Only from load balancer
        - action: allow
          source: 10.10.10.10
          protocol: tcp
          destination_port: "80,443"
        - action: drop
      egress:
        # DNS and NTP
        - action: allow
          protocol: udp
          destination_port: "53,123"
        # Updates
        - action: allow
          protocol: tcp
          destination_port: "80,443"
        - action: drop

  network_forwards:
    prod-lb:
      network: production
      listen_address: 10.10.10.1
      ports:
        - listen_port: "80"
          protocol: tcp
          target_address: 10.10.10.10
          target_port: "80"

  network_zones:
    prod.local:
      config:
        dns.nameservers: 10.10.10.1
      records:
        lb:
          entries:
            - type: A
              value: 10.10.10.10
        www:
          entries:
            - type: CNAME
              value: lb.prod.local.
```

### Microservices Architecture

```yaml
incus:
  networks:
    services:
      network_type: bridge
      config:
        ipv4.address: 10.20.0.1/24
        ipv4.nat: "true"
        ipv4.dhcp: "true"
        dns.domain: svc.local
        dns.mode: managed

  network_zones:
    svc.local:
      description: Microservices
      records:
        api-gateway:
          entries:
            - type: A
              value: 10.20.0.10

        auth-service:
          entries:
            - type: A
              value: 10.20.0.20

        user-service:
          entries:
            - type: A
              value: 10.20.0.21

        product-service:
          entries:
            - type: A
              value: 10.20.0.22

        db-primary:
          entries:
            - type: A
              value: 10.20.0.30

        db-replica:
          entries:
            - type: A
              value: 10.20.0.31
            - type: A
              value: 10.20.0.32

  network_forwards:
    api-gateway-forward:
      network: services
      listen_address: 10.20.0.1
      ports:
        - listen_port: "80"
          protocol: tcp
          target_address: 10.20.0.10
          target_port: "8080"
        - listen_port: "443"
          protocol: tcp
          target_address: 10.20.0.10
          target_port: "8443"
```

## Applying Configuration

### Apply All Networks

```bash
salt 'minion' state.apply incus.network
```

### Apply with Test (dry-run)

```bash
salt 'minion' state.apply incus.network test=True
```

### Apply Specific Network

```bash
salt 'minion' state.sls_id incus-network-mybr0 incus.network
```

## Useful Salt Commands

### List Networks

```bash
salt 'minion' incus.network_list recursion=1
```

### Network Information

```bash
salt 'minion' incus.network_get mybr0
```

### Network State

```bash
salt 'minion' incus.network_state mybr0
```

### DHCP Leases

```bash
salt 'minion' incus.network_lease_list mybr0
```

### List ACLs

```bash
salt 'minion' incus.network_acl_list recursion=1
```

### List DNS Zones

```bash
salt 'minion' incus.network_zone_list recursion=1
```

## Debugging

### Check State Application

```bash
salt 'minion' state.show_sls incus.network
```

### Check Pillar

```bash
salt 'minion' pillar.get incus:networks
```

### Show Low-Level State

```bash
salt 'minion' state.show_low_sls incus.network
```

## Additional Information

- [Official Incus Documentation](https://linuxcontainers.org/incus/docs/main/)
- [Incus Network Configuration](https://linuxcontainers.org/incus/docs/main/reference/network/)
- [Incus ACL Documentation](https://linuxcontainers.org/incus/docs/main/reference/network_acls/)
