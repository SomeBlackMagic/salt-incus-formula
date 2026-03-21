{%- from tpldir ~ "/map.jinja" import incus with context %}

{%- set connection = incus.get("connection") | default({}, true) %}
{%- set cert_storage = connection.get("cert_storage") | default({}, true) %}
{%- set cert_storage_type = cert_storage.get("type", "local_files") %}
{%- set client_cert = incus.get("client_cert") | default({}, true) %}
{%- set client_cert_enable = client_cert.get("enable", false) %}

{%- if client_cert_enable %}
  {%- set cert_path = client_cert.get("cert_path") %}
  {%- if not cert_path and cert_storage_type == "local_files" %}
    {%- set cert_path = cert_storage.get("cert") %}
  {%- endif %}

  {%- set key_path = client_cert.get("key_path") %}
  {%- if not key_path and cert_storage_type == "local_files" %}
    {%- set key_path = cert_storage.get("key") %}
  {%- endif %}

  {%- set cert_cn = client_cert.get("cn", "salt-incus-client") %}
  {%- set cert_days = client_cert.get("days", 3650) %}
  {%- set cert_curve = client_cert.get("curve", "P-384") %}

  {%- if cert_storage_type != "local_files" %}
incus-client-certificates-storage-type-error:
  test.fail_without_changes:
    - name: >
        incus.client_cert.enable=true requires connection.cert_storage.type=local_files.
        Current type: {{ cert_storage_type }}

  {%- elif not cert_path or not key_path %}
incus-client-certificates-paths-error:
  test.fail_without_changes:
    - name: >
        incus.client_cert.enable=true requires both cert and key paths.
        Set incus.client_cert.cert_path/key_path or connection.cert_storage.cert/key.

  {%- else %}
    {%- set cert_dir = salt["file.dirname"](cert_path) %}
    {%- set key_dir = salt["file.dirname"](key_path) %}

incus-client-certificates-openssl:
  pkg.installed:
    - name: openssl

incus-client-certificates-cert-dir:
  file.directory:
    - name: {{ cert_dir | tojson }}
    - mode: "0700"
    - makedirs: true

    {%- if key_dir != cert_dir %}
incus-client-certificates-key-dir:
  file.directory:
    - name: {{ key_dir | tojson }}
    - mode: "0700"
    - makedirs: true
    {%- endif %}

incus-client-certificates-generate:
  cmd.run:
    - name: >
        openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:{{ cert_curve }}
        -nodes -days {{ cert_days | int }}
        -subj {{ ("/CN=" ~ cert_cn) | tojson }}
        -keyout {{ key_path | tojson }}
        -out {{ cert_path | tojson }}
    - unless: test -s {{ cert_path | tojson }} && test -s {{ key_path | tojson }}
    - require:
      - pkg: incus-client-certificates-openssl
      - file: incus-client-certificates-cert-dir
      {%- if key_dir != cert_dir %}
      - file: incus-client-certificates-key-dir
      {%- endif %}

incus-client-certificates-permissions:
  cmd.run:
    - name: chmod 0600 {{ key_path | tojson }} && chmod 0644 {{ cert_path | tojson }}
    - onlyif: test -s {{ cert_path | tojson }} && test -s {{ key_path | tojson }}
    - unless: test "$(stat -c '%a' {{ key_path | tojson }})" = "600" && test "$(stat -c '%a' {{ cert_path | tojson }})" = "644"
    - require:
      - cmd: incus-client-certificates-generate

  {%- endif %}
{%- endif %}
