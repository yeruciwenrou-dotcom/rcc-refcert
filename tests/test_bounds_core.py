from __future__ import annotations

import json
import random
import subprocess
import sys
import unittest
from decimal import getcontext
from fractions import Fraction as Q
from pathlib import Path

from rcc_refcert.bounds import (
    BudgetError,
    InputError,
    Task,
    UnsupportedContract,
    bound_from_counts,
    bound_from_spectrum,
    hoeffding_lower,
    projection_information,
    render_record,
    spectral_information,
)
from rcc_refcert.bounds.scalar import (
    Interval,
    ceil_fraction,
    invert_canonical,
    log2_interval,
    rational,
    sqrt_interval,
)

ROOT = Path(__file__).resolve().parents[1] / "src/rcc_refcert/bounds"


class ScalarTests(unittest.TestCase):
    def test_rejects_ambiguous_or_nonfinite(self):
        for value in [True, 0.1, float("nan"), "nan", "inf", "1/0", None, object()]:
            with self.subTest(value=str(value)), self.assertRaises(InputError):
                rational(value)

    def test_input_budget(self):
        with self.assertRaises(BudgetError):
            rational("1e99999999")
        with self.assertRaises(BudgetError):
            rational("0." + "1" * 511)
        with self.assertRaises(BudgetError):
            rational("1" * 5001)
        with self.assertRaises(BudgetError):
            rational(str(2**8192))

    def test_canonical_integer_round_trip_at_bit_budget(self):
        for value in [10**512, 2**8192 - 1, -(2**8192 - 1)]:
            with self.subTest(value_bits=value.bit_length()):
                self.assertEqual(rational(str(rational(value))), value)

    def test_context_is_not_modified(self):
        before = getcontext().copy()
        log2_interval(Q(11, 5))
        self.assertEqual(str(before), str(getcontext()))

    def test_power_two_logs_exact(self):
        for e in range(-16, 17):
            q = Q(2) ** e
            self.assertEqual(log2_interval(q), Interval.point(e))

    def test_sqrt_exact_enclosure(self):
        for q in [Q(0), Q(2), Q(1, 9), Q(10**10), Q(1, 10**140), Q(17, 31)]:
            i = sqrt_interval(q)
            self.assertLessEqual(i.lower * i.lower, q)
            self.assertGreaterEqual(i.upper * i.upper, q)

    def test_basic_interval_arithmetic(self):
        a = Interval(Q(-2), Q(3))
        b = Interval(Q(4), Q(5))
        self.assertEqual(a * b, Interval(Q(-10), Q(15)))
        self.assertEqual(a / b, Interval(Q(-1, 2), Q(3, 4)))

    def test_linear_inverse_exact(self):
        for y in [-1, 0, 1, 2, 10]:
            i, s = invert_canonical(Interval.point(y), Interval.point(2), 0)
            self.assertEqual(i, Interval.point(max(Q(0), Q(y, 2))))
            self.assertEqual(s, "complete")

    def test_nonlinear_exact_boundary(self):
        # Phi_{1,1}(2)=3 exactly; a loose root bracket must still contain 2.
        i, _s = invert_canonical(Interval.point(3), Interval.point(1), 1)
        self.assertLessEqual(i.lower, 2)
        self.assertGreaterEqual(i.upper, 2)
        self.assertEqual(ceil_fraction(i.lower), 2)

    def test_zero_and_budget_inverse(self):
        i, s = invert_canonical(Interval.point(-1), Interval.point(1), 1)
        self.assertEqual(i, Interval.point(0))
        i, s = invert_canonical(Interval.point(10), Interval.point(1), 1, max_steps=1)
        self.assertEqual(s, "iteration_budget_reached")
        self.assertGreaterEqual(i.upper, i.lower)

    def test_inverse_invalid(self):
        for g, a in [(0, 1), (1, -1)]:
            with self.assertRaises(InputError):
                invert_canonical(Interval.point(2), Interval.point(g), a)

    def test_near_integer_ceil(self):
        self.assertEqual(ceil_fraction(Q(2) - Q(1, 10**50)), 2)
        self.assertEqual(ceil_fraction(Q(2) + Q(1, 10**50)), 3)


class SpectrumTests(unittest.TestCase):
    def test_named_spectral_caps(self):
        for eps, cap in [
            ("0", "0.55"),
            ("0.1", "0.45"),
            ("0.3", "0.275"),
            ("0.35", "0.25"),
            ("1", "0.25"),
        ]:
            r = spectral_information([".55", ".30", ".10", ".05"], 4, eps)
            self.assertEqual(r.cap, Q(cap))

    def test_uniform_states(self):
        for d in [1, 2, 3, 4, 7, 16]:
            for eps in [Q(0), Q(1, 5), Q(1)]:
                r = spectral_information([Q(1, d)] * d, d, eps)
                self.assertEqual(r.information, Interval.point(0))
                self.assertIsNone(r.witness_rank)

    def test_pure_states_full_epsilon_domain(self):
        for d in [1, 2, 4, 8]:
            for eps in [Q(0), Q(1, 10), Q(1, 2), Q(9, 10), Q(1)]:
                r = spectral_information([1] + [0] * (d - 1), d, eps)
                self.assertEqual(r.cap, max(Q(1, d), 1 - eps))

    def test_permutation_and_monotonicity(self):
        r1 = spectral_information([".55", ".3", ".1", ".05"], 4, ".1")
        r2 = spectral_information([".1", ".55", ".05", ".3"], 4, ".1")
        self.assertEqual(r1, r2)
        caps = [
            spectral_information([".55", ".3", ".1", ".05"], 4, Q(i, 20)).cap
            for i in range(21)
        ]
        self.assertEqual(caps, sorted(caps, reverse=True))

    def test_witness_identity(self):
        rng = random.Random(20260909)
        for d in [2, 3, 4, 8]:
            for _ in range(6):
                w = [rng.randint(1, 50) for _ in range(d)]
                lam = [Q(v, sum(w)) for v in w]
                for eps in [Q(0), Q(1, 20), Q(1, 5)]:
                    r = spectral_information(lam, d, eps)
                    if r.witness_rank:
                        self.assertEqual((r.witness_mass - eps) / r.witness_rank, r.cap)
                        self.assertEqual(
                            projection_information(
                                r.witness_mass, r.witness_rank, d, eps
                            ),
                            r.information,
                        )

    def test_invalid_spectra(self):
        for lam, d, eps in [
            ([".9"], 2, 0),
            ([".8", ".3"], 2, 0),
            (["1.1", "-.1"], 2, 0),
            ([0, 0], 2, 0),
            ([1, 0], 2, "1.1"),
            ([1, 0], 2, "-.01"),
        ]:
            with self.subTest(lam=lam, d=d, eps=eps), self.assertRaises(InputError):
                spectral_information(lam, d, eps)

    def test_feasible_cap_is_wrong_direction(self):
        r = spectral_information([".55", ".3", ".1", ".05"], 4, ".1")
        self.assertGreater(log2_interval(Q(4) * Q(".46")).lower, r.information.upper)

    def test_denominator_preflight_is_explicit(self):
        lam = [Q(1, 2**100)] * 1999 + [1 - Q(1999, 2**100)]
        with self.assertRaises(BudgetError):
            spectral_information(lam, 2000, 0)

    def test_large_dimension_budget(self):
        with self.assertRaises(BudgetError):
            spectral_information([], 4097, 0)


class StatisticalTests(unittest.TestCase):
    def test_zero_hits(self):
        self.assertEqual(hoeffding_lower(0, 10, ".05"), Interval.point(0))

    def test_all_hits_and_small_sample(self):
        r = hoeffding_lower(10, 10, ".05")
        self.assertGreater(r.lower, 0)
        self.assertLess(r.upper, 1)
        self.assertEqual(hoeffding_lower(1, 1, ".001"), Interval.point(0))

    def test_invalid_counts(self):
        for h, n, delta in [
            (1, 0, ".05"),
            (-1, 10, ".05"),
            (11, 10, ".05"),
            (True, 10, ".05"),
            (2, 10, 0),
            (2, 10, 1),
            (2, 10, "nan"),
        ]:
            with self.subTest(h=h, n=n, delta=delta), self.assertRaises(InputError):
                hoeffding_lower(h, n, delta)

    def test_projection_endpoints(self):
        self.assertEqual(projection_information(".1", 1, 4, ".1"), Interval.point(0))
        self.assertEqual(projection_information("1", 4, 4, 0), Interval.point(0))
        self.assertEqual(projection_information("1", 1, 4, 0), Interval.point(2))

    def test_invalid_rank(self):
        for rank in [0, 5, True]:
            with self.assertRaises(InputError):
                projection_information(".5", rank, 4, ".1")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads((ROOT / "data/spectrum.json").read_text())
        self.c = json.loads((ROOT / "data/projection_counts.json").read_text())

    def test_d47_record_and_evidence_separation(self):
        a = bound_from_spectrum(self.s)
        b = bound_from_counts(self.c)
        self.assertIsNone(a["confidence"])
        self.assertEqual(b["confidence"]["coverage_at_least_exact"], "19/20")
        for key in [
            "model",
            "qualification",
            "path",
            "parameters",
            "calibration",
            "reference_treatment",
            "flags",
        ]:
            self.assertIn(key, a)
            self.assertIn(key, b)
        self.assertFalse(a["cost"]["enclosure_upper_is_process_upper_bound"])
        self.assertEqual(a["record_role"], "conditional_cost_lower_bound")

    def test_no_unspecified_integer_rounding(self):
        self.s["task"]["model"]["cost_domain"] = "unspecified"
        self.assertIsNone(
            bound_from_spectrum(self.s)["cost"]["integer_lower_bound_slots"]
        )

    def test_no_implicit_missing_parameters(self):
        del self.s["task"]["model"]["transcription"]["a"]
        with self.assertRaises(InputError):
            bound_from_spectrum(self.s)

    def test_h34_point_estimate_refused(self):
        self.s["task"]["model"]["reference_domination"]["source_kind"] = (
            "h34_point_estimate"
        )
        with self.assertRaises(InputError):
            bound_from_spectrum(self.s)

    def test_unsupported_tc(self):
        self.s["task"]["model"]["transcription"]["mode"] = "approximate"
        with self.assertRaises(UnsupportedContract):
            bound_from_spectrum(self.s)

    def test_same_data_witness_selection_refused(self):
        self.c["protocol"]["selection"] = "selected_on_same_data"
        with self.assertRaises(UnsupportedContract):
            bound_from_counts(self.c)

    def test_non_iid_and_optional_stopping_refused(self):
        for mode in ["correlated", "optional_stopping"]:
            self.c["protocol"]["sampling"] = mode
            with self.assertRaises(UnsupportedContract):
                bound_from_counts(self.c)

    def test_task_protocol_mismatch_refused(self):
        self.c["task"]["target"]["epsilon"] = ".2"
        with self.assertRaises(InputError):
            bound_from_counts(self.c)

    def test_fixed_sample_size_mismatch_refused(self):
        self.c["data"]["samples"] = 999
        with self.assertRaises(InputError):
            bound_from_counts(self.c)

    def test_unknown_fields_refused(self):
        self.s["leakage_correction"] = ".1"
        with self.assertRaises(InputError):
            bound_from_spectrum(self.s)

    def test_immutable_task_snapshot(self):
        t = Task.from_dict(self.s["task"])
        fingerprint = t.fingerprint
        self.s["task"]["model"]["id"] = "other"
        self.assertEqual(t.fingerprint, fingerprint)

    def test_render_preserves_record_values(self):
        r = bound_from_spectrum(self.s)
        self.assertIn(r["cost"]["lower_bound_slots"], render_record(r, details=True))

    def test_cli_real_entrypoint(self):
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "rcc_refcert.bounds",
                "spectrum",
                str(ROOT / "data/spectrum.json"),
                "--format",
                "json",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(
            json.loads(run.stdout)["record_role"], "conditional_cost_lower_bound"
        )

    def test_cli_failure_has_no_cost(self):
        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "rcc_refcert.bounds",
                "spectrum",
                str(ROOT / "data/missing.json"),
                "--format",
                "json",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(run.returncode, 2)
        self.assertIsNone(json.loads(run.stdout)["cost"])


if __name__ == "__main__":
    unittest.main()
