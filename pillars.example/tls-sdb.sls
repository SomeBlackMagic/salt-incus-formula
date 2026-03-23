incus:
  enable: true

  api_client:
    enabled: true
    # 1) Local writable storage for `incus.tls-generate`
    generate_storage:
      cert: /etc/salt/pki/incus/client.crt
      key: /etc/salt/pki/incus/client.key

    # 2) Import storage for `incus.tls` (shared backend example)
    import_storage:
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key

    generate:
      cn: salt-cloud
      days: 3650

    # Whether to register the certificate as restricted in Incus trust store.
    restricted: false

    # 3) salt-cloud / HTTPS client storage
    salt_cloud_storage:
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key

  # HTTPS API access uses the same cert/key from SDB.
  connection:
    type: https
    url: https://incus.example.com:8443
    cert_storage:
      cert: sdb://vault/incus/client_cert
      key: sdb://vault/incus/client_key
      verify: sdb://vault/incus/ca_cert
