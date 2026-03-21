"""
Salt execution module for managing Incus API client certificates.

This module provides:
- keypair generation (EC P-384 self-signed certificate)
- storage helpers for local filesystem and Salt SDB
- trust store synchronization helpers built on top of incus.trust_* functions
"""

import datetime
import hashlib
import logging
import os

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    HAS_CRYPTOGRAPHY = True
except Exception:
    HAS_CRYPTOGRAPHY = False


log = logging.getLogger(__name__)

__virtualname__ = "incus_pki"

DEFAULT_STORAGE = {
    "type": "local_files",
    "cert": "/etc/salt/pki/incus/client.crt",
    "key": "/etc/salt/pki/incus/client.key",
}


def __virtual__():
    if not HAS_CRYPTOGRAPHY:
        return False, "python-cryptography is required"
    return __virtualname__


def _api_client_cfg():
    cfg_get = __salt__.get("config.get", lambda *_: {})
    incus_cfg = cfg_get("incus", {}) or {}
    if not isinstance(incus_cfg, dict):
        return {}
    api_client = incus_cfg.get("api_client", {}) or {}
    return api_client if isinstance(api_client, dict) else {}


def _normalize_storage(storage=None):
    if storage is None:
        storage = _api_client_cfg().get("storage", {}) or {}
    if not isinstance(storage, dict):
        raise ValueError("storage must be a mapping")

    normalized = dict(DEFAULT_STORAGE)
    normalized.update(storage)

    stype = normalized.get("type", "local_files")
    if stype not in ("local_files", "sdb"):
        raise ValueError("storage.type must be 'local_files' or 'sdb'")

    cert = normalized.get("cert")
    key = normalized.get("key")
    if not cert or not key:
        raise ValueError("storage.cert and storage.key are required")

    return {
        "type": stype,
        "cert": cert,
        "key": key,
    }


def _normalize_generate(cn=None, days=None):
    generate_cfg = _api_client_cfg().get("generate", {}) or {}
    if not isinstance(generate_cfg, dict):
        generate_cfg = {}

    cert_cn = cn or generate_cfg.get("cn") or "salt-cloud"
    cert_days = days if days is not None else generate_cfg.get("days", 3650)

    try:
        cert_days = int(cert_days)
    except (TypeError, ValueError):
        raise ValueError("days must be an integer")

    if cert_days <= 0:
        raise ValueError("days must be greater than 0")

    return cert_cn, cert_days


def _sdb_get(uri):
    utils = globals().get("__utils__", {}) or {}

    for util_name in ("sdb.get", "sdb.sdb_get"):
        getter = utils.get(util_name) if hasattr(utils, "get") else None
        if callable(getter):
            return getter(uri)

    try:
        import salt.utils.sdb as salt_sdb
    except Exception as exc:
        raise ValueError(f"Failed to import salt.utils.sdb for URI '{uri}': {exc}") from exc

    opts = globals().get("__opts__", {}) or {}
    try:
        return salt_sdb.sdb_get(uri, opts, utils)
    except TypeError:
        return salt_sdb.sdb_get(uri, opts)
    except Exception as exc:
        raise ValueError(f"Failed to resolve SDB URI '{uri}': {exc}") from exc


def _sdb_set(uri, value):
    utils = globals().get("__utils__", {}) or {}

    for util_name in ("sdb.set", "sdb.sdb_set"):
        setter = utils.get(util_name) if hasattr(utils, "get") else None
        if callable(setter):
            result = setter(uri, value)
            if result is False:
                raise ValueError(f"Failed to write SDB URI '{uri}'")
            return result

    try:
        import salt.utils.sdb as salt_sdb
    except Exception as exc:
        raise ValueError(f"Failed to import salt.utils.sdb for URI '{uri}': {exc}") from exc

    opts = globals().get("__opts__", {}) or {}
    try:
        result = salt_sdb.sdb_set(uri, value, opts, utils)
    except TypeError:
        result = salt_sdb.sdb_set(uri, value, opts)
    except Exception as exc:
        raise ValueError(f"Failed to write SDB URI '{uri}': {exc}") from exc

    if result is False:
        raise ValueError(f"Failed to write SDB URI '{uri}'")
    return result


def _storage_read(storage, key):
    stype = storage.get("type", "local_files")
    target = storage.get(key)

    if stype == "local_files":
        if not target or not os.path.exists(target):
            return None
        with open(target, "r", encoding="utf-8") as fp:
            return fp.read()

    if not isinstance(target, str) or not target.startswith("sdb://"):
        raise ValueError(f"storage.{key} must be an sdb:// URI for type=sdb")
    value = _sdb_get(target)
    if value in (None, ""):
        return None
    return str(value)


def _storage_write(storage, key, value, mode):
    stype = storage.get("type", "local_files")
    target = storage.get(key)

    if stype == "local_files":
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)
        with open(target, "w", encoding="utf-8") as fp:
            fp.write(value)
        os.chmod(target, mode)
        return

    if not isinstance(target, str) or not target.startswith("sdb://"):
        raise ValueError(f"storage.{key} must be an sdb:// URI for type=sdb")
    _sdb_set(target, value)


def _storage_write_pair(storage, cert_pem, key_pem):
    _storage_write(storage, "cert", cert_pem, 0o644)
    _storage_write(storage, "key", key_pem, 0o600)


def _generate_keypair(cn, days):
    private_key = ec.generate_private_key(ec.SECP384R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key=private_key, algorithm=hashes.SHA384())
    )

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    return cert_pem, key_pem


def _fingerprint_from_cert(cert_pem):
    cert_obj = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    cert_der = cert_obj.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(cert_der).hexdigest()


def _normalize_fingerprint(value):
    if value is None:
        return ""
    return str(value).replace(":", "").strip().lower()


def _find_trust_entry(certificates, fingerprint):
    normalized = _normalize_fingerprint(fingerprint)
    for item in certificates or []:
        if not isinstance(item, dict):
            continue
        current = _normalize_fingerprint(item.get("fingerprint"))
        if current == normalized:
            return item
    return None


def cert_get(storage=None):
    """
    Read certificate from configured storage.
    """
    try:
        normalized_storage = _normalize_storage(storage)
        cert_pem = _storage_read(normalized_storage, "cert")
        if not cert_pem:
            return {
                "success": False,
                "changed": False,
                "comment": "Certificate not found in storage",
                "error": "certificate_not_found",
            }
        return {
            "success": True,
            "changed": False,
            "comment": "Certificate loaded from storage",
            "cert": cert_pem,
        }
    except Exception as exc:
        log.error("Failed to read certificate from storage: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to read certificate from storage: {exc}",
            "error": str(exc),
        }


def key_get(storage=None):
    """
    Read private key from configured storage.
    """
    try:
        normalized_storage = _normalize_storage(storage)
        key_pem = _storage_read(normalized_storage, "key")
        if not key_pem:
            return {
                "success": False,
                "changed": False,
                "comment": "Private key not found in storage",
                "error": "key_not_found",
            }
        return {
            "success": True,
            "changed": False,
            "comment": "Private key loaded from storage",
            "key": key_pem,
        }
    except Exception as exc:
        log.error("Failed to read private key from storage: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to read private key from storage: {exc}",
            "error": str(exc),
        }


def cert_fingerprint(cert_pem=None, storage=None):
    """
    Calculate SHA-256 fingerprint from certificate PEM.
    """
    try:
        cert_value = cert_pem
        if cert_value is None:
            cert_result = cert_get(storage=storage)
            if not cert_result.get("success"):
                return cert_result
            cert_value = cert_result.get("cert")

        fingerprint = _fingerprint_from_cert(cert_value)
        return {
            "success": True,
            "changed": False,
            "comment": "Certificate fingerprint calculated",
            "fingerprint": fingerprint,
        }
    except Exception as exc:
        log.error("Failed to calculate certificate fingerprint: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to calculate certificate fingerprint: {exc}",
            "error": str(exc),
        }


def generate_keypair(cn=None, days=None, storage=None, force=False):
    """
    Generate an EC P-384 client keypair and save it to storage.
    """
    try:
        normalized_storage = _normalize_storage(storage)
        cert_cn, cert_days = _normalize_generate(cn=cn, days=days)

        existing_cert = _storage_read(normalized_storage, "cert")
        existing_key = _storage_read(normalized_storage, "key")

        if existing_cert and existing_key and not force:
            log.info("TLS keypair already exists in storage, skipping generation")
            return {
                "success": True,
                "changed": False,
                "comment": "Certificate and key already exist in storage",
            }

        cert_pem, key_pem = _generate_keypair(cert_cn, cert_days)
        _storage_write_pair(normalized_storage, cert_pem, key_pem)
        fingerprint = _fingerprint_from_cert(cert_pem)

        log.info("Generated new TLS keypair for CN '%s'", cert_cn)
        return {
            "success": True,
            "changed": True,
            "comment": "TLS keypair generated and stored",
            "fingerprint": fingerprint,
        }
    except Exception as exc:
        log.error("Failed to generate TLS keypair: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to generate TLS keypair: {exc}",
            "error": str(exc),
        }


def trust_present_check(cert_pem=None, storage=None):
    """
    Check whether certificate fingerprint is present in Incus trust store.

    Returns:
        True  - certificate present
        False - certificate missing
        None  - Incus trust API error
    """
    try:
        cert_value = cert_pem
        if cert_value is None:
            cert_result = cert_get(storage=storage)
            if not cert_result.get("success"):
                return False
            cert_value = cert_result.get("cert")

        fingerprint = _fingerprint_from_cert(cert_value)
        trust_result = __salt__["incus.trust_list"]()
        if not trust_result.get("success"):
            return None

        certificates = trust_result.get("certificates", [])
        return _find_trust_entry(certificates, fingerprint) is not None
    except Exception as exc:
        log.error("Failed to check trust presence: %s", exc)
        return None


def trust_add_from_storage(name=None, storage=None, restricted=False):
    """
    Ensure certificate from storage exists in Incus trust store.

    If fingerprint exists but trust name/restricted flags drift, certificate is
    recreated (remove + add).
    """
    try:
        cert_result = cert_get(storage=storage)
        if not cert_result.get("success"):
            return cert_result
        cert_pem = cert_result.get("cert")

        fp_result = cert_fingerprint(cert_pem=cert_pem)
        if not fp_result.get("success"):
            return fp_result
        fingerprint = fp_result.get("fingerprint")

        trust_result = __salt__["incus.trust_list"]()
        if not trust_result.get("success"):
            error = trust_result.get("error", "Failed to list trust store")
            return {
                "success": False,
                "changed": False,
                "comment": f"Failed to list trust store: {error}",
                "error": error,
            }

        certificates = trust_result.get("certificates", [])
        existing_entry = _find_trust_entry(certificates, fingerprint)
        desired_name = name if name is not None else _api_client_cfg().get("trust_name", "salt-cloud")
        desired_restricted = bool(restricted)

        if existing_entry:
            current_name = existing_entry.get("name")
            current_restricted = bool(existing_entry.get("restricted", False))

            if current_name != desired_name or current_restricted != desired_restricted:
                remove_result = __salt__["incus.trust_remove"](fingerprint)
                if not remove_result.get("success"):
                    error = remove_result.get("error", "Failed to remove trust entry")
                    return {
                        "success": False,
                        "changed": False,
                        "comment": f"Failed to recreate trust entry (remove step): {error}",
                        "error": error,
                        "fingerprint": fingerprint,
                    }

                add_result = __salt__["incus.trust_add"](cert_pem, desired_name, desired_restricted)
                if not add_result.get("success"):
                    error = add_result.get("error", "Failed to add trust entry")
                    return {
                        "success": False,
                        "changed": False,
                        "comment": f"Failed to recreate trust entry (add step): {error}",
                        "error": error,
                        "fingerprint": fingerprint,
                    }

                log.info("Recreated trust entry for fingerprint %s", fingerprint)
                return {
                    "success": True,
                    "changed": True,
                    "comment": "Trust entry recreated to match desired name/restricted",
                    "fingerprint": fingerprint,
                    "action": "recreated",
                }

            return {
                "success": True,
                "changed": False,
                "comment": "Certificate already present in trust store",
                "fingerprint": fingerprint,
                "action": "present",
            }

        add_result = __salt__["incus.trust_add"](cert_pem, desired_name, desired_restricted)
        if not add_result.get("success"):
            error = add_result.get("error", "Failed to add trust entry")
            return {
                "success": False,
                "changed": False,
                "comment": f"Failed to add trust entry: {error}",
                "error": error,
                "fingerprint": fingerprint,
            }

        log.info("Added trust entry for fingerprint %s", fingerprint)
        return {
            "success": True,
            "changed": True,
            "comment": "Certificate added to trust store",
            "fingerprint": fingerprint,
            "action": "added",
        }
    except Exception as exc:
        log.error("Failed to ensure trust presence: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to ensure trust presence: {exc}",
            "error": str(exc),
        }


def trust_remove_from_storage(storage=None):
    """
    Remove certificate from Incus trust store by fingerprint derived from storage.
    """
    try:
        cert_result = cert_get(storage=storage)
        if not cert_result.get("success"):
            return cert_result
        cert_pem = cert_result.get("cert")

        fp_result = cert_fingerprint(cert_pem=cert_pem)
        if not fp_result.get("success"):
            return fp_result
        fingerprint = fp_result.get("fingerprint")

        trust_result = __salt__["incus.trust_list"]()
        if not trust_result.get("success"):
            error = trust_result.get("error", "Failed to list trust store")
            return {
                "success": False,
                "changed": False,
                "comment": f"Failed to list trust store: {error}",
                "error": error,
            }

        certificates = trust_result.get("certificates", [])
        existing_entry = _find_trust_entry(certificates, fingerprint)
        if not existing_entry:
            return {
                "success": True,
                "changed": False,
                "comment": "Certificate is already absent from trust store",
                "fingerprint": fingerprint,
            }

        remove_result = __salt__["incus.trust_remove"](fingerprint)
        if not remove_result.get("success"):
            error = remove_result.get("error", "Failed to remove trust entry")
            return {
                "success": False,
                "changed": False,
                "comment": f"Failed to remove trust entry: {error}",
                "error": error,
                "fingerprint": fingerprint,
            }

        log.info("Removed trust entry for fingerprint %s", fingerprint)
        return {
            "success": True,
            "changed": True,
            "comment": "Certificate removed from trust store",
            "fingerprint": fingerprint,
        }
    except Exception as exc:
        log.error("Failed to remove certificate from trust store: %s", exc)
        return {
            "success": False,
            "changed": False,
            "comment": f"Failed to remove certificate from trust store: {exc}",
            "error": str(exc),
        }
