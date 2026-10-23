"""Bounded, data-only storage for finite RCC models and H.3/H.4 proof objects.

The archive contains JSON and raw numeric arrays. Reading it never imports a
named type, extracts a path, or executes user code. Integrity hashes identify
bytes; they do not authenticate a producer or establish physical assumptions.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import stat
import struct
import tempfile
import zipfile
import zlib
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np

from ._version import __version__
from .bellman_choi import BellmanChoiCertificate
from .bounds.certificates import _snapshot
from .bounds.contracts import canonical_hash
from .limits import DEFAULT_LIMITS, ComputationLimits, ResourceLimitError
from .model import Action, FiniteControlModel
from .reference_potential import ReferencePotentialCertificate

FORMAT = "rcc-refcert.analysis-bundle"
SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_MEMBERS = 4096
MAX_DEPTH = 48
MAX_NODES = 100_000
_ARRAY_ID = re.compile(r"a[0-9]{6}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DTYPES = {
    "|b1",
    "|i1",
    "|u1",
    "<i2",
    "<i4",
    "<i8",
    "<u2",
    "<u4",
    "<u8",
    "<f2",
    "<f4",
    "<f8",
    "<c8",
    "<c16",
}
_TYPES = {
    cls.__name__: cls
    for cls in (
        Action,
        FiniteControlModel,
        BellmanChoiCertificate,
        ReferencePotentialCertificate,
    )
}


class BundleFormatError(ValueError):
    """An archive fails the supported data format or its integrity checks."""


@dataclass(frozen=True)
class BundlePayload:
    model: FiniteControlModel
    certificate: BellmanChoiCertificate | ReferencePotentialCertificate
    analysis: dict
    manifest: dict


def _fail(message: str) -> None:
    raise BundleFormatError(message)


def _exact_keys(value: object, keys: set[str], label: str) -> None:
    if type(value) is not dict or set(value) != keys:
        _fail(f"{label}: unexpected or missing fields")


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise BundleFormatError("unsupported JSON value") from exc


def _json_hash(value: object) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _text_bytes(value: str) -> int:
    if len(value) > MAX_MANIFEST_BYTES:
        _fail("manifest byte budget exceeded by text")
    total = 0
    try:
        for offset in range(0, len(value), 8192):
            total += len(value[offset : offset + 8192].encode("utf-8"))
            if total > MAX_MANIFEST_BYTES:
                _fail("manifest byte budget exceeded by text")
    except UnicodeError as exc:
        raise BundleFormatError("text must be valid UTF-8") from exc
    return total


def _bounded_json(
    value: object, depth: int = 0, counter: list[int] | None = None
) -> None:
    if counter is None:
        counter = [0, 0]
    counter[0] += 1
    if depth > MAX_DEPTH or counter[0] > MAX_NODES:
        _fail("JSON nesting or node budget exceeded")
    if type(value) is str:
        counter[1] += _text_bytes(value)
        if counter[1] > MAX_MANIFEST_BYTES:
            _fail("manifest byte budget exceeded by text")
        return
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if value.bit_length() > 8192:
            _fail("JSON integer exceeds 8192 bits")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail("nonfinite JSON scalar")
        return
    if type(value) is list:
        for item in value:
            _bounded_json(item, depth + 1, counter)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for key in value:
            counter[1] += _text_bytes(key)
        if counter[1] > MAX_MANIFEST_BYTES:
            _fail("manifest byte budget exceeded by text")
        for item in value.values():
            _bounded_json(item, depth + 1, counter)
        return
    _fail("analysis and manifest metadata must contain only JSON values")


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(data: bytes) -> dict:
    try:
        result = json.loads(
            data,
            object_pairs_hook=_pairs_unique,
            parse_constant=lambda value: _fail(f"nonfinite JSON: {value}"),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, BundleFormatError):
            raise
        raise BundleFormatError("invalid manifest JSON") from exc
    _bounded_json(result)
    return result


def _dtype(value: object) -> np.dtype:
    if type(value) is not str or len(value) > 4:
        _fail("array dtype must name a standard numeric dtype")
    try:
        dtype = np.dtype(value)
    except TypeError as exc:
        raise BundleFormatError("unsupported array dtype") from exc
    if dtype.str != value or dtype.newbyteorder("<").str not in _DTYPES:
        _fail("array dtype must be a standard numeric dtype")
    return dtype


class _Encoder:
    def __init__(self, limits: ComputationLimits):
        self.arrays: dict[str, np.ndarray] = {}
        self.descriptors: dict[str, dict] = {}
        self.limits = limits
        self.elements = 0
        self.nodes = 0
        self.text_bytes = 0

    def encode(self, value: object, depth: int = 0) -> object:
        self.nodes += 1
        if depth > MAX_DEPTH or self.nodes > MAX_NODES:
            _fail("model or certificate nesting/node budget exceeded")
        if type(value) is str:
            self.text_bytes += _text_bytes(value)
            if self.text_bytes > MAX_MANIFEST_BYTES:
                _fail("manifest byte budget exceeded by text")
            return value
        if value is None or type(value) is bool:
            return value
        if type(value) is int or isinstance(value, np.integer):
            result = int(value)
            if result.bit_length() > 8192:
                _fail("integer exceeds 8192 bits")
            return result
        if isinstance(value, (float, np.floating)):
            if isinstance(value, np.floating) and value.dtype.itemsize > 8:
                _fail("extended-precision scalar is unsupported")
            if not np.isfinite(value):
                _fail("nonfinite model or certificate scalar")
            return {"kind": "float", "hex": float(value).hex()}
        if isinstance(value, (complex, np.complexfloating)):
            if isinstance(value, np.complexfloating) and value.dtype.itemsize > 16:
                _fail("extended-precision scalar is unsupported")
            if not np.isfinite(value):
                _fail("nonfinite model or certificate scalar")
            return {
                "kind": "complex",
                "real": float(value.real).hex(),
                "imag": float(value.imag).hex(),
            }
        if type(value) is np.ndarray:
            if value.ndim != 2 or any(d < 1 for d in value.shape):
                _fail("model and certificate arrays must be nonempty matrices")
            dtype = _dtype(value.dtype.str)
            self.elements += value.size
            if self.elements > self.limits.max_matrix_elements:
                raise ResourceLimitError(
                    "bundle_input_elements",
                    self.elements,
                    self.limits.max_matrix_elements,
                )
            if len(self.arrays) >= MAX_MEMBERS - 1:
                _fail("too many arrays")
            key = f"a{len(self.arrays):06d}"
            self.arrays[key] = value
            self.descriptors[key] = {
                "path": f"arrays/{key}.bin",
                "shape": list(value.shape),
                "dtype": dtype.str,
                "storage_dtype": dtype.newbyteorder("<").str,
                "nbytes": value.size * dtype.itemsize,
            }
            return {"kind": "array", "id": key}
        if type(value) in _TYPES.values():
            return {
                "kind": "object",
                "type": type(value).__name__,
                "fields": {
                    f.name: self.encode(getattr(value, f.name), depth + 1)
                    for f in fields(value)
                },
            }
        if type(value) in (tuple, list):
            return {
                "kind": "tuple" if type(value) is tuple else "list",
                "items": [self.encode(item, depth + 1) for item in value],
            }
        if type(value) is dict:
            return {
                "kind": "map",
                "items": [
                    [self.encode(key, depth + 1), self.encode(item, depth + 1)]
                    for key, item in value.items()
                ],
            }
        _fail(f"unsupported input type: {type(value).__name__}")


def _hex_float(value: object) -> float:
    if type(value) is not str or len(value) > 40:
        _fail("invalid hexadecimal float")
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise BundleFormatError("invalid hexadecimal float") from exc
    if not math.isfinite(result) or result.hex() != value:
        _fail("float must be finite and canonically encoded")
    return result


def _map_key(value: object) -> bool:
    return type(value) is str or (
        type(value) is tuple and all(_map_key(v) for v in value)
    )


class _Decoder:
    def __init__(self, arrays: dict[str, np.ndarray]):
        self.arrays = arrays
        self.used: set[str] = set()

    def decode(self, value: object, depth: int = 0) -> object:
        if depth > MAX_DEPTH:
            _fail("encoded input nesting exceeded")
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is not dict or type(value.get("kind")) is not str:
            _fail("invalid encoded input node")
        kind = value["kind"]
        if kind == "float":
            _exact_keys(value, {"kind", "hex"}, "float")
            return _hex_float(value["hex"])
        if kind == "complex":
            _exact_keys(value, {"kind", "real", "imag"}, "complex")
            return complex(_hex_float(value["real"]), _hex_float(value["imag"]))
        if kind == "array":
            _exact_keys(value, {"kind", "id"}, "array reference")
            key = value["id"]
            if type(key) is not str or key not in self.arrays:
                _fail("unknown array reference")
            if key in self.used:
                _fail("duplicate array reference")
            self.used.add(key)
            return self.arrays[key]
        if kind in ("tuple", "list", "map"):
            _exact_keys(value, {"kind", "items"}, kind)
            if type(value["items"]) is not list:
                _fail("encoded items must be an array")
            if kind != "map":
                items = [self.decode(item, depth + 1) for item in value["items"]]
                return tuple(items) if kind == "tuple" else items
            mapping = {}
            for pair in value["items"]:
                if type(pair) is not list or len(pair) != 2:
                    _fail("map entries must be key/value pairs")
                key = self.decode(pair[0], depth + 1)
                if not _map_key(key):
                    _fail("model mapping keys must be strings or tuples of strings")
                if key in mapping:
                    _fail("duplicate encoded map key")
                mapping[key] = self.decode(pair[1], depth + 1)
            return mapping
        if kind == "object":
            _exact_keys(value, {"kind", "type", "fields"}, "object")
            name = value["type"]
            if type(name) is not str or name not in _TYPES:
                _fail("unknown object type")
            cls = _TYPES[name]
            _exact_keys(value["fields"], {f.name for f in fields(cls)}, name)
            return cls(
                **{
                    key: self.decode(item, depth + 1)
                    for key, item in value["fields"].items()
                }
            )
        _fail("unknown encoded input kind")


def _is_block(value: object) -> bool:
    return (
        type(value) is tuple and len(value) == 2 and all(type(v) is str for v in value)
    )


def _matrix_map(value: object, *, blocks: bool = False) -> bool:
    return type(value) is dict and all(
        (_is_block(k) if blocks else type(k) is str) and type(v) is np.ndarray
        for k, v in value.items()
    )


def _validate_objects(model: object, certificate: object) -> None:
    if type(model) is not FiniteControlModel:
        _fail("model must be a FiniteControlModel")
    if (
        type(model.syntax_states) is not tuple
        or not model.syntax_states
        or not all(type(s) is str for s in model.syntax_states)
        or type(model.control_dims) is not dict
        or not model.control_dims
        or not all(
            type(k) is str and type(v) is int and v > 0
            for k, v in model.control_dims.items()
        )
        or type(model.output_dim) is not int
        or model.output_dim < 1
        or type(model.actions_by_syntax) is not dict
        or not _matrix_map(model.initial_blocks)
        or type(model.reference_state) is not np.ndarray
        or not all(
            type(v) is str for v in (model.start_syntax, model.name, model.scope_note)
        )
    ):
        _fail("malformed finite-control model fields")
    for key, actions in model.actions_by_syntax.items():
        if type(key) is not str or type(actions) is not tuple:
            _fail("malformed syntax/action mapping")
        for action in actions:
            if (
                type(action) is not Action
                or type(action.name) is not str
                or type(action.codeword) is not str
                or not (action.successor is None or type(action.successor) is str)
                or type(action.continue_kraus) is not dict
                or type(action.halt_kraus) is not dict
            ):
                _fail("malformed action fields")
            for mapping, blocks in (
                (action.continue_kraus, True),
                (action.halt_kraus, False),
            ):
                for target, matrices in mapping.items():
                    if (
                        not (_is_block(target) if blocks else type(target) is str)
                        or type(matrices) is not tuple
                        or not all(type(matrix) is np.ndarray for matrix in matrices)
                    ):
                        _fail("malformed Kraus mapping")
    if type(certificate) is BellmanChoiCertificate:
        if (
            not _matrix_map(certificate.choi_envelopes, blocks=True)
            or type(certificate.constant) not in (int, float)
            or type(certificate.name) is not str
        ):
            _fail("malformed H.3 certificate fields")
    elif type(certificate) is ReferencePotentialCertificate:
        if (
            not _matrix_map(certificate.theta, blocks=True)
            or type(certificate.name) is not str
        ):
            _fail("malformed H.4 certificate fields")
        for name in ("a", "transition_coefficients", "halt_coefficients", "potential"):
            mapping = getattr(certificate, name)
            if type(mapping) is not dict:
                _fail("malformed H.4 coefficient mapping")
            for key, value in mapping.items():
                valid_key = (
                    _is_block(key)
                    if name != "transition_coefficients"
                    else type(key) is tuple
                    and len(key) == 2
                    and all(_is_block(v) for v in key)
                )
                if not valid_key or type(value) not in (int, float):
                    _fail("malformed H.4 coefficient")
    else:
        _fail("certificate must be an H.3 or H.4 proof object")


def _check_budget(
    model: FiniteControlModel, certificate: object, limits: ComputationLimits
) -> None:
    # Lazy import keeps the storage layer independent of verifier imports.
    from .limits import check_certificate_budget

    check_certificate_budget(model, certificate, limits)


def _component_hashes(model: FiniteControlModel, certificate: object) -> dict:
    return {
        "model_sha256": canonical_hash(_snapshot(model)),
        "certificate_sha256": canonical_hash(_snapshot(certificate)),
    }


def save_bundle_payload(
    path: str | Path,
    model: FiniteControlModel,
    certificate: BellmanChoiCertificate | ReferencePotentialCertificate,
    *,
    analysis: dict,
    limits: ComputationLimits = DEFAULT_LIMITS,
    overwrite: bool = False,
) -> Path:
    """Atomically save complete inputs and JSON analysis metadata.

    This function validates storage and resource contracts. Numerical proof and
    history verification belong to the higher-level analysis workflow.
    """
    if type(analysis) is not dict:
        _fail("analysis must be a JSON object")
    _bounded_json(analysis)
    encoder = _Encoder(limits)
    model_node, certificate_node = encoder.encode(model), encoder.encode(certificate)
    normalized = _Decoder(encoder.arrays)
    normalized_model = normalized.decode(model_node)
    normalized_certificate = normalized.decode(certificate_node)
    _validate_objects(normalized_model, normalized_certificate)
    _check_budget(normalized_model, normalized_certificate, limits)
    total_bytes = sum(d["nbytes"] for d in encoder.descriptors.values())
    if total_bytes > MAX_UNCOMPRESSED_BYTES - MAX_MANIFEST_BYTES:
        _fail("uncompressed array byte budget exceeded")
    payloads = {}
    for key, array in encoder.arrays.items():
        if not np.isfinite(array).all():
            _fail("nonfinite matrix entry")
        descriptor = encoder.descriptors[key]
        raw = array.astype(np.dtype(descriptor["storage_dtype"]), copy=False).tobytes(
            order="C"
        )
        descriptor["sha256"] = hashlib.sha256(raw).hexdigest()
        payloads[descriptor["path"]] = raw
    manifest = {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "producer": {
            "package": "rcc-refcert",
            "version": __version__,
            "numpy": np.__version__,
            "python": platform.python_version(),
        },
        "model": model_node,
        "certificate": certificate_node,
        "arrays": encoder.descriptors,
        "analysis": analysis,
        "component_hashes": _component_hashes(normalized_model, normalized_certificate),
    }
    manifest["manifest_sha256"] = ""
    _bounded_json(manifest)
    manifest["manifest_sha256"] = _json_hash(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    raw_manifest = _json_bytes(manifest)
    if len(raw_manifest) > MAX_MANIFEST_BYTES:
        _fail("manifest byte budget exceeded")
    destination = Path(path)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".rcc-bundle-", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            with zipfile.ZipFile(
                stream, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr("manifest.json", raw_manifest)
                for member, raw in payloads.items():
                    archive.writestr(member, raw)
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.getsize(temp_name) > MAX_ARCHIVE_BYTES:
            _fail("archive byte budget exceeded")
        if overwrite:
            os.replace(temp_name, destination)
        else:
            # An exclusive hard link avoids a check-then-replace race.
            os.link(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return destination


def _read_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, expected: int
) -> bytes:
    if info.file_size != expected:
        _fail(f"member size differs from manifest: {info.filename}")
    with archive.open(info) as member:
        raw = member.read(expected + 1)
    if len(raw) != expected:
        _fail(f"member length differs from manifest: {info.filename}")
    return raw


def _preflight_directory(stream) -> None:
    """Bound central-directory entries before ZipFile constructs its objects."""
    size = os.fstat(stream.fileno()).st_size
    if size < 22:
        _fail("archive is missing its end record")
    stream.seek(size - 22)
    end = stream.read(22)
    signature, disk, start_disk, disk_count, count, directory_size, offset, comment = (
        struct.unpack("<4s4H2LH", end)
    )
    if (
        signature != b"PK\x05\x06"
        or disk
        or start_disk
        or comment
        or disk_count != count
        or count > MAX_MEMBERS
        or count == 65535
        or offset == 2**32 - 1
        or offset + directory_size != size - 22
    ):
        _fail("unsupported or oversized archive directory")
    if directory_size > MAX_MEMBERS * 256:
        _fail("archive directory byte budget exceeded")
    stream.seek(offset)
    seen = 0
    consumed = 0
    while consumed < directory_size:
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            _fail("invalid central directory")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", header, 28)
        if name_size > 64 or extra_size > 128 or comment_size:
            _fail("unsupported central-directory metadata")
        skip = name_size + extra_size + comment_size
        if consumed + 46 + skip > directory_size:
            _fail("truncated central-directory entry")
        stream.seek(skip, 1)
        consumed += 46 + skip
        seen += 1
        if seen > MAX_MEMBERS:
            _fail("archive member budget exceeded")
    if seen != count:
        _fail("central-directory entry count mismatch")
    stream.seek(0)


def _load(archive: zipfile.ZipFile, limits: ComputationLimits) -> BundlePayload:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        _fail("archive member budget exceeded")
    names = [info.filename for info in infos]
    if len(set(names)) != len(names):
        _fail("duplicate archive member")
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        _fail("uncompressed archive byte budget exceeded")
    for info in infos:
        if info.filename != "manifest.json" and not re.fullmatch(
            r"arrays/a[0-9]{6}\.bin", info.filename
        ):
            _fail("unexpected or unsafe archive path")
        mode = info.external_attr >> 16
        if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
            _fail("archive member must be a regular file")
        if info.flag_bits & 1 or info.compress_type not in (
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
        ):
            _fail("unsupported encrypted or compressed archive member")
    by_name = {info.filename: info for info in infos}
    if "manifest.json" not in by_name:
        _fail("missing manifest.json")
    manifest_info = by_name["manifest.json"]
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        _fail("manifest byte budget exceeded")
    manifest = _read_json(_read_member(archive, manifest_info, manifest_info.file_size))
    _exact_keys(
        manifest,
        {
            "format",
            "schema_version",
            "producer",
            "model",
            "certificate",
            "arrays",
            "analysis",
            "component_hashes",
            "manifest_sha256",
        },
        "manifest",
    )
    if (
        manifest["format"] != FORMAT
        or type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != SCHEMA_VERSION
    ):
        _fail("unsupported analysis-bundle schema")
    _exact_keys(
        manifest["producer"], {"package", "version", "numpy", "python"}, "producer"
    )
    if manifest["producer"]["package"] != "rcc-refcert" or not all(
        type(v) is str and v for v in manifest["producer"].values()
    ):
        _fail("malformed producer identity")
    unsigned = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if manifest["manifest_sha256"] != _json_hash(unsigned):
        _fail("manifest integrity hash mismatch")
    if type(manifest["analysis"]) is not dict or type(manifest["arrays"]) is not dict:
        _fail("analysis and arrays must be objects")
    _exact_keys(
        manifest["component_hashes"],
        {"model_sha256", "certificate_sha256"},
        "component hashes",
    )
    if not all(
        type(v) is str and _SHA256.fullmatch(v)
        for v in manifest["component_hashes"].values()
    ):
        _fail("invalid component hash")
    descriptors = manifest["arrays"]
    placeholders = {}
    elements = 0
    expected_names = {"manifest.json"}
    for key, descriptor in descriptors.items():
        if not _ARRAY_ID.fullmatch(key):
            _fail("invalid array identifier")
        _exact_keys(
            descriptor,
            {"path", "shape", "dtype", "storage_dtype", "nbytes", "sha256"},
            "array descriptor",
        )
        if descriptor["path"] != f"arrays/{key}.bin":
            _fail("array path differs from its identifier")
        dtype = _dtype(descriptor["dtype"])
        if descriptor["storage_dtype"] != dtype.newbyteorder("<").str:
            _fail("array storage dtype is not canonical little endian")
        shape = descriptor["shape"]
        if (
            type(shape) is not list
            or len(shape) != 2
            or not all(type(d) is int and 0 < d <= 2**31 - 1 for d in shape)
        ):
            _fail("array shape must contain two bounded positive dimensions")
        count = math.prod(shape)
        elements += count
        if elements > limits.max_matrix_elements:
            raise ResourceLimitError(
                "bundle_input_elements", elements, limits.max_matrix_elements
            )
        nbytes = descriptor["nbytes"]
        if type(nbytes) is not int or nbytes != count * dtype.itemsize:
            _fail("array shape, dtype and byte count disagree")
        if type(descriptor["sha256"]) is not str or not _SHA256.fullmatch(
            descriptor["sha256"]
        ):
            _fail("invalid array hash")
        if (
            descriptor["path"] not in by_name
            or by_name[descriptor["path"]].file_size != nbytes
        ):
            _fail("array is missing or has an incorrect byte count")
        expected_names.add(descriptor["path"])
        # A zero-stride view represents the dimensions without allocating a matrix.
        placeholders[key] = np.broadcast_to(np.zeros((), dtype=dtype), tuple(shape))
    if set(names) != expected_names:
        _fail("archive contains unlisted arrays")
    preview = _Decoder(placeholders)
    model = preview.decode(manifest["model"])
    certificate = preview.decode(manifest["certificate"])
    if preview.used != set(descriptors):
        _fail("manifest contains unused arrays")
    _validate_objects(model, certificate)
    _check_budget(model, certificate, limits)
    arrays = {}
    for key, descriptor in descriptors.items():
        raw = _read_member(archive, by_name[descriptor["path"]], descriptor["nbytes"])
        if hashlib.sha256(raw).hexdigest() != descriptor["sha256"]:
            _fail("array integrity hash mismatch")
        array = np.frombuffer(raw, dtype=np.dtype(descriptor["storage_dtype"])).reshape(
            descriptor["shape"]
        )
        if not np.isfinite(array).all():
            _fail("nonfinite matrix entry")
        arrays[key] = array.astype(np.dtype(descriptor["dtype"]), copy=True)
    decoder = _Decoder(arrays)
    model, certificate = (
        decoder.decode(manifest["model"]),
        decoder.decode(manifest["certificate"]),
    )
    if _component_hashes(model, certificate) != manifest["component_hashes"]:
        _fail("model or certificate identity hash mismatch")
    return BundlePayload(model, certificate, manifest["analysis"], manifest)


def load_bundle_payload(
    path: str | Path,
    *,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> BundlePayload:
    """Load bounded data, preserving inputs without running numerical verification."""
    source = Path(path)
    with source.open("rb") as stream:
        if os.fstat(stream.fileno()).st_size > MAX_ARCHIVE_BYTES:
            _fail("archive byte budget exceeded")
        try:
            _preflight_directory(stream)
            with zipfile.ZipFile(stream) as archive:
                return _load(archive, limits)
        except (
            zipfile.BadZipFile,
            zlib.error,
            EOFError,
            RuntimeError,
            OverflowError,
        ) as exc:
            raise BundleFormatError("invalid archive bytes") from exc
