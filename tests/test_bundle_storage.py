"""Data fidelity and hostile-input checks for the analysis container."""

import hashlib
import json
import stat
import struct
import zipfile
from copy import deepcopy
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from rcc_refcert import bundle_storage as storage
from rcc_refcert.bellman_choi import verify_bellman_choi
from rcc_refcert.bounds.certificates import _snapshot
from rcc_refcert.bounds.contracts import canonical_hash
from rcc_refcert.examples import (
    make_dephase_bellman_choi_certificate,
    make_dephase_or_halt_model,
    make_multiblock_bellman_choi_certificate,
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificate,
)
from rcc_refcert.limits import (
    ComputationLimits,
    ResourceLimitError,
    estimate_certificate_resources,
)
from rcc_refcert.reference_potential import verify_reference_potential


def _objects():
    model = make_dephase_or_halt_model()
    return model, make_dephase_bellman_choi_certificate(model)


@pytest.fixture
def archive(tmp_path):
    model, certificate = _objects()
    path = tmp_path / "inputs.rcc"
    storage.save_bundle_payload(path, model, certificate, analysis={"exact": "19/20"})
    return path


def _read(path):
    with zipfile.ZipFile(path) as archive:
        data = {name: archive.read(name) for name in archive.namelist()}
    return data, json.loads(data["manifest.json"])


def _rewrite(path, data, manifest=None):
    if manifest is not None:
        unsigned = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        manifest["manifest_sha256"] = storage._json_hash(unsigned)
        data["manifest.json"] = json.dumps(manifest).encode()
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in data.items():
            archive.writestr(name, value)


@pytest.mark.parametrize("kind", ["H3", "H4"])
def test_rectangular_model_and_both_proofs_round_trip(tmp_path, kind):
    model = make_multiblock_rectangular_model()
    certificate = (
        make_multiblock_bellman_choi_certificate(model)
        if kind == "H3"
        else make_multiblock_reference_potential_certificate()
    )
    verifier = verify_bellman_choi if kind == "H3" else verify_reference_potential
    history = {
        "request": {"epsilon": "1/10", "eigenvalues": ["19/20", "1/20"]},
        "report": {"constant": verifier(model, certificate).constant},
    }
    path = storage.save_bundle_payload(
        tmp_path / "model.rcc", model, certificate, analysis=history
    )
    loaded = storage.load_bundle_payload(path)
    assert canonical_hash(_snapshot(loaded.model)) == canonical_hash(_snapshot(model))
    assert canonical_hash(_snapshot(loaded.certificate)) == canonical_hash(
        _snapshot(certificate)
    )
    assert (
        verifier(loaded.model, loaded.certificate).outcome
        == verifier(model, certificate).outcome
    )
    assert loaded.analysis == history
    schema = json.loads(
        (
            Path(storage.__file__).parent / "bundle_data/analysis_bundle.schema.json"
        ).read_text()
    )
    jsonschema.validate(loaded.manifest, schema)


def test_complex_endian_and_strided_arrays_preserve_values_and_dtype(tmp_path):
    model, certificate = _objects()
    source = np.array([[0.5, -0.0 + 0.1j], [-0.0 - 0.1j, 0.5]], dtype=">c16")
    backing = np.empty((4, 4), dtype=">c16")
    backing[::2, ::2] = source
    model.initial_blocks["q"] = backing[::2, ::2]
    assert not model.initial_blocks["q"].flags.c_contiguous
    certificate.constant = np.float32(1)
    path = storage.save_bundle_payload(
        tmp_path / "complex.rcc", model, certificate, analysis={}
    )
    loaded = storage.load_bundle_payload(path)
    assert loaded.model.initial_blocks["q"].dtype.str == ">c16"
    assert loaded.model.initial_blocks["q"].tobytes() == source.tobytes()
    assert canonical_hash(_snapshot(loaded.model)) == canonical_hash(_snapshot(model))
    assert canonical_hash(_snapshot(loaded.certificate)) == canonical_hash(
        _snapshot(certificate)
    )


def test_existing_file_needs_explicit_overwrite(archive):
    old = archive.read_bytes()
    model, certificate = _objects()
    with pytest.raises(FileExistsError):
        storage.save_bundle_payload(
            archive, model, certificate, analysis={"changed": True}
        )
    assert archive.read_bytes() == old
    storage.save_bundle_payload(
        archive, model, certificate, analysis={"changed": True}, overwrite=True
    )
    assert storage.load_bundle_payload(archive).analysis == {"changed": True}


def test_shared_budget_rejects_before_array_reads(archive, monkeypatch):
    model, certificate = _objects()
    estimate = estimate_certificate_resources(model, certificate)["estimated_elements"]
    calls = []
    original = storage._read_member

    def watch(*args):
        calls.append(args[1].filename)
        return original(*args)

    monkeypatch.setattr(storage, "_read_member", watch)
    with pytest.raises(ResourceLimitError, match="certificate_matrix_elements"):
        storage.load_bundle_payload(
            archive, limits=ComputationLimits(max_matrix_elements=estimate - 1)
        )
    assert calls == ["manifest.json"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "hash",
        "shape",
        "dtype",
        "nonfinite",
        "unused",
        "schema",
        "type",
        "map_duplicate",
        "field",
    ],
)
def test_invalid_payloads_are_rejected_even_with_recomputed_manifest(archive, mutation):
    data, manifest = _read(archive)
    descriptor = next(iter(manifest["arrays"].values()))
    if mutation == "missing":
        del data[descriptor["path"]]
    elif mutation == "hash":
        raw = bytearray(data[descriptor["path"]])
        raw[0] ^= 1
        data[descriptor["path"]] = bytes(raw)
    elif mutation == "shape":
        descriptor["shape"] = [2**31 - 1, 2**31 - 1]
    elif mutation == "dtype":
        descriptor["dtype"] = "|O"
    elif mutation == "nonfinite":
        array = np.frombuffer(
            data[descriptor["path"]], dtype=descriptor["storage_dtype"]
        ).copy()
        array[0] = np.nan
        data[descriptor["path"]] = array.tobytes()
        descriptor["sha256"] = hashlib.sha256(array.tobytes()).hexdigest()
    elif mutation == "unused":
        duplicate = deepcopy(descriptor)
        duplicate["path"] = "arrays/a999999.bin"
        manifest["arrays"]["a999999"] = duplicate
        data[duplicate["path"]] = data[descriptor["path"]]
    elif mutation == "schema":
        manifest["schema_version"] = 99
    elif mutation == "type":
        manifest["model"]["type"] = "arbitrary.module.Constructor"
    elif mutation == "map_duplicate":
        mapping = manifest["model"]["fields"]["control_dims"]["items"]
        mapping.append(deepcopy(mapping[0]))
    elif mutation == "field":
        manifest["model"]["fields"]["run_code"] = "print('unsafe')"
    _rewrite(archive, data, manifest)
    with pytest.raises((storage.BundleFormatError, ResourceLimitError)):
        storage.load_bundle_payload(archive)


@pytest.mark.parametrize(
    "name", ["../escape", "/tmp/escape", "arrays/../escape", "code.py"]
)
def test_archive_paths_are_never_extracted(archive, name):
    with zipfile.ZipFile(archive, "a") as target:
        target.writestr(name, b"not executable")
    with pytest.raises(storage.BundleFormatError, match="path"):
        storage.load_bundle_payload(archive)
    assert not (archive.parent.parent / "escape").exists()


def test_duplicate_member_and_symlink_are_rejected(archive):
    data, manifest = _read(archive)
    with (
        pytest.warns(UserWarning, match="Duplicate"),
        zipfile.ZipFile(archive, "a") as target,
    ):
        target.writestr("manifest.json", data["manifest.json"])
    with pytest.raises(storage.BundleFormatError, match="duplicate archive"):
        storage.load_bundle_payload(archive)
    _rewrite(archive, data, manifest)
    key = next(iter(manifest["arrays"].values()))["path"]
    with zipfile.ZipFile(archive, "w") as target:
        for name, value in data.items():
            info = zipfile.ZipInfo(name)
            if name == key:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            target.writestr(info, value)
    with pytest.raises(storage.BundleFormatError, match="regular file"):
        storage.load_bundle_payload(archive)


def test_duplicate_json_key_and_lying_directory_count_rejected(archive):
    data, manifest = _read(archive)
    data["manifest.json"] = b'{"format":"one","format":"two"}'
    _rewrite(archive, data)
    with pytest.raises(storage.BundleFormatError, match="duplicate JSON"):
        storage.load_bundle_payload(archive)
    _rewrite(archive, data, manifest)
    raw = bytearray(archive.read_bytes())
    struct.pack_into("<H", raw, len(raw) - 12, 0)
    struct.pack_into("<H", raw, len(raw) - 14, 0)
    archive.write_bytes(raw)
    with pytest.raises(storage.BundleFormatError, match="entry count"):
        storage.load_bundle_payload(archive)


@pytest.mark.parametrize(
    "bad", [np.array([[object()]], dtype=object), np.array([[np.inf]]), np.ones(2)]
)
def test_writer_rejects_unsupported_arrays(tmp_path, bad):
    model, certificate = _objects()
    model.reference_state = bad
    with pytest.raises(storage.BundleFormatError):
        storage.save_bundle_payload(
            tmp_path / "bad.rcc", model, certificate, analysis={}
        )
    assert not (tmp_path / "bad.rcc").exists()


def test_writer_and_reader_metadata_budgets(tmp_path, archive, monkeypatch):
    model, certificate = _objects()
    nested = {}
    for _ in range(60):
        nested = {"child": nested}
    with pytest.raises(storage.BundleFormatError, match="nesting"):
        storage.save_bundle_payload(
            tmp_path / "deep.rcc", model, certificate, analysis=nested
        )
    monkeypatch.setattr(storage, "MAX_MANIFEST_BYTES", 64)
    with pytest.raises(storage.BundleFormatError, match="manifest byte"):
        storage.load_bundle_payload(archive)
    with pytest.raises(storage.BundleFormatError, match="manifest byte"):
        storage.save_bundle_payload(
            tmp_path / "large.rcc", model, certificate, analysis={}
        )


def test_writer_counts_manifest_wrapping_in_depth_limit(tmp_path):
    model, certificate = _objects()
    nested = {}
    for _ in range(storage.MAX_DEPTH):
        nested = {"child": nested}
    with pytest.raises(storage.BundleFormatError, match="nesting"):
        storage.save_bundle_payload(
            tmp_path / "wrapped.rcc", model, certificate, analysis=nested
        )
    assert not (tmp_path / "wrapped.rcc").exists()


def test_invalid_deflate_stream_has_format_error(archive):
    raw = bytearray(archive.read_bytes())
    with zipfile.ZipFile(archive) as target:
        info = target.getinfo("manifest.json")
    name_size, extra_size = struct.unpack_from("<2H", raw, info.header_offset + 26)
    payload_offset = info.header_offset + 30 + name_size + extra_size
    raw[payload_offset] = 0xFF
    archive.write_bytes(raw)
    with pytest.raises(storage.BundleFormatError, match="archive bytes"):
        storage.load_bundle_payload(archive)


def test_complete_analysis_conforms_to_both_published_schemas(tmp_path):
    from rcc_refcert.bundle import save_analysis_bundle

    model, certificate = _objects()
    path = save_analysis_bundle(tmp_path / "analysis.rcc", model, certificate)
    loaded = storage.load_bundle_payload(path)
    directory = Path(storage.__file__).parent / "bundle_data"
    container_schema = json.loads(
        (directory / "analysis_bundle.schema.json").read_text()
    )
    analysis_schema = json.loads((directory / "analysis.schema.json").read_text())
    jsonschema.validate(loaded.manifest, container_schema)
    jsonschema.validate(loaded.analysis, analysis_schema)
    invalid = deepcopy(loaded.analysis)
    invalid["controls"]["unknown"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, analysis_schema)


@pytest.mark.parametrize("target", ["analysis", "model"])
def test_oversized_text_rejected_before_hashing_or_serialization(
    tmp_path, monkeypatch, target
):
    model, certificate = _objects()
    analysis = {}
    huge = "x" * (storage.MAX_MANIFEST_BYTES + 1)
    if target == "analysis":
        analysis["text"] = huge
    else:
        model.name = huge

    def unexpected(*args):
        pytest.fail("oversized text reached serialization or hashing")

    monkeypatch.setattr(storage, "_json_bytes", unexpected)
    monkeypatch.setattr(storage, "_component_hashes", unexpected)
    with pytest.raises(storage.BundleFormatError, match="manifest byte"):
        storage.save_bundle_payload(
            tmp_path / "oversized.rcc", model, certificate, analysis=analysis
        )
