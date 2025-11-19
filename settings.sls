{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set server_settings = incus.get("server_settings", {}) %}
{% set server_settings_individual = incus.get("server_settings_individual", {}) %}

# ======================================================================
# Server Settings
# ======================================================================
# Incus server global configuration controls various aspects including:
# - HTTPS address and trust password (core.*)
# - Automatic image updates (images.*)
# - Cluster configuration (cluster.*)
# - Storage configuration (storage.*)
# - And many other server-wide settings
#
#  can be managed in three ways:
# 1. Bulk update via server_settings (merges with existing)
# 2. Individual settings via server_settings_individual
# 3. Exact match via managed_settings (replaces all)
# ======================================================================

# Bulk server settings (merged with existing)
{% if server_settings.get("config") %}
incus-server-settings:
  incus.settings_present:
    - name: incus_server_configuration
    - config: {{ server_settings.get("config") | tojson }}
{% endif %}

# Individual settings management
{% for setting_name, setting in server_settings_individual.items() %}
{%- set safe_setting_name = setting_name | replace(".", "_") | replace("-", "_") %}
{%- if setting.get("ensure", "present") == "present" %}
incus-setting-{{ safe_setting_name }}:
  incus.settings_config:
    - name: {{ setting_name | tojson }}
    - key: {{ setting.get("key", setting_name) | tojson }}
    - value: {{ setting.get("value") | tojson }}

{%- elif setting.get("ensure") == "absent" %}
incus-setting-{{ safe_setting_name }}-absent:
  incus.settings_absent:
    - name: {{ setting_name | tojson }}
    - key: {{ setting.get("key", setting_name) | tojson }}
{%- endif %}
{% endfor %}

# Managed settings (exact match - replaces all settings)
{% if server_settings.get("managed") and server_settings.get("managed_config") %}
incus-server-settings-managed:
  incus.settings_managed:
    - name: incus_server_configuration_managed
    - config: {{ server_settings.get("managed_config") | tojson }}
{% endif %}
