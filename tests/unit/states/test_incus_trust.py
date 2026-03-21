import os
import tempfile
import unittest
from unittest.mock import MagicMock

import _states.incus as incus_state


def _ok_cmd_run_all(cmd, python_shell=True):
    if "-fingerprint -sha256" in cmd:
        return {"retcode": 0, "stdout": "sha256 Fingerprint=AA:BB"}
    return {"retcode": 0, "stdout": ""}


class TestClientCertificateTrusted(unittest.TestCase):
    def setUp(self):
        self._orig_salt = getattr(incus_state, "__salt__", {})
        self._orig_opts = getattr(incus_state, "__opts__", {})
        incus_state.__opts__ = {"test": False}
        incus_state.__salt__ = {
            "cmd.run_all": _ok_cmd_run_all,
            "incus.certificate_list": MagicMock(return_value={"success": True, "certificates": []}),
            "incus.certificate_add": MagicMock(return_value={"success": True}),
            "incus.certificate_remove": MagicMock(return_value={"success": True}),
        }

    def tearDown(self):
        incus_state.__salt__ = self._orig_salt
        incus_state.__opts__ = self._orig_opts

    def test_absent_missing_cert_warns_and_noop(self):
        missing_path = "/tmp/does-not-exist-incus-client.crt"
        if os.path.exists(missing_path):
            os.unlink(missing_path)

        ret = incus_state.client_certificate_trusted(
            name="salt-cloud",
            cert_path=missing_path,
            ensure="absent",
        )

        self.assertTrue(ret["result"])
        self.assertEqual(ret["changes"], {})
        self.assertTrue(ret.get("warnings"))
        self.assertIn("Skipping trust removal", ret["comment"])

    def test_present_fails_on_name_conflict_with_different_fingerprint(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as fp:
            fp.write("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n")
            cert_path = fp.name

        try:
            incus_state.__salt__["incus.certificate_list"] = MagicMock(
                return_value={
                    "success": True,
                    "certificates": [
                        {"name": "salt-cloud", "fingerprint": "CC:DD"},
                    ],
                }
            )

            ret = incus_state.client_certificate_trusted(
                name="salt-cloud",
                cert_path=cert_path,
                ensure="present",
            )

            self.assertFalse(ret["result"])
            self.assertIn("Certificate name conflict", ret["comment"])
        finally:
            os.unlink(cert_path)

    def test_present_in_test_mode_reports_planned_add(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as fp:
            fp.write("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n")
            cert_path = fp.name

        try:
            incus_state.__opts__ = {"test": True}
            incus_state.__salt__["incus.certificate_list"] = MagicMock(
                return_value={"success": True, "certificates": []}
            )

            ret = incus_state.client_certificate_trusted(
                name="salt-cloud",
                cert_path=cert_path,
                ensure="present",
            )

            self.assertIsNone(ret["result"])
            self.assertIn("would be added", ret["comment"])
            self.assertEqual(
                ret["changes"]["certificate"]["new"]["fingerprint"],
                "aabb",
            )
            incus_state.__salt__["incus.certificate_add"].assert_not_called()
        finally:
            os.unlink(cert_path)

    def test_absent_removes_existing_fingerprint(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False) as fp:
            fp.write("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n")
            cert_path = fp.name

        try:
            remove_mock = MagicMock(return_value={"success": True})
            incus_state.__salt__["incus.certificate_list"] = MagicMock(
                return_value={
                    "success": True,
                    "certificates": [
                        {"name": "salt-cloud", "fingerprint": "AA:BB"},
                    ],
                }
            )
            incus_state.__salt__["incus.certificate_remove"] = remove_mock

            ret = incus_state.client_certificate_trusted(
                name="salt-cloud",
                cert_path=cert_path,
                ensure="absent",
            )

            self.assertTrue(ret["result"])
            self.assertIn("removed", ret["comment"])
            self.assertEqual(ret["changes"]["certificate"]["new"], None)
            remove_mock.assert_called_once_with("aabb")
        finally:
            os.unlink(cert_path)

