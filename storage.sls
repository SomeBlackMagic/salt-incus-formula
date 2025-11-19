{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set storage_pools = incus.get("storage_pools", {}) %}
{% set storage_volumes = incus.get("storage_volumes", {}) %}
{% set volume_snapshots = incus.get("volume_snapshots", {}) %}
{% set volume_attachments = incus.get("volume_attachments", {}) %}

# ======================================================================
# Storage Pools
# ======================================================================

{% for pool_name, pool in storage_pools.items() %}
{%- if pool.get("ensure", "present") == "present" %}
incus_storage_pool_{{ pool_name | replace("-", "_") | replace(".", "_") }}:
  incus.storage_pool_present:
    - name: {{ pool_name | tojson }}
    - driver: {{ pool.get("driver", "dir") | tojson }}
    {%- if pool.get("config") %}
    - config: {{ pool.get("config") | tojson }}
    {%- endif %}
    {%- if pool.get("description") %}
    - description: {{ pool.get("description") | tojson }}
    {%- endif %}

{%- if pool.get("update_config") %}
incus_storage_pool_{{ pool_name | replace("-", "_") | replace(".", "_") }}_config:
  incus.storage_pool_config:
    - name: {{ pool_name | tojson }}
    - config: {{ pool.get("update_config") | tojson }}
    {%- if pool.get("update_description") %}
    - description: {{ pool.get("update_description") | tojson }}
    {%- endif %}
    - require:
      - incus: incus_storage_pool_{{ pool_name | replace("-", "_") | replace(".", "_") }}
{%- endif %}

{%- elif pool.get("ensure") == "absent" %}
incus_storage_pool_{{ pool_name | replace("-", "_") | replace(".", "_") }}_absent:
  incus.storage_pool_absent:
    - name: {{ pool_name | tojson }}
{%- endif %}
{% endfor %}

# ======================================================================
# Storage Volumes
# ======================================================================

{% for volume_id, volume in storage_volumes.items() %}
{%- set vol_name = volume.get("name", volume_id) %}
{%- set vol_pool = volume.get("pool", "default") %}
{%- set safe_volume_id = volume_id | replace("-", "_") | replace(".", "_") %}
{%- set safe_pool_id = vol_pool | replace("-", "_") | replace(".", "_") %}
{%- if volume.get("ensure", "present") == "present" %}
incus_storage_volume_{{ safe_volume_id }}:
  incus.volume_present:
    - name: {{ vol_name | tojson }}
    - pool: {{ vol_pool | tojson }}
    {%- if volume.get("volume_type") %}
    - volume_type: {{ volume.get("volume_type") | tojson }}
    {%- endif %}
    {%- if volume.get("config") %}
    - config: {{ volume.get("config") | tojson }}
    {%- endif %}
    {%- if volume.get("description") %}
    - description: {{ volume.get("description") | tojson }}
    {%- endif %}
    {%- if storage_pools.get(vol_pool) %}
    - require:
      - incus: incus_storage_pool_{{ safe_pool_id }}
    {%- endif %}

{%- if volume.get("update_config") %}
incus_storage_volume_{{ safe_volume_id }}_config:
  incus.volume_config:
    - name: {{ vol_name | tojson }}
    - pool: {{ vol_pool | tojson }}
    {%- if volume.get("volume_type") %}
    - volume_type: {{ volume.get("volume_type") | tojson }}
    {%- endif %}
    - config: {{ volume.get("update_config") | tojson }}
    {%- if volume.get("update_description") %}
    - description: {{ volume.get("update_description") | tojson }}
    {%- endif %}
    - require:
      - incus: incus_storage_volume_{{ safe_volume_id }}
{%- endif %}

{%- elif volume.get("ensure") == "absent" %}
incus_storage_volume_{{ safe_volume_id }}_absent:
  incus.volume_absent:
    - name: {{ vol_name | tojson }}
    - pool: {{ vol_pool | tojson }}
    {%- if volume.get("volume_type") %}
    - volume_type: {{ volume.get("volume_type") | tojson }}
    {%- endif %}
{%- endif %}
{% endfor %}

# ======================================================================
# Volume Snapshots
# ======================================================================

{% for snapshot_id, snapshot in volume_snapshots.items() %}
{%- set snap_name = snapshot.get("name", snapshot_id) %}
{%- set snap_pool = snapshot.get("pool", "default") %}
{%- set snap_volume = snapshot.get("volume") %}
{%- set safe_snapshot_id = snapshot_id | replace("-", "_") | replace(".", "_") %}
{%- if snap_volume %}
{%- if snapshot.get("ensure", "present") == "present" %}
incus_volume_snapshot_{{ safe_snapshot_id }}:
  incus.volume_snapshot_present:
    - name: {{ snap_name | tojson }}
    - pool: {{ snap_pool | tojson }}
    - volume: {{ snap_volume | tojson }}
    {%- if snapshot.get("volume_type") %}
    - volume_type: {{ snapshot.get("volume_type") | tojson }}
    {%- endif %}
    {%- if snapshot.get("description") %}
    - description: {{ snapshot.get("description") | tojson }}
    {%- endif %}
    {%- set volume_ref = None %}
    {%- for vol_id, vol in storage_volumes.items() %}
      {%- if vol.get("name", vol_id) == snap_volume and vol.get("pool", "default") == snap_pool %}
        {%- set volume_ref = vol_id | replace("-", "_") | replace(".", "_") %}
      {%- endif %}
    {%- endfor %}
    {%- if volume_ref %}
    - require:
      - incus: incus_storage_volume_{{ volume_ref }}
    {%- endif %}

{%- elif snapshot.get("ensure") == "absent" %}
incus_volume_snapshot_{{ safe_snapshot_id }}_absent:
  incus.volume_snapshot_absent:
    - name: {{ snap_name | tojson }}
    - pool: {{ snap_pool | tojson }}
    - volume: {{ snap_volume | tojson }}
    {%- if snapshot.get("volume_type") %}
    - volume_type: {{ snapshot.get("volume_type") | tojson }}
    {%- endif %}
{%- endif %}
{%- endif %}
{% endfor %}

# ======================================================================
# Volume Attachments
# ======================================================================

{% for attachment_id, attachment in volume_attachments.items() %}
{%- set vol_name = attachment.get("volume") %}
{%- set vol_pool = attachment.get("pool", "default") %}
{%- set instance_name = attachment.get("instance") %}
{%- set safe_attachment_id = attachment_id | replace("-", "_") | replace(".", "_") %}
{%- if vol_name and instance_name %}
{%- if attachment.get("ensure", "attached") == "attached" %}
incus_volume_attachment_{{ safe_attachment_id }}:
  incus.volume_attached:
    - name: {{ vol_name | tojson }}
    - pool: {{ vol_pool | tojson }}
    - instance: {{ instance_name | tojson }}
    {%- if attachment.get("device_name") %}
    - device_name: {{ attachment.get("device_name") | tojson }}
    {%- endif %}
    {%- if attachment.get("path") %}
    - path: {{ attachment.get("path") | tojson }}
    {%- endif %}
    {%- if attachment.get("volume_type") %}
    - volume_type: {{ attachment.get("volume_type") | tojson }}
    {%- endif %}
    {%- set volume_ref = None %}
    {%- for vol_id, vol in storage_volumes.items() %}
      {%- if vol.get("name", vol_id) == vol_name and vol.get("pool", "default") == vol_pool %}
        {%- set volume_ref = vol_id | replace("-", "_") | replace(".", "_") %}
      {%- endif %}
    {%- endfor %}
    {%- if volume_ref %}
    - require:
      - incus: incus_storage_volume_{{ volume_ref }}
    {%- endif %}

{%- elif attachment.get("ensure") == "detached" %}
incus_volume_attachment_{{ safe_attachment_id }}_detached:
  incus.volume_detached:
    - name: {{ vol_name | tojson }}
    - pool: {{ vol_pool | tojson }}
    - instance: {{ instance_name | tojson }}
    {%- if attachment.get("device_name") %}
    - device_name: {{ attachment.get("device_name") | tojson }}
    {%- endif %}
{%- endif %}
{%- endif %}
{% endfor %}
