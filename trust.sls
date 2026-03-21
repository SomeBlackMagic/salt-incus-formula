{%- from tpldir ~ "/map.jinja" import incus with context %}

include:
  - .install
  - .certificates

{%- set api_trust = incus.get("api_client_trust") | default({}, true) %}
{%- set api_trust_enable = api_trust.get("enable", false) %}

{%- if api_trust_enable %}
  {%- set incus_enable = incus.get("enable", false) %}
  {%- set ensure = api_trust.get("ensure", "present") %}
  {%- set trust_name = api_trust.get("name", "salt-cloud") %}
  {%- set cert_path = api_trust.get("cert_path", "/etc/salt/pki/incus/client.crt") %}
  {%- set cert_sdb = api_trust.get("cert_sdb") %}
  {%- set cert_sdb_defined = cert_sdb is not none %}
  {%- set cert_contents = api_trust.get("cert_contents") %}
  {%- set cert_source = api_trust.get("cert_source") %}

  {%- if not incus_enable %}
incus-api-client-trust-disabled-incus-error:
  test.fail_without_changes:
    - name: >-
        incus.api_client_trust.enable=true requires incus.enable=true.

  {%- else %}
    {%- set cert_dir = salt["file.dirname"](cert_path) %}

incus-api-client-trust-cert-dir:
  file.directory:
    - name: {{ cert_dir | tojson }}
    - mode: "0700"
    - makedirs: true

incus-api-client-trust-openssl:
  pkg.installed:
    - name: openssl

    {%- if cert_sdb_defined %}
      {%- if not cert_sdb %}
incus-api-client-trust-certificate:
  test.fail_without_changes:
    - name: >-
        incus.api_client_trust.cert_sdb is set but empty.
      {%- else %}
      {%- set resolved_cert_sdb = salt["sdb.get"](cert_sdb) %}
      {%- if not resolved_cert_sdb %}
incus-api-client-trust-certificate:
  test.fail_without_changes:
    - name: >-
        incus.api_client_trust.cert_sdb is set but returned an empty value: {{ cert_sdb }}
      {%- else %}
incus-api-client-trust-certificate:
  file.managed:
    - name: {{ cert_path | tojson }}
    - user: root
    - group: root
    - mode: "0644"
    - makedirs: true
    - show_changes: false
    - contents: |
{{ resolved_cert_sdb | indent(8, true) }}
    - require:
      - file: incus-api-client-trust-cert-dir
      {%- endif %}
      {%- endif %}
    {%- elif cert_contents %}
incus-api-client-trust-certificate:
  file.managed:
    - name: {{ cert_path | tojson }}
    - user: root
    - group: root
    - mode: "0644"
    - makedirs: true
    - show_changes: false
    - contents: |
{{ cert_contents | indent(8, true) }}
    - require:
      - file: incus-api-client-trust-cert-dir
    {%- elif cert_source %}
incus-api-client-trust-certificate:
  file.managed:
    - name: {{ cert_path | tojson }}
    - source: {{ cert_source | tojson }}
    - user: root
    - group: root
    - mode: "0644"
    - makedirs: true
    - show_changes: false
    - require:
      - file: incus-api-client-trust-cert-dir
    {%- endif %}

incus-api-client-trust-state:
  incus.client_certificate_trusted:
    - name: {{ trust_name | tojson }}
    - ensure: {{ ensure | tojson }}
    - cert_path: {{ cert_path | tojson }}
    - require:
      - service: incus-service
      - pkg: incus-api-client-trust-openssl
      - file: incus-api-client-trust-cert-dir
      {%- if cert_sdb_defined or cert_contents or cert_source %}
      - file: incus-api-client-trust-certificate
      {%- endif %}
  {%- endif %}
{%- endif %}
