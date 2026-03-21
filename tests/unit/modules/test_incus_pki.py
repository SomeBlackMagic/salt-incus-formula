import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import _modules.incus_pki as incus_pki


@unittest.skipUnless(incus_pki.HAS_CRYPTOGRAPHY, "python-cryptography is required for PKI tests")
class TestIncusPkiExecution(unittest.TestCase):
    def setUp(self):
        self._orig_salt = getattr(incus_pki, "__salt__", {})
        self._orig_utils = getattr(incus_pki, "__utils__", {})
        self._orig_opts = getattr(incus_pki, "__opts__", {})

        incus_pki.__salt__ = {"config.get": MagicMock(return_value={})}
        incus_pki.__utils__ = {}
        incus_pki.__opts__ = {}

    def tearDown(self):
        incus_pki.__salt__ = self._orig_salt
        incus_pki.__utils__ = self._orig_utils
        incus_pki.__opts__ = self._orig_opts

    def test_generate_keypair_writes_local_files_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cert_path = os.path.join(tmp_dir, "client.crt")
            key_path = os.path.join(tmp_dir, "client.key")
            storage = {"type": "local_files", "cert": cert_path, "key": key_path}

            result = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)

            self.assertTrue(result["success"])
            self.assertTrue(result["changed"])
            self.assertTrue(os.path.exists(cert_path))
            self.assertTrue(os.path.exists(key_path))
            self.assertEqual(os.stat(cert_path).st_mode & 0o777, 0o644)
            self.assertEqual(os.stat(key_path).st_mode & 0o777, 0o600)
            self.assertTrue(result.get("fingerprint"))

    def test_generate_keypair_is_idempotent_when_pair_exists(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cert_path = os.path.join(tmp_dir, "client.crt")
            key_path = os.path.join(tmp_dir, "client.key")
            storage = {"type": "local_files", "cert": cert_path, "key": key_path}

            first = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)
            second = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)

            self.assertTrue(first["success"])
            self.assertTrue(first["changed"])
            self.assertTrue(second["success"])
            self.assertFalse(second["changed"])

    def test_trust_add_from_storage_adds_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cert_path = os.path.join(tmp_dir, "client.crt")
            key_path = os.path.join(tmp_dir, "client.key")
            storage = {"type": "local_files", "cert": cert_path, "key": key_path}

            gen = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)
            self.assertTrue(gen["success"])

            trust_list = MagicMock(return_value={"success": True, "certificates": []})
            trust_add = MagicMock(return_value={"success": True})
            trust_remove = MagicMock(return_value={"success": True})
            incus_pki.__salt__.update(
                {
                    "incus.trust_list": trust_list,
                    "incus.trust_add": trust_add,
                    "incus.trust_remove": trust_remove,
                }
            )

            result = incus_pki.trust_add_from_storage(
                name="salt-cloud",
                storage=storage,
                restricted=False,
            )

            self.assertTrue(result["success"])
            self.assertTrue(result["changed"])
            self.assertEqual(result.get("action"), "added")
            trust_add.assert_called_once()
            trust_remove.assert_not_called()

    def test_trust_add_from_storage_recreates_on_drift(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cert_path = os.path.join(tmp_dir, "client.crt")
            key_path = os.path.join(tmp_dir, "client.key")
            storage = {"type": "local_files", "cert": cert_path, "key": key_path}

            gen = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)
            self.assertTrue(gen["success"])
            fingerprint = gen["fingerprint"]

            trust_list = MagicMock(
                return_value={
                    "success": True,
                    "certificates": [
                        {
                            "fingerprint": fingerprint,
                            "name": "old-name",
                            "restricted": False,
                        }
                    ],
                }
            )
            trust_add = MagicMock(return_value={"success": True})
            trust_remove = MagicMock(return_value={"success": True})
            incus_pki.__salt__.update(
                {
                    "incus.trust_list": trust_list,
                    "incus.trust_add": trust_add,
                    "incus.trust_remove": trust_remove,
                }
            )

            result = incus_pki.trust_add_from_storage(
                name="salt-cloud",
                storage=storage,
                restricted=True,
            )

            self.assertTrue(result["success"])
            self.assertTrue(result["changed"])
            self.assertEqual(result.get("action"), "recreated")
            trust_remove.assert_called_once_with(fingerprint)
            trust_add.assert_called_once()

    def test_trust_remove_from_storage_is_noop_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            cert_path = os.path.join(tmp_dir, "client.crt")
            key_path = os.path.join(tmp_dir, "client.key")
            storage = {"type": "local_files", "cert": cert_path, "key": key_path}

            gen = incus_pki.generate_keypair(cn="salt-cloud", days=30, storage=storage, force=False)
            self.assertTrue(gen["success"])

            trust_list = MagicMock(return_value={"success": True, "certificates": []})
            trust_remove = MagicMock(return_value={"success": True})
            incus_pki.__salt__.update(
                {
                    "incus.trust_list": trust_list,
                    "incus.trust_remove": trust_remove,
                }
            )

            result = incus_pki.trust_remove_from_storage(storage=storage)

            self.assertTrue(result["success"])
            self.assertFalse(result["changed"])
            trust_remove.assert_not_called()
