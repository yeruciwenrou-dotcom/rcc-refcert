"""Scientific contracts, exact inputs and saved-record regression tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

from rcc_refcert.bounds import (
    InputError,
    Task,
    bound_from_counts,
    bound_from_spectrum,
    prepare_protocol,
    render_record,
    replay_record,
    validate_record,
)
from rcc_refcert.bounds.scalar import Interval, invert_canonical

ROOT = Path(__file__).resolve().parents[1] / "src/rcc_refcert/bounds"


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((ROOT / "data/spectrum.json").read_text())
        self.c = json.loads((ROOT / "data/projection_counts.json").read_text())

    def cli(self, request, command="spectrum", raw=False, details=False):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "request.json"
            file.write_text(request if raw else json.dumps(request), encoding="utf-8")
            args = [
                sys.executable,
                "-m",
                "rcc_refcert.bounds",
                command,
                str(file),
                "--format",
                "json",
            ]
            if details:
                args.append("--details")
            return subprocess.run(args, text=True, capture_output=True, check=False)

    def test_protocol_scientific_changes_reject_old_data(self):
        for key, value in [
            ("rank", 2),
            ("witness_id", "different"),
            ("delta_stat", ".9"),
            ("id", "different-protocol"),
        ]:
            with self.subTest(field=key):
                request = copy.deepcopy(self.c)
                request["protocol"][key] = value
                with self.assertRaises(InputError):
                    bound_from_counts(request)

    def test_missing_acquisition_digest_rejected(self):
        del self.c["data"]["protocol_sha256"]
        with self.assertRaises(InputError):
            bound_from_counts(self.c)

    def test_prepare_protocol_is_nonmutating(self):
        spec = {k: v for k, v in self.c["protocol"].items() if k != "task_fingerprint"}
        before = copy.deepcopy(spec)
        frozen = prepare_protocol(self.c["task"], spec)
        self.assertEqual(spec, before)
        self.assertEqual(frozen["protocol_sha256"], self.c["data"]["protocol_sha256"])
        self.assertFalse(frozen["chronology_or_iid_independently_verified"])

    def test_protocol_equivalent_decimal_spellings(self):
        for value in ["0.05", "1/20", Q(1, 20), Decimal(".050")]:
            self.c["protocol"]["delta_stat"] = value
            result = bound_from_counts(self.c)
            self.assertEqual(result["confidence"]["coverage_at_least_exact"], "19/20")

    def test_exact_python_spectrum_types(self):
        baseline = bound_from_spectrum(self.s)
        for values in [
            [Q(11, 20), Q(3, 10), Q(1, 10), Q(1, 20)],
            [Decimal(".55"), Decimal(".3"), Decimal(".1"), Decimal(".05")],
        ]:
            self.s["spectrum"] = values
            result = bound_from_spectrum(self.s)
            self.assertEqual(result["cost"], baseline["cost"])
            self.assertEqual(result["information"], baseline["information"])

    def test_exact_python_model_types(self):
        before = Task.from_dict(self.s["task"]).fingerprint
        m = self.s["task"]["model"]
        m["transcription"]["a"] = Q(0)
        m["transcription"]["gamma_bits"] = Decimal(0)
        m["reference_domination"]["upper_constant"] = Q(1)
        self.s["task"]["target"]["epsilon"] = Decimal(".10")
        self.assertEqual(Task.from_dict(self.s["task"]).fingerprint, before)
        bound_from_spectrum(self.s)

    def test_exact_nonterminating_rational_spectrum(self):
        self.s["spectrum"] = [Q(1, 3), Q(1, 3), Q(1, 3), Q(0)]
        result = bound_from_spectrum(self.s)
        self.assertEqual(result["information"]["cap_exact"], "3/10")

    def test_large_transcription_integer_record_round_trip(self):
        for field in ["a", "gamma_bits"]:
            for value in [10**512, Q(10**512), "1e512", Decimal("1e512")]:
                with self.subTest(field=field, scalar_type=type(value).__name__):
                    request = copy.deepcopy(self.s)
                    request["task"]["model"]["transcription"][field] = value
                    record = bound_from_spectrum(request)
                    replay_record(json.loads(json.dumps(record)))

    def test_binary_float_not_silently_promoted(self):
        self.s["spectrum"] = [0.55, 0.30, 0.10, 0.05]
        with self.assertRaises(InputError):
            bound_from_spectrum(self.s)

    def test_json_decimal_tokens_are_lossless(self):
        self.s["spectrum"] = [0.55, 0.30, 0.10, 0.05]
        run = self.cli(self.s)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(json.loads(run.stdout)["information"]["cap_exact"], "9/20")

    def test_cli_duplicate_keys_rejected(self):
        raw = json.dumps(self.s).replace(
            '"epsilon": "0.1"', '"epsilon":"0.1","epsilon":"0.2"'
        )
        run = self.cli(raw, raw=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("duplicate JSON key", run.stdout)

    def test_cli_nonfinite_json_rejected(self):
        raw = json.dumps(self.s).replace('"0.55"', "NaN")
        run = self.cli(raw, raw=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["analysis_state"], "invalid_input")

    def test_cli_error_states_are_separate(self):
        requests = []
        a = copy.deepcopy(self.s)
        a["spectrum"] = [1, 1, 0, 0]
        requests.append((a, "invalid_input"))
        a = copy.deepcopy(self.s)
        a["task"]["model"]["transcription"]["mode"] = "approximate"
        requests.append((a, "unsupported_contract"))
        a = copy.deepcopy(self.s)
        a["spectrum"][0] = "1e9999"
        requests.append((a, "resource_limit"))
        for request, state in requests:
            with self.subTest(state=state):
                run = self.cli(request)
                self.assertEqual(run.returncode, 2)
                payload = json.loads(run.stdout)
                self.assertEqual(payload["analysis_state"], state)
                self.assertIsNone(payload["cost"])

    def test_prepare_protocol_cli(self):
        spec = json.loads((ROOT / "data/protocol_spec.json").read_text())
        run = self.cli(spec, command="prepare-protocol")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(
            json.loads(run.stdout)["protocol_sha256"], self.c["data"]["protocol_sha256"]
        )

    def test_spectrum_shape_raises_domain_error(self):
        for value in [None, 1, {"0": 1}, True]:
            with self.subTest(value=value):
                self.s["spectrum"] = value
                with self.assertRaises(InputError):
                    bound_from_spectrum(self.s)

    def test_enum_types_raise_domain_error(self):
        for field in ["source_kind"]:
            self.s["task"]["model"]["reference_domination"][field] = []
            with self.assertRaises(InputError):
                bound_from_spectrum(self.s)

    def test_short_output_is_downward(self):
        for epsilon in ["0", ".1", ".30", ".35", "1"]:
            self.s["task"]["target"]["epsilon"] = epsilon
            result = bound_from_spectrum(self.s)
            self.assertLessEqual(
                Q(result["display"]["lower_bound_slots"]),
                Q(result["cost"]["lower_bound_slots"]),
            )
            self.assertIn(result["display"]["lower_bound_slots"], render_record(result))
            self.assertIn(
                result["cost"]["lower_bound_slots"], render_record(result, details=True)
            )

    def test_unspecified_integer_is_not_shown_as_none(self):
        self.s["task"]["model"]["cost_domain"] = "unspecified"
        self.assertNotIn("None", render_record(bound_from_spectrum(self.s)))

    def test_smoothing_zero_explanation(self):
        self.s["task"]["target"]["epsilon"] = ".35"
        result = bound_from_spectrum(self.s)
        self.assertEqual(result["cost"]["zero_reason"], "smoothing_saturated")
        self.assertIn("not a claim of zero preparation cost", render_record(result))

    def test_model_overhead_zero_explanation(self):
        self.s["task"]["model"]["transcription"]["gamma_bits"] = "2"
        result = bound_from_spectrum(self.s)
        self.assertEqual(result["cost"]["zero_reason"], "model_overhead_exhausted")

    def test_sampling_zero_explanation(self):
        self.c["data"]["hits"] = 0
        self.assertEqual(
            bound_from_counts(self.c)["cost"]["zero_reason"],
            "sampling_margin_exhausted",
        )

    def test_reference_contrast_zero_explanation(self):
        self.c["data"]["hits"] = 200
        self.assertEqual(
            bound_from_counts(self.c)["cost"]["zero_reason"],
            "reference_contrast_not_resolved",
        )

    def test_record_role_confidence_and_identity_mutations(self):
        base = bound_from_counts(self.c)
        changes = [
            lambda r: r.__setitem__("confidence", {}),
            lambda r: r["confidence"].__setitem__("coverage_at_least_exact", "1"),
            lambda r: r["task"].__setitem__("fingerprint", "0" * 64),
            lambda r: r["parameters"].__setitem__("smoothing_radius", "0"),
            lambda r: r["reference_treatment"].__setitem__("reference_id", "different"),
            lambda r: r["qualification"].__setitem__("TC", {}),
            lambda r: r["cost"].__setitem__("lower_bound_slots", "NaN"),
            lambda r: r["cost"].__setitem__(
                "enclosure_upper_is_process_upper_bound", True
            ),
            lambda r: r["information"].__setitem__("rank", 2),
            lambda r: r["display"].__setitem__("lower_bound_slots", "999"),
            lambda r: r.__setitem__("analysis_state", "partial"),
        ]
        for i, change in enumerate(changes):
            with self.subTest(mutation=i):
                record = copy.deepcopy(base)
                change(record)
                with self.assertRaises(InputError):
                    validate_record(record)

    def test_spectrum_confidence_invention_refused(self):
        record = bound_from_spectrum(self.s)
        record["confidence"] = {"coverage_at_least_exact": "1", "scope": "fabricated"}
        with self.assertRaises(InputError):
            validate_record(record)

    def test_schema_v1_is_not_silently_accepted(self):
        record = bound_from_spectrum(self.s)
        record["schema_version"] = 1
        with self.assertRaises(InputError):
            validate_record(record)

    def test_integer_boundary_is_enclosed_without_rounding_snap(self):
        for y in [Q(1) - Q(1, 10**30), Q(1), Q(1) + Q(1, 10**30)]:
            interval, _status = invert_canonical(
                Interval.point(y), Interval.point(1), 0
            )
            self.assertEqual(interval.lower, y)
            self.assertEqual(interval.upper, y)

    def test_optional_schema_shapes(self):
        if importlib.util.find_spec("jsonschema") is None:
            self.skipTest(
                "optional JSON Schema validator not installed; stdlib cross-field checks still run"
            )
        from jsonschema import Draft202012Validator

        schema = json.loads((ROOT / "data/bound_record.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for result in [bound_from_spectrum(self.s), bound_from_counts(self.c)]:
            validator.validate(result)
        base = bound_from_counts(self.c)
        for change in [
            lambda r: r["cost"].__setitem__("lower_bound_slots", "NaN"),
            lambda r: r.__setitem__("confidence", {}),
            lambda r: r["qualification"].__setitem__("TC", {}),
            lambda r: r["calibration"].__setitem__("statistical", None),
            lambda r: r["path"].__setitem__("name", "unimplemented"),
        ]:
            record = copy.deepcopy(base)
            change(record)
            self.assertTrue(list(validator.iter_errors(record)))


class ReplayAndInversionTests(unittest.TestCase):
    def test_records_replay_both_paths(self):
        from rcc_refcert.bounds import replay_record

        for name, function in [
            ("spectrum", bound_from_spectrum),
            ("projection_counts", bound_from_counts),
        ]:
            request = json.loads((ROOT / "data" / f"{name}.json").read_text())
            record = function(request)
            self.assertTrue(replay_record(json.loads(json.dumps(record)))["matches"])

    def test_snapshot_tampering_refused(self):
        from rcc_refcert.bounds import replay_record

        request = json.loads((ROOT / "data/spectrum.json").read_text())
        record = bound_from_spectrum(request)
        record["provenance"]["input_snapshot"]["spectrum"][0] = ".56"
        with self.assertRaises(InputError):
            replay_record(record)

    def test_valid_shape_with_wrong_scientific_result_does_not_replay(self):
        from rcc_refcert.bounds import replay_record

        request = json.loads((ROOT / "data/spectrum.json").read_text())
        record = bound_from_spectrum(request)
        # Lowering a diagnostic need not fail a shape validator, but replay
        # must detect a scientific value differing from the saved input.
        record["information"]["relative_entropy_bits"] = {"lower": "0", "upper": "0"}
        validate_record(record)
        with self.assertRaises(InputError):
            replay_record(record)

    def test_nonlinear_closed_roots(self):
        for root in [Q(2), Q(4), Q(16)]:
            from rcc_refcert.bounds.scalar import phi_interval

            y = phi_interval(root, Interval.point(3), Q(1))
            interval, status = invert_canonical(y, Interval.point(3), 1)
            self.assertLessEqual(interval.lower, root)
            self.assertGreaterEqual(interval.upper, root)
            self.assertEqual(status, "complete")

    def test_iteration_budget_reports_safe_partial(self):
        interval, status = invert_canonical(
            Interval.point(13), Interval.point(3), 1, max_steps=1
        )
        self.assertNotEqual(status, "complete")
        from rcc_refcert.bounds.scalar import phi_interval

        self.assertLessEqual(
            phi_interval(interval.lower, Interval.point(3), Q(1)).upper, 13
        )
        self.assertGreaterEqual(
            phi_interval(interval.upper, Interval.point(3), Q(1)).lower, 13
        )


class ExtremeScalarRoundtripTests(unittest.TestCase):
    def test_small_exact_radius_survives_canonical_serialization(self):
        from rcc_refcert.bounds import replay_record

        request = json.loads((ROOT / "data/spectrum.json").read_text())
        request["task"]["target"]["epsilon"] = "1e-600"
        record = bound_from_spectrum(request)
        self.assertTrue(replay_record(json.loads(json.dumps(record)))["matches"])

    def test_public_version_matches_producer(self):
        import rcc_refcert.bounds

        request = json.loads((ROOT / "data/spectrum.json").read_text())
        self.assertEqual(
            bound_from_spectrum(request)["producer"]["version"],
            rcc_refcert.bounds.__version__,
        )


if __name__ == "__main__":
    unittest.main()
