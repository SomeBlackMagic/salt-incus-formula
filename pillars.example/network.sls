# ======================================================================
# Incus Network Configuration Example
# ======================================================================
# This pillar file demonstrates all network-related configurations
# available in the Incus Salt formula.
#
# Usage:
#   1. Copy this file to your pillar directory
#   2. Customize the values according to your needs
#   3. Include in your top.sls or specific minion pillar
# ======================================================================

incus:
  # ====================================================================
  # Networks
  # ====================================================================
  # Define Incus networks with full configuration support
  networks:
    # Bridge network example
    mybr0:
      network_type: bridge
      description: Main bridge network for containers
      config:
        # IPv4 configuration
        ipv4.address: 10.100.0.1/24
        ipv4.nat: "true"
        ipv4.dhcp: "true"
        ipv4.dhcp.ranges: 10.100.0.100-10.100.0.200
        ipv4.routing: "true"

        # IPv6 configuration
        ipv6.address: fd42:1234:5678::1/64
        ipv6.nat: "true"
        ipv6.dhcp: "true"
        ipv6.dhcp.stateful: "true"

        # DNS configuration
        dns.domain: incus.local
        dns.mode: managed
        dns.search: incus.local

        # Bridge specific
        bridge.driver: native
        bridge.mtu: "1500"
        bridge.hwaddr: 00:16:3e:xx:xx:xx

        # Security
        security.acls: default

    # OVN network example
    ovn-net:
      network_type: ovn
      description: OVN overlay network
      config:
        network: ovn-uplink
        ipv4.address: 10.200.0.1/24
        ipv4.nat: "true"
        ipv6.address: none
        dns.domain: ovn.local

    # Physical network example (for direct access)
    physical-net:
      network_type: physical
      description: Physical network passthrough
      config:
        parent: eth0
        mtu: "9000"
        vlan: "100"

    # Macvlan network example
    macvlan-net:
      network_type: macvlan
      description: Macvlan network for direct host network access
      config:
        parent: eth1
        mtu: "1500"
        vlan: "200"

  # ====================================================================
  # Network ACLs (Access Control Lists)
  # ====================================================================
  # Define firewall rules for networks
  network_acls:
    # Default ACL with common rules
    default:
      description: Default ACL for all networks

      # Ingress rules (incoming traffic)
      ingress:
        # Allow SSH from internal network
        - action: allow
          source: 10.0.0.0/8
          destination: ""
          protocol: tcp
          destination_port: "22"
          description: Allow SSH from internal

        # Allow HTTP/HTTPS from anywhere
        - action: allow
          source: ""
          destination: ""
          protocol: tcp
          destination_port: "80,443"
          description: Allow web traffic

        # Allow ping
        - action: allow
          source: ""
          destination: ""
          protocol: icmp4
          icmp_type: "8"
          icmp_code: "0"
          description: Allow ping

        # Drop everything else
        - action: drop
          source: ""
          destination: ""

      # Egress rules (outgoing traffic)
      egress:
        # Allow all outgoing traffic
        - action: allow
          source: ""
          destination: ""

    # Restrictive ACL for DMZ
    dmz:
      description: Restrictive ACL for DMZ instances
      ingress:
        # Only allow HTTP/HTTPS
        - action: allow
          source: ""
          destination: ""
          protocol: tcp
          destination_port: "80,443"

        # Block everything else
        - action: reject
          source: ""
          destination: ""

      egress:
        # Allow DNS
        - action: allow
          source: ""
          destination: ""
          protocol: udp
          destination_port: "53"

        # Allow HTTP/HTTPS for updates
        - action: allow
          source: ""
          destination: ""
          protocol: tcp
          destination_port: "80,443"

        # Drop other traffic
        - action: drop
          source: ""
          destination: ""

    # Internal only ACL
    internal:
      description: Internal network only access
      ingress:
        # Allow from internal networks only
        - action: allow
          source: 10.0.0.0/8
          destination: ""
        - action: allow
          source: 172.16.0.0/12
          destination: ""
        - action: allow
          source: 192.168.0.0/16
          destination: ""

        # Reject external
        - action: reject
          source: ""
          destination: ""

      egress:
        # Allow to internal only
        - action: allow
          source: ""
          destination: 10.0.0.0/8
        - action: allow
          source: ""
          destination: 172.16.0.0/12
        - action: allow
          source: ""
          destination: 192.168.0.0/16

        # Drop external
        - action: drop
          source: ""
          destination: ""

  # ====================================================================
  # Network Forwards (Port Forwarding / NAT)
  # ====================================================================
  # Forward external traffic to internal instances
  network_forwards:
    # Web server forward
    web-forward:
      network: mybr0
      listen_address: 10.100.0.1
      description: Forward web traffic to internal web server
      ports:
        # HTTP
        - listen_port: "80"
          protocol: tcp
          target_address: 10.100.0.10
          target_port: "8080"

        # HTTPS
        - listen_port: "443"
          protocol: tcp
          target_address: 10.100.0.10
          target_port: "8443"

    # Database forward
    db-forward:
      network: mybr0
      listen_address: 10.100.0.1
      description: Forward database traffic
      ports:
        # PostgreSQL
        - listen_port: "5432"
          protocol: tcp
          target_address: 10.100.0.20
          target_port: "5432"

        # MySQL
        - listen_port: "3306"
          protocol: tcp
          target_address: 10.100.0.21
          target_port: "3306"

    # SSH bastion forward
    ssh-bastion:
      network: mybr0
      listen_address: 10.100.0.1
      description: SSH jump host
      ports:
        - listen_port: "2222"
          protocol: tcp
          target_address: 10.100.0.30
          target_port: "22"

  # ====================================================================
  # Network Peers (Network Peering for OVN)
  # ====================================================================
  # Connect networks across projects or clusters
  network_peers:
    # Peer to another project
    project-peer:
      network: ovn-net
      peer_name: peer-to-dev
      description: Peer to development project
      target_network: dev-network
      target_project: development

    # Peer to another cluster member
    cluster-peer:
      network: ovn-net
      peer_name: peer-to-node2
      description: Peer to node2
      target_network: cluster-net
      # target_project is optional for same project

  # ====================================================================
  # Network Zones (DNS Zones)
  # ====================================================================
  # Manage internal DNS zones and records
  network_zones:
    # Main internal zone
    incus.local:
      description: Main Incus internal DNS zone
      config:
        dns.nameservers: ns1.incus.local,ns2.incus.local
        peers.ns1.address: 10.100.0.1
        peers.ns2.address: 10.100.0.2

      # DNS records for this zone
      records:
        # Name server records
        ns1:
          description: Primary nameserver
          entries:
            - type: A
              value: 10.100.0.1
            - type: AAAA
              value: fd42:1234:5678::1

        ns2:
          description: Secondary nameserver
          entries:
            - type: A
              value: 10.100.0.2
            - type: AAAA
              value: fd42:1234:5678::2

        # Web server records
        www:
          description: Web server
          entries:
            - type: A
              value: 10.100.0.10
            - type: AAAA
              value: fd42:1234:5678::10

        # Alias for www
        web:
          description: Web server alias
          entries:
            - type: CNAME
              value: www.incus.local.

        # Database server
        db:
          description: Database server
          entries:
            - type: A
              value: 10.100.0.20

        # Mail server
        mail:
          description: Mail server
          entries:
            - type: A
              value: 10.100.0.40
            - type: MX
              value: "10 mail.incus.local."

        # Wildcard record
        "*.dev":
          description: Development wildcard
          entries:
            - type: A
              value: 10.100.0.100

    # Application specific zone
    app.local:
      description: Application DNS zone
      config:
        dns.nameservers: ns1.incus.local

      records:
        api:
          description: API endpoint
          entries:
            - type: A
              value: 10.100.0.50

        frontend:
          description: Frontend application
          entries:
            - type: A
              value: 10.100.0.51

        backend:
          description: Backend application
          entries:
            - type: A
              value: 10.100.0.52

# ======================================================================
# Complete Network Configuration Example
# ======================================================================
# This example shows a complete setup with network, ACLs, and DNS

incus_complete_example:
  networks:
    production:
      network_type: bridge
      description: Production network with full security
      config:
        ipv4.address: 10.10.10.1/24
        ipv4.nat: "true"
        ipv4.dhcp: "true"
        ipv4.dhcp.ranges: 10.10.10.100-10.10.10.200
        ipv6.address: none
        dns.domain: prod.local
        dns.mode: managed
        security.acls: production
        security.acls.default.ingress: drop
        security.acls.default.egress: reject

  network_acls:
    production:
      description: Production environment ACL
      ingress:
        # Allow load balancer
        - action: allow
          source: 10.10.10.10
          protocol: tcp
          destination_port: "80,443"
        # Block everything else
        - action: drop
      egress:
        # Allow DNS
        - action: allow
          protocol: udp
          destination_port: "53"
        # Allow NTP
        - action: allow
          protocol: udp
          destination_port: "123"
        # Allow HTTP/HTTPS for updates
        - action: allow
          protocol: tcp
          destination_port: "80,443"
        # Drop everything else
        - action: drop

  network_forwards:
    prod-lb:
      network: production
      listen_address: 10.10.10.1
      description: Production load balancer
      ports:
        - listen_port: "80"
          protocol: tcp
          target_address: 10.10.10.10
          target_port: "80"
        - listen_port: "443"
          protocol: tcp
          target_address: 10.10.10.10
          target_port: "443"

  network_zones:
    prod.local:
      description: Production DNS zone
      config:
        dns.nameservers: 10.10.10.1
      records:
        lb:
          description: Load balancer
          entries:
            - type: A
              value: 10.10.10.10
        www:
          description: Web frontend
          entries:
            - type: CNAME
              value: lb.prod.local.
