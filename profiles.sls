{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set profiles = incus.get("profiles", {}) %}

# ======================================================================
# Profiles
# ======================================================================
# Profiles store configuration that can be applied to instances at
# creation time. They contain configuration options and devices.
#
# Profiles can be:
# - Created with initial config and devices
# - Updated with new config/devices
# - Managed via profile_config for config-only updates
# - Removed when no longer needed
# ======================================================================

{% for profile_name, profile in profiles.items() %}
{%- if profile.get("ensure", "present") == "present" %}
incus-profile-{{ profile_name }}:
  incus.profile_present:
    - name: {{ profile_name | tojson }}
    {%- if profile.get("config") %}
    - config: {{ profile.get("config") | tojson }}
    {%- endif %}
    {%- if profile.get("devices") %}
    - devices: {{ profile.get("devices") | tojson }}
    {%- endif %}
    {%- if profile.get("description") %}
    - description: {{ profile.get("description") | tojson }}
    {%- endif %}

{%- if profile.get("update_config") %}
incus-profile-{{ profile_name }}-config:
  incus.profile_config:
    - name: {{ profile_name | tojson }}
    - config: {{ profile.get("update_config") | tojson }}
    {%- if profile.get("update_description") %}
    - description: {{ profile.get("update_description") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-profile-{{ profile_name }}
{%- endif %}

{%- elif profile.get("ensure") == "absent" %}
incus-profile-{{ profile_name }}-absent:
  incus.profile_absent:
    - name: {{ profile_name | tojson }}
{%- endif %}
{% endfor %}
