# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as incus with context %}

{% set server_settings = incus.get("server_settings") | default({}, true) %}
{% set server_settings_individual = incus.get("server_settings_individual") | default({}, true) %}

# ======================================================================
# Server Settings
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
