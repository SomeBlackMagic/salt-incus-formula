import os
import sys
import unittest
from unittest.mock import MagicMock


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import _states.incus_pki as incus_pki_state


class TestIncusPkiState(unittest.TestCase):
    def setUp(self):
        self._orig_salt = getattr(incus_pki_state, "__salt__", {})
        self._orig_opts = getattr(incus_pki_state, "__opts__", {})
        incus_pki_state.__salt__ = {}
        incus_pki_state.__opts__ = {"test": False}

    def tearDown(self):
        incus_pki_state.__salt__ = self._orig_salt
        incus_pki_state.__opts__ = self._orig_opts

    def test_keypair_present_noop_when_pair_exists(self):
        incus_pki_state.__salt__ = {
            "incus_pki.cert_get": MagicMock(return_value={"success": True, "cert": "CERT"}),
            "incus_pki.key_get": MagicMock(return_value={"success": True, "key": "KEY"}),
            "incus_pki.generate_keypair": MagicMock(),
        }

        ret = incus_pki_state.keypair_present("incus-api-client")

        self.assertTrue(ret["result"])
        self.assertEqual(ret["changes"], {})
        self.assertIn("already present", ret["comment"])
        incus_pki_state.__salt__["incus_pki.generate_keypair"].assert_not_called()

    def test_trust_present_test_mode_reports_recreate(self):
        incus_pki_state.__opts__["test"] = True
        incus_pki_state.__salt__ = {
            "incus_pki.cert_get": MagicMock(return_value={"success": True, "cert": "CERT"}),
            "incus_pki.cert_fingerprint": MagicMock(return_value={"success": True, "fingerprint": "abc123"}),
            "incus.trust_list": MagicMock(
                return_value={
                    "success": True,
                    "certificates": [
                        {"fingerprint": "abc123", "name": "old-name", "restricted": False}
                    ],
                }
            ),
            "incus_pki.trust_add_from_storage": MagicMock(),
        }

        ret = incus_pki_state.trust_present("salt-cloud", restricted=True)

        self.assertIsNone(ret["result"])
        self.assertEqual(ret["changes"], {})
        self.assertIn("would be recreated", ret["comment"])
        incus_pki_state.__salt__["incus_pki.trust_add_from_storage"].assert_not_called()

    def test_trust_present_recreates_when_drift_detected(self):
        incus_pki_state.__salt__ = {
            "incus_pki.cert_get": MagicMock(return_value={"success": True, "cert": "CERT"}),
            "incus_pki.cert_fingerprint": MagicMock(return_value={"success": True, "fingerprint": "abc123"}),
            "incus.trust_list": MagicMock(
                return_value={
                    "success": True,
                    "certificates": [
                        {"fingerprint": "abc123", "name": "old-name", "restricted": False}
                    ],
                }
            ),
            "incus_pki.trust_add_from_storage": MagicMock(
                return_value={"success": True, "changed": True, "comment": "recreated"}
            ),
        }

        ret = incus_pki_state.trust_present("salt-cloud", restricted=True)

        self.assertTrue(ret["result"])
        self.assertIn("trust", ret["changes"])
        self.assertEqual(ret["changes"]["trust"]["old"]["name"], "old-name")
        self.assertEqual(ret["changes"]["trust"]["new"]["name"], "salt-cloud")
        incus_pki_state.__salt__["incus_pki.trust_add_from_storage"].assert_called_once()

    def test_trust_absent_test_mode_reports_remove(self):
        incus_pki_state.__opts__["test"] = True
        incus_pki_state.__salt__ = {
            "incus_pki.cert_get": MagicMock(return_value={"success": True, "cert": "CERT"}),
            "incus_pki.cert_fingerprint": MagicMock(return_value={"success": True, "fingerprint": "abc123"}),
            "incus.trust_list": MagicMock(
                return_value={
                    "success": True,
                    "certificates": [{"fingerprint": "abc123", "name": "salt-cloud", "restricted": False}],
                }
            ),
            "incus_pki.trust_remove_from_storage": MagicMock(),
        }

        ret = incus_pki_state.trust_absent("salt-cloud")

        self.assertIsNone(ret["result"])
        self.assertEqual(ret["changes"], {})
        self.assertIn("would be removed", ret["comment"])
        incus_pki_state.__salt__["incus_pki.trust_remove_from_storage"].assert_not_called()
