"""
Salt state module for managing Incus API client TLS certificates.
"""

import logging

log = logging.getLogger(__name__)

__virtualname__ = "incus_pki"


def __virtual__():
    if "incus_pki.generate_keypair" in __salt__:
        return __virtualname__
    return (False, "incus_pki execution module is not available")


def _normalize_fingerprint(value):
    if value is None:
        return ""
    return str(value).replace(":", "").strip().lower()


def _get_trust_entry_from_storage(storage=None):
    cert_fp = __salt__["incus_pki.cert_fingerprint"](storage=storage)
    if not cert_fp.get("success"):
        return None, None, cert_fp.get("comment") or cert_fp.get("error") or "Failed to calculate fingerprint"

    fingerprint = cert_fp.get("fingerprint")
    trust_result = __salt__["incus.trust_list"]()
    if not trust_result.get("success"):
        return None, fingerprint, trust_result.get("error", "Failed to query Incus trust store")

    for item in trust_result.get("certificates", []) or []:
        if not isinstance(item, dict):
            continue
        if _normalize_fingerprint(item.get("fingerprint")) == _normalize_fingerprint(fingerprint):
            return item, fingerprint, None
    return None, fingerprint, None


def keypair_present(name, storage=None, generate=None, force=False):
    """
    Ensure API client keypair exists in configured storage.
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    cert_result = __salt__["incus_pki.cert_get"](storage=storage)
    key_result = __salt__["incus_pki.key_get"](storage=storage)

    if cert_result.get("success") and key_result.get("success") and not force:
        ret["comment"] = "TLS keypair already present in storage"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = "TLS keypair would be generated"
        return ret

    generate = generate or {}
    if not isinstance(generate, dict):
        generate = {}

    gen_result = __salt__["incus_pki.generate_keypair"](
        cn=generate.get("cn"),
        days=generate.get("days"),
        storage=storage,
        force=force,
    )

    if not gen_result.get("success"):
        ret["result"] = False
        ret["comment"] = gen_result.get("comment") or gen_result.get("error") or "Failed to generate TLS keypair"
        return ret

    ret["comment"] = gen_result.get("comment", "TLS keypair is present")
    if gen_result.get("changed"):
        ret["changes"] = {
            "keypair": {
                "old": None,
                "new": gen_result.get("fingerprint", "generated"),
            }
        }
    return ret


def trust_present(name, storage=None, restricted=False):
    """
    Ensure certificate from storage is present in Incus trust store.
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    cert_result = __salt__["incus_pki.cert_get"](storage=storage)
    if not cert_result.get("success"):
        ret["result"] = False
        ret["comment"] = cert_result.get("comment", "Certificate not found in storage")
        return ret

    existing, fingerprint, error = _get_trust_entry_from_storage(storage=storage)
    if error:
        ret["result"] = False
        ret["comment"] = error
        return ret

    desired_restricted = bool(restricted)
    if existing:
        current_name = existing.get("name")
        current_restricted = bool(existing.get("restricted", False))

        if current_name != name or current_restricted != desired_restricted:
            if __opts__.get("test"):
                ret["result"] = None
                ret["comment"] = "Certificate trust entry would be recreated"
                return ret

            sync_result = __salt__["incus_pki.trust_add_from_storage"](
                name=name,
                storage=storage,
                restricted=restricted,
            )
            if not sync_result.get("success"):
                ret["result"] = False
                ret["comment"] = sync_result.get("comment", "Failed to recreate trust entry")
                return ret

            if sync_result.get("changed"):
                ret["changes"] = {
                    "trust": {
                        "old": {
                            "name": current_name,
                            "restricted": current_restricted,
                        },
                        "new": {
                            "name": name,
                            "restricted": desired_restricted,
                        },
                    }
                }
            ret["comment"] = sync_result.get("comment", "Certificate trust entry recreated")
            return ret

        ret["comment"] = "Certificate already present in trust store"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = "Certificate would be added to trust store"
        return ret

    add_result = __salt__["incus_pki.trust_add_from_storage"](
        name=name,
        storage=storage,
        restricted=restricted,
    )
    if not add_result.get("success"):
        ret["result"] = False
        ret["comment"] = add_result.get("comment", "Failed to add certificate to trust store")
        return ret

    if add_result.get("changed"):
        ret["changes"] = {
            "trust": {
                "old": None,
                "new": fingerprint or add_result.get("fingerprint"),
            }
        }
    ret["comment"] = add_result.get("comment", "Certificate added to trust store")
    return ret


def trust_absent(name, storage=None):
    """
    Ensure certificate from storage is absent in Incus trust store.
    """
    ret = {
        "name": name,
        "result": True,
        "changes": {},
        "comment": "",
    }

    cert_result = __salt__["incus_pki.cert_get"](storage=storage)
    if not cert_result.get("success"):
        ret["result"] = False
        ret["comment"] = cert_result.get("comment", "Certificate not found in storage")
        return ret

    existing, fingerprint, error = _get_trust_entry_from_storage(storage=storage)
    if error:
        ret["result"] = False
        ret["comment"] = error
        return ret

    if not existing:
        ret["comment"] = "Certificate already absent from trust store"
        return ret

    if __opts__.get("test"):
        ret["result"] = None
        ret["comment"] = "Certificate would be removed from trust store"
        return ret

    remove_result = __salt__["incus_pki.trust_remove_from_storage"](storage=storage)
    if not remove_result.get("success"):
        ret["result"] = False
        ret["comment"] = remove_result.get("comment", "Failed to remove certificate from trust store")
        return ret

    if remove_result.get("changed"):
        ret["changes"] = {
            "trust": {
                "old": fingerprint or remove_result.get("fingerprint"),
                "new": None,
            }
        }
    ret["comment"] = remove_result.get("comment", "Certificate removed from trust store")
    return ret
