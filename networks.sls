{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set networks = incus.get("networks", {}) %}
{% set network_acls = incus.get("network_acls", {}) %}
{% set network_forwards = incus.get("network_forwards", {}) %}
{% set network_peers = incus.get("network_peers", {}) %}
{% set network_zones = incus.get("network_zones", {}) %}

# ======================================================================
# Networks
# ======================================================================

{% for net_name, net in networks.items() %}
incus-network-{{ net_name }}:
  incus.network_present:
    - name: {{ net_name | tojson }}
    {%- if net.get("network_type") %}
    - network_type: {{ net.get("network_type") | tojson }}
    {%- endif %}
    {%- if net.get("config") %}
    - config: {{ net.get("config") | tojson }}
    {%- endif %}
    {%- if net.get("description") %}
    - description: {{ net.get("description") | tojson }}
    {%- endif %}
{% endfor %}

# ======================================================================
# Network ACLs
# ======================================================================

{% for acl_name, acl in network_acls.items() %}
incus-network-acl-{{ acl_name }}:
  incus.network_acl_present:
    - name: {{ acl_name | tojson }}
    {%- if acl.get("config") %}
    - config: {{ acl.get("config") | tojson }}
    {%- endif %}
    {%- if acl.get("description") %}
    - description: {{ acl.get("description") | tojson }}
    {%- endif %}
    {%- if acl.get("egress") %}
    - egress: {{ acl.get("egress") | tojson }}
    {%- endif %}
    {%- if acl.get("ingress") %}
    - ingress: {{ acl.get("ingress") | tojson }}
    {%- endif %}
{% endfor %}

# ======================================================================
# Network Forwards
# ======================================================================

{% for forward_id, forward in network_forwards.items() %}
incus-network-forward-{{ forward_id }}:
  incus.network_forward_present:
    - network: {{ forward.get("network") | tojson }}
    - listen_address: {{ forward.get("listen_address") | tojson }}
    {%- if forward.get("config") %}
    - config: {{ forward.get("config") | tojson }}
    {%- endif %}
    {%- if forward.get("description") %}
    - description: {{ forward.get("description") | tojson }}
    {%- endif %}
    {%- if forward.get("ports") %}
    - ports: {{ forward.get("ports") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-network-{{ forward.get("network") }}
{% endfor %}

# ======================================================================
# Network Peers
# ======================================================================

{% for peer_id, peer in network_peers.items() %}
incus-network-peer-{{ peer_id }}:
  incus.network_peer_present:
    - network: {{ peer.get("network") | tojson }}
    - peer_name: {{ peer.get("peer_name") | tojson }}
    {%- if peer.get("config") %}
    - config: {{ peer.get("config") | tojson }}
    {%- endif %}
    {%- if peer.get("description") %}
    - description: {{ peer.get("description") | tojson }}
    {%- endif %}
    {%- if peer.get("target_network") %}
    - target_network: {{ peer.get("target_network") | tojson }}
    {%- endif %}
    {%- if peer.get("target_project") %}
    - target_project: {{ peer.get("target_project") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-network-{{ peer.get("network") }}
{% endfor %}

# ======================================================================
# Network Zones (DNS)
# ======================================================================

{% for zone_name, zone in network_zones.items() %}
incus-network-zone-{{ zone_name }}:
  incus.network_zone_present:
    - zone: {{ zone_name | tojson }}
    {%- if zone.get("config") %}
    - config: {{ zone.get("config") | tojson }}
    {%- endif %}
    {%- if zone.get("description") %}
    - description: {{ zone.get("description") | tojson }}
    {%- endif %}

{# Network Zone Records #}
{%- if zone.get("records") %}
{%- for record_name, record in zone.get("records").items() %}
incus-network-zone-{{ zone_name }}-record-{{ record_name }}:
  incus.network_zone_record_present:
    - zone: {{ zone_name | tojson }}
    - record_name: {{ record_name | tojson }}
    {%- if record.get("config") %}
    - config: {{ record.get("config") | tojson }}
    {%- endif %}
    {%- if record.get("description") %}
    - description: {{ record.get("description") | tojson }}
    {%- endif %}
    {%- if record.get("entries") %}
    - entries: {{ record.get("entries") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-network-zone-{{ zone_name }}
{%- endfor %}
{%- endif %}
{% endfor %}
