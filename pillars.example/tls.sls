incus:
  api_client:
    enabled: true

    # 1) Local writable storage for `incus.tls-generate`
    generate_storage:
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key

    # 2) Read-only storage for `incus.tls` trust import
    import_storage:
      cert: salt://incus/pki/client.crt
      key: salt://incus/pki/client.key

    generate:
      cn: salt-cloud
      days: 3650

    # Whether to register the certificate as restricted in Incus trust store.
    restricted: false

    # 3) Storage for salt-cloud / HTTPS execution client
    salt_cloud_storage:
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key

  # salt-cloud / execution-module HTTPS connection should point
  # to the salt_cloud_storage material.
  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key
      verify: true
