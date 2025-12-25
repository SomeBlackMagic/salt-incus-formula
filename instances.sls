{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set instances = incus.get("instances", {}) %}

{% for inst_name, inst in instances.items() %}
incus-instance-{{ inst_name }}:
  incus.instance_present:
    - name: {{ inst_name | tojson }}
    {%- if inst.get("source") %}
    - source: {{ inst.get("source") | tojson }}
    {%- endif %}
    {%- if inst.get("instance_type") %}
    - instance_type: {{ inst.get("instance_type") | tojson }}
    {%- endif %}
    {%- if inst.get("config") %}
    - config: {{ inst.get("config") | tojson }}
    {%- endif %}
    {%- if inst.get("devices") %}
    - devices: {{ inst.get("devices") | tojson }}
    {%- endif %}
    {%- if inst.get("profiles") %}
    - profiles: {{ inst.get("profiles") | tojson }}
    {%- endif %}
    {%- if inst.get("ephemeral") is not none %}
    - ephemeral: {{ inst.get("ephemeral") | tojson }}
    {%- endif %}

{%- if inst.get("started") %}
incus-instance-{{ inst_name }}-running:
  incus.instance_running:
    - name: {{ inst_name | tojson }}
    {%- if inst.get("wait_is_ready") is not none %}
    - wait_is_ready: {{ inst.get("wait_is_ready") | tojson }}
    {%- endif %}
    {%- if inst.get("ready_timeout") %}
    - ready_timeout: {{ inst.get("ready_timeout") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-instance-{{ inst_name }}
{%- endif %}

{%- if inst.get("wait_cloudinit") %}
incus-instance-{{ inst_name }}-initialized:
  incus.instance_initialized:
    - name: {{ inst_name | tojson }}
    {%- if inst.get("cloudinit_timeout") %}
    - timeout: {{ inst.get("cloudinit_timeout") | tojson }}
    {%- endif %}
    {%- if inst.get("cloudinit_check_interval") %}
    - check_interval: {{ inst.get("cloudinit_check_interval") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-instance-{{ inst_name }}
      {%- if inst.get("started") %}
      - incus: incus-instance-{{ inst_name }}-running
      {%- endif %}
{%- endif %}

{%- if inst.get("restarted") %}
incus-instance-{{ inst_name }}-restarted:
  incus.instance_stopped:
    - name: {{ inst_name | tojson }}
    - force: False
    - require:
      - incus: incus-instance-{{ inst_name }}
  incus.instance_running:
    - name: {{ inst_name | tojson }}
    {%- if inst.get("wait_is_ready") is not none %}
    - wait_is_ready: {{ inst.get("wait_is_ready") | tojson }}
    {%- endif %}
    {%- if inst.get("ready_timeout") %}
    - ready_timeout: {{ inst.get("ready_timeout") | tojson }}
    {%- endif %}
    - require:
      - incus: incus-instance-{{ inst_name }}-restarted
{%- endif %}
{% endfor %}
