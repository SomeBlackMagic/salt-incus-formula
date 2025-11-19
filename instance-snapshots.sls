{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set instance_snapshots = incus.get("instance_snapshots", {}) %}

# ======================================================================
# Instance Snapshots
# ======================================================================
# This state file manages instance snapshots with automatic rotation
# policies. It supports:
# - Creating snapshots (stateful and stateless)
# - Automatic rotation based on retention policies
# - Pattern-based snapshot management
# - Expiry date management
# - Snapshot restoration
# ======================================================================

{% for snapshot_id, snapshot in instance_snapshots.items() %}
{%- set snap_name = snapshot.get("name", snapshot_id) %}
{%- set snap_instance = snapshot.get("instance") %}
{%- set safe_snapshot_id = snapshot_id | replace("-", "_") | replace(".", "_") %}

{%- if snap_instance %}

{# ===== Basic Snapshot Present/Absent ===== #}
{%- if snapshot.get("ensure", "present") == "present" %}
incus_instance_snapshot_{{ safe_snapshot_id }}:
  incus.instance_snapshot_present:
    - instance: {{ snap_instance | tojson }}
    - name: {{ snap_name | tojson }}
    {%- if snapshot.get("stateful") is defined %}
    - stateful: {{ snapshot.get("stateful") | tojson }}
    {%- endif %}
    {%- if snapshot.get("description") %}
    - description: {{ snapshot.get("description") | tojson }}
    {%- endif %}

{# ===== Snapshot Restoration ===== #}
{%- elif snapshot.get("ensure") == "restored" %}
incus_instance_snapshot_{{ safe_snapshot_id }}_restored:
  incus.instance_snapshot_restored:
    - instance: {{ snap_instance | tojson }}
    - name: {{ snap_name | tojson }}

{# ===== Snapshot Absent ===== #}
{%- elif snapshot.get("ensure") == "absent" %}
incus_instance_snapshot_{{ safe_snapshot_id }}_absent:
  incus.instance_snapshot_absent:
    - instance: {{ snap_instance | tojson }}
    - name: {{ snap_name | tojson }}

{%- endif %}

{%- endif %}
{% endfor %}

# ======================================================================
# Managed Snapshots with Rotation
# ======================================================================
# Use instance_snapshots_managed for automated snapshot management
# with rotation policies. This is ideal for scheduled snapshots like
# daily, weekly, monthly backups.
# ======================================================================

{# Group snapshots by instance for managed rotation #}
{%- set managed_snapshots = {} %}
{%- for snapshot_id, snapshot in instance_snapshots.items() %}
  {%- set snap_instance = snapshot.get("instance") %}
  {%- if snap_instance and snapshot.get("managed", False) %}
    {%- if snap_instance not in managed_snapshots %}
      {%- set _ = managed_snapshots.update({snap_instance: {}}) %}
    {%- endif %}
    {%- set _ = managed_snapshots[snap_instance].update({snapshot_id: snapshot}) %}
  {%- endif %}
{%- endfor %}

{# Create managed snapshot states #}
{% for instance_name, snapshots_config in managed_snapshots.items() %}
{%- set safe_instance_name = instance_name | replace("-", "_") | replace(".", "_") %}
incus_instance_snapshots_managed_{{ safe_instance_name }}:
  incus.instance_snapshots_managed:
    - instance: {{ instance_name | tojson }}
    - snapshots_config:
      {%- for snap_id, snap in snapshots_config.items() %}
        {{ snap_id }}:
          name: {{ snap.get("name", snap_id) | tojson }}
          {%- if snap.get("stateful") is defined %}
          stateful: {{ snap.get("stateful") | tojson }}
          {%- endif %}
          {%- if snap.get("description") %}
          description: {{ snap.get("description") | tojson }}
          {%- endif %}
          {%- if snap.get("pattern") %}
          pattern: {{ snap.get("pattern") | tojson }}
          {%- endif %}
          {%- if snap.get("keep") is defined %}
          keep: {{ snap.get("keep") | tojson }}
          {%- endif %}
          {%- if snap.get("expires_at") %}
          expires_at: {{ snap.get("expires_at") | tojson }}
          {%- endif %}
      {%- endfor %}
{% endfor %}

# ======================================================================
# Standalone Snapshot Rotation
# ======================================================================
# Use instance_snapshots_rotated for manual rotation policies.
# This is useful when you want to rotate existing snapshots without
# creating new ones.
# ======================================================================

{%- set rotation_policies = incus.get("snapshot_rotation", {}) %}
{% for policy_id, policy in rotation_policies.items() %}
{%- set policy_instance = policy.get("instance") %}
{%- set policy_pattern = policy.get("pattern") %}
{%- set policy_keep = policy.get("keep") %}
{%- set safe_policy_id = policy_id | replace("-", "_") | replace(".", "_") %}

{%- if policy_instance and policy_pattern and policy_keep is defined %}
incus_snapshot_rotation_{{ safe_policy_id }}:
  incus.instance_snapshots_rotated:
    - instance: {{ policy_instance | tojson }}
    - pattern: {{ policy_pattern | tojson }}
    - keep: {{ policy_keep | tojson }}
{%- endif %}
{% endfor %}
