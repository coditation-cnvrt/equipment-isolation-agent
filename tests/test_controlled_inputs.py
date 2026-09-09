import copy
from datetime import datetime, timedelta, timezone
import json
import unittest

from equipment_isolation.domain.controlled_inputs import (
    ControlledInputError, approved_fhr, canonical_bytes, content_hash,
    prepare_content, scope_for, utc_timestamp, validate_approval,
)
from tests.test_isolation_standard import _approved_fhr


class ControlledInputDomainTests(unittest.TestCase):
    def test_canonical_golden_vector_and_numeric_equivalence(self):
        value = {"z": [1.0, -0.0, 1e-7], "a": "é"}
        self.assertEqual(canonical_bytes(value), b'{"a":"\xc3\xa9","z":[1,0,0.0000001]}')
        self.assertEqual(content_hash({"a": 1}), "015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862")
        self.assertEqual(content_hash({"a": 1.0}), content_hash({"a": 1}))
        self.assertNotEqual(content_hash([1, 2]), content_hash([2, 1]))

    def test_invalid_json_values_are_rejected_recursively(self):
        for value in (float("nan"), float("inf"), float("-inf"), {1: "bad"}, (1, 2), object(), "\ud800"):
            with self.subTest(value=repr(value)), self.assertRaises(ControlledInputError):
                canonical_bytes({"nested": [value]})

    def test_time_has_explicit_utc_encoding(self):
        stamp = datetime(2026, 9, 8, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(utc_timestamp(stamp), "2026-09-08T06:30:00.000000Z")
        with self.assertRaises(ControlledInputError):
            utc_timestamp(stamp.replace(tzinfo=None))

    def test_unordered_fhr_rows_canonicalize_without_mutating_source(self):
        payload = _approved_fhr()
        payload["fluids"].append({**payload["fluids"][0], "fluid_code": "ANOTHER"})
        payload["service_code_map"].append({"pid_service_code": "A", "fluid_code": "ANOTHER", "unit_scope": ""})
        original = copy.deepcopy(payload)
        first, _ = prepare_content("fhr", "fhr-v1", payload)
        self.assertEqual(payload, original)
        payload["fluids"].reverse()
        payload["service_code_map"].reverse()
        second, _ = prepare_content("fhr", "fhr-v1", payload)
        self.assertEqual(content_hash(first), content_hash(second))
        self.assertEqual(content_hash(json.loads(canonical_bytes(first))), content_hash(first))

    def test_unsupported_units_and_schema_fail_approval(self):
        payload = _approved_fhr()
        payload["fluids"][0]["flash_point_f"] = 200
        with self.assertRaises(ControlledInputError):
            prepare_content("fhr", "fhr-v1", payload)
        for kind, schema in (("sic", "sic-v1"), ("fhr", "fhr-v99")):
            self.assertEqual(prepare_content(kind, schema, {})[1]["status"], "unsupported")
            with self.assertRaises(ControlledInputError):
                validate_approval(kind, schema, {})

    def test_mock_cannot_be_approved(self):
        payload = _approved_fhr()
        payload["document"]["status"] = "draft_mock_unapproved"
        with self.assertRaisesRegex(ControlledInputError, "Synthetic"):
            validate_approval("fhr", "fhr-v1", payload)

    def test_server_decision_covers_rows_without_rewriting_imported_claims(self):
        payload = _approved_fhr()
        payload["document"].update(status="submitted", approved_by="", approved_date="")
        payload["fluids"][0].update(approved_by="", approved_date="")
        original = copy.deepcopy(payload)
        revision = dict(input_type="fhr", schema_version="fhr-v1", payload=payload,
            content_hash=content_hash(payload), decision="approved", decided_by="server-reviewer",
            decided_at="2026-09-08T00:00:00.000000Z")
        register = approved_fhr(revision)
        register.assert_approved()
        self.assertEqual(register.fluids[0].approved_by, "server-reviewer")
        self.assertEqual(payload, original)
        with self.assertRaises(ControlledInputError):
            approved_fhr({**revision, "decision": "pending"})
        with self.assertRaises(ControlledInputError):
            approved_fhr({**revision, "content_hash": "0" * 64})

    def test_scope_is_exact_and_rejects_missing_identity(self):
        context = dict(cnvrt_project_id=1, collection_id=2, job_id=3)
        self.assertEqual(scope_for("fhr", context)["job_id"], "3")
        self.assertEqual(scope_for("sic", context)["job_id"], "")
        for invalid in ({}, dict(context, job_id=True)):
            with self.assertRaises(ControlledInputError):
                scope_for("fhr", invalid)
