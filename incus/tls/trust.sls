# -*- coding: utf-8 -*-
# vim: ft=sls

{%- set tplroot = tpldir.split('/')[0] %}
{%- from tplroot ~ "/map.jinja" import mapdata as incus with context %}

{%- set api_client = incus.get("api_client", {}) %}
{%- set storage = api_client.get("import_storage", {}) %}
{%- set generate = api_client.get("generate", {}) %}

{%- if api_client.get("enabled") %}
incus-api-client-trusted:
  incus_pki.trust_present:
    - name: {{ generate.get("cn", "salt-cloud") }}
    - restricted: {{ api_client.get("restricted", false) | lower }}
    - storage:
        cert: {{ storage.get("cert") }}
        key: {{ storage.get("key") }}
{%- endif %}
