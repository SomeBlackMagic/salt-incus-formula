{%- from tpldir ~ "/map.jinja" import incus with context %}
{%- set api_client = incus.get("api_client", {}) %}
{%- set storage = api_client.get("storage", {}) %}

{%- if incus.get("enable", False) and api_client.get("enabled", False) and api_client.get("trust_import", False) %}
incus-api-client-trust:
  incus_pki.trust_present:
    - name: {{ api_client.get("trust_name", "salt-cloud") }}
    - storage: {{ storage | tojson }}
    - restricted: {{ api_client.get("trust_restricted", False) }}
    - require:
      - service: incus-service
{%- endif %}
