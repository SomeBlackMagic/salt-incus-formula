{%- from tpldir ~ "/map.jinja" import incus with context %}
{% set images = incus.get("images", {}) %}

{#
  Note: img_name becomes the PRIMARY alias for the image in Incus.
  Additional aliases can be specified via the 'aliases' parameter.
#}

{% for img_name, img in images.items() %}
incus-image-{{ img_name }}:
  incus.image_present:
    - name: {{ img_name | tojson }}
    {%- if img.get("fingerprint") %}
    - fingerprint: {{ img.get("fingerprint") | tojson }}
    {%- endif %}
    {%- if img.get("source") %}
    - source: {{ img.get("source") | tojson }}
    {%- endif %}
    {%- if img.get("auto_update") is not none %}
    - auto_update: {{ img.get("auto_update") | tojson }}
    {%- endif %}
    {%- if img.get("public") is not none %}
    - public: {{ img.get("public") | tojson }}
    {%- endif %}
    {%- if img.get("aliases") %}
    - aliases: {{ img.get("aliases") | tojson }}
    {%- endif %}
    {%- if img.get("properties") %}
    - properties: {{ img.get("properties") | tojson }}
    {%- endif %}
    {%- if img.get("expires_at") %}
    - expires_at: {{ img.get("expires_at") | tojson }}
    {%- endif %}
    {%- if img.get("compression_algorithm") %}
    - compression_algorithm: {{ img.get("compression_algorithm") | tojson }}
    {%- endif %}
{% endfor %}