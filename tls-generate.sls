{%- from tpldir ~ "/map.jinja" import incus with context %}
{%- set api_client = incus.get("api_client", {}) %}
{%- set storage = api_client.get("generate_storage", {}) %}
{%- set generate = api_client.get("generate", {}) %}

{%- if api_client.get("enabled") %}
incus-api-client-keypair:
  incus_pki.keypair_present:
    - name: {{ generate.get("cn", "salt-cloud") }}
    - storage:
        cert: {{ storage.get("cert") }}
        key: {{ storage.get("key") }}
    - generate:
        cn: {{ generate.get("cn", "salt-cloud") }}
        days: {{ generate.get("days", 3650) }}
{%- endif %}
