{#-
  Install Incus and its OS-level dependencies.
  Supports both Debian and RedHat families.
  Package lists are defined via map.jinja (defaults + pillar overrides).
-#}
{% from tpldir ~ "/map.jinja" import incus with context %}

{% if incus.enable %}

  {% set os_family = grains.get("os_family") %}
  {% set codename = grains.get("oscodename", "bookworm") %}
  {% set repo = incus.get("repo") | default({}, true) %}
  {% set repo_debian = repo.get("debian") | default({}, true) %}
  {% set repo_redhat = repo.get("redhat") | default({}, true) %}
  {% set pkg = incus.get("pkg") | default({}, true) %}
  {% set service = incus.get("service") | default({}, true) %}
  {% set incus_version = incus.get("version", None) %}
  {% set pkg_name = pkg.get("name", "incus") %}
  {% set db_file = '/var/lib/incus/database/local.db' %}
  {% set trust_store = incus.get("trust_store") | default({}, true) %}
  {% set trust_enable = trust_store.get("enable", false) %}
  {% set trust_sdb = trust_store.get("sdb") %}
  {% set trust_source = trust_store.get("source") %}
  {% set trust_contents = trust_store.get("contents") %}
  {% set trust_target = trust_store.get("target") %}
  {% set trust_update_cmd = trust_store.get("update_cmd") %}

  {% if trust_sdb %}
    {% set trust_contents = salt['sdb.get'](trust_sdb) %}
  {% endif %}

  {% if not trust_target %}
    {% if os_family == "RedHat" %}
      {% set trust_target = "/etc/pki/ca-trust/source/anchors/incus-remote.crt" %}
    {% else %}
      {% set trust_target = "/usr/local/share/ca-certificates/incus-remote.crt" %}
    {% endif %}
  {% endif %}

  {% if not trust_update_cmd %}
    {% if os_family == "RedHat" %}
      {% set trust_update_cmd = "update-ca-trust extract" %}
    {% else %}
      {% set trust_update_cmd = "update-ca-certificates" %}
    {% endif %}
  {% endif %}

  {#- Debian/Ubuntu repository setup -#}
  {% if repo.get("enable") and os_family == "Debian" %}
    {% set arch = repo_debian.get("architecture", "amd64") %}
    {% set repo_channel = repo.get("channel", "stable") %}
    {% set key_url = repo_debian.get("key_url", "https://pkgs.zabbly.com/key.asc") %}

incus-keyring-directory:
  file.directory:
    - name: /etc/apt/keyrings
    - user: root
    - group: root
    - mode: '0755'
    - makedirs: True

incus-repo-key:
  file.managed:
    - name: /etc/apt/keyrings/zabbly.asc
    - source: {{ key_url }}
    - skip_verify: True
    - mode: '0644'
    - user: root
    - group: root
    - require:
      - file: incus-keyring-directory

incus-repo:
  file.managed:
    - name: /etc/apt/sources.list.d/zabbly-incus-{{ repo_channel }}.sources
    - user: root
    - group: root
    - mode: '0644'
    - contents: |
        Enabled: yes
        Types: deb
        URIs: https://pkgs.zabbly.com/incus/{{ repo_channel }}
        Suites: {{ codename }}
        Components: main
        Architectures: {{ arch }}
        Signed-By: /etc/apt/keyrings/zabbly.asc
    - require:
      - file: incus-repo-key
{% endif %}

  {#- RedHat/CentOS/Fedora repository setup -#}
  {% if repo.get("enable") and os_family == "RedHat" %}
  {% set repo_name = repo_redhat.get("name", "incus-stable") %}
  {% set baseurl = repo_redhat.get("baseurl", "https://pkgs.zabbly.com/incus/stable/rpm/$releasever/$basearch") %}
  {% set gpgkey = repo_redhat.get("gpgkey", "https://pkgs.zabbly.com/key.asc") %}
  {% set repo_enabled = repo_redhat.get("enabled", 1) %}
  {% set gpgcheck = repo_redhat.get("gpgcheck", 1) %}

incus-repo:
  pkgrepo.managed:
    - name: {{ repo_name }}
    - humanname: Incus Repository
    - baseurl: {{ baseurl }}
    - gpgkey: {{ gpgkey }}
    - enabled: {{ repo_enabled }}
    - gpgcheck: {{ gpgcheck }}
  {% endif %}

{#- Install main Incus package -#}
incus-package:
  pkg.installed:
    - name: {{ pkg_name }}
    {% if incus_version %}
    - version: {{ incus_version }}
    {% endif %}
    {% if repo.get("enable") %}
    - refresh: True
    {% if os_family == "Debian" %}
    - require:
      - file: incus-repo
    {% elif os_family == "RedHat" %}
    - require:
      - pkgrepo: incus-repo
    {% endif %}
    {% endif %}


incus-service:
  service.running:
    - name: {{ service.get("name", "incus") }}
    - enable: {{ service.get("enable", True) }}
    - require:
      - pkg: incus-package

incus-init:
  cmd.run:
    - name: incus admin init --minimal
    - unless: test -f {{ db_file }}
    - require:
      - service: incus-service

  {% if trust_enable %}
incus-ca-certificates:
  pkg.installed:
    - name: ca-certificates
    - require:
      - pkg: incus-package

  {% if trust_contents %}
incus-trust-certificate:
  file.managed:
    - name: {{ trust_target }}
    - user: root
    - group: root
    - mode: '0644'
    - makedirs: True
    - contents: |
{{ trust_contents | indent(8, true) }}
    - require:
      - pkg: incus-ca-certificates
  {% elif trust_source %}
incus-trust-certificate:
  file.managed:
    - name: {{ trust_target }}
    - source: {{ trust_source | tojson }}
    - user: root
    - group: root
    - mode: '0644'
    - makedirs: True
    - require:
      - pkg: incus-ca-certificates
  {% else %}
incus-trust-certificate-config-error:
  test.fail_without_changes:
    - name: >-
        incus.trust_store.enable=true, but no certificate provided.
        Set one of: incus.trust_store.sdb, incus.trust_store.contents, incus.trust_store.source.
  {% endif %}

  {% if trust_contents or trust_source %}
incus-trust-store-update:
  cmd.run:
    - name: {{ trust_update_cmd | tojson }}
    - onchanges:
      - file: incus-trust-certificate
    - require:
      - file: incus-trust-certificate
  {% endif %}
  {% endif %}

  {#- Install dependencies -#}
  {% if pkg.get("deps") %}
incus-deps:
  pkg.installed:
    - pkgs: {{ pkg.get("deps") | tojson }}
    - require:
      - pkg: incus-package
  {% endif %}

{% endif %}
