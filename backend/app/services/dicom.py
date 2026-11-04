"""DICOM metadata extraction and compressed-preview generation.

These operations are CPU-heavy (pixel decoding, resizing). To keep the ASGI event
loop responsive during chunked uploads, callers run :func:`process_dicom_file`
off the event loop — either via ``asyncio.to_thread`` or, in a request, by
scheduling it on FastAPI ``BackgroundTasks`` (see the upload router, added in the
imaging-upload iteration). The synchronous functions below do the actual work and
are independently unit-testable.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

try:  # pydicom 3.x location
    from pydicom.pixels import apply_voi_lut
except ImportError:  # pragma: no cover - older pydicom fallback
    from pydicom.pixel_data_handlers.util import apply_voi_lut


@dataclass(slots=True)
class DicomMetadata:
    """The subset of DICOM tags the MVP surfaces in the worklist."""

    modality: str | None = None
    study_date: str | None = None
    body_part: str | None = None
    accession_number: str | None = None
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None
    sop_instance_uid: str | None = None
    patient_id: str | None = None


def is_valid_dicom(path: str | Path) -> bool:
    """Return True if the file parses as DICOM (validity gate for uploads)."""
    try:
        dcmread(str(path), stop_before_pixels=True, force=False)
        return True
    except (InvalidDicomError, FileNotFoundError, ValueError):
        return False


def extract_metadata(path: str | Path) -> DicomMetadata:
    """Read header tags without decoding pixel data."""
    ds = dcmread(str(path), stop_before_pixels=True)
    return DicomMetadata(
        modality=ds.get("Modality"),
        study_date=ds.get("StudyDate"),
        body_part=ds.get("BodyPartExamined"),
        accession_number=ds.get("AccessionNumber"),
        study_instance_uid=ds.get("StudyInstanceUID"),
        series_instance_uid=ds.get("SeriesInstanceUID"),
        sop_instance_uid=ds.get("SOPInstanceUID"),
        patient_id=ds.get("PatientID"),
    )


def generate_preview(
    path: str | Path,
    output_path: str | Path,
    max_size: int = 1024,
    quality: int = 72,
) -> str:
    """Render a DICOM image to a compressed JPEG preview for low-bandwidth viewing.

    Applies VOI LUT/windowing, normalizes to 8-bit, downsizes to ``max_size`` on
    the longest edge, and writes a progressive JPEG. Returns the output path.
    """
    ds = dcmread(str(path))
    arr = ds.pixel_array

    # Multi-frame / 3D volume: take the middle slice for the preview.
    if arr.ndim == 3 and arr.shape[-1] not in (3, 4):
        arr = arr[arr.shape[0] // 2]

    # Apply windowing when present for a clinically reasonable preview.
    try:
        arr = apply_voi_lut(arr, ds)
    except Exception:  # noqa: BLE001 - windowing is best-effort for a preview
        pass

    # MONOCHROME1 is inverted (min = white); flip so bone/air read naturally.
    if ds.get("PhotometricInterpretation") == "MONOCHROME1":
        arr = np.amax(arr) - arr

    arr = arr.astype(np.float32)
    lo, hi = float(np.min(arr)), float(np.max(arr))
    if hi > lo:
        arr = (arr - lo) / (hi - lo) * 255.0
    else:
        arr = np.zeros_like(arr)
    arr = arr.astype(np.uint8)

    image = Image.fromarray(arr)
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")
    image.thumbnail((max_size, max_size))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return str(out)


def generate_image_preview(
    path: str | Path,
    output_path: str | Path,
    max_size: int = 1024,
    quality: int = 72,
) -> str:
    """Compressed JPEG preview for a non-DICOM raster image (PNG/JPEG)."""
    image = Image.open(str(path))
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")
    image.thumbnail((max_size, max_size))
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return str(out)


def is_valid_image(path: str | Path) -> bool:
    """Return True if the file is a readable raster image (validity gate)."""
    try:
        with Image.open(str(path)) as img:
            img.verify()
        return True
    except Exception:  # noqa: BLE001
        return False


def process_dicom_file(
    source_path: str | Path, preview_path: str | Path
) -> DicomMetadata:
    """Synchronous pipeline: extract metadata + generate preview. Thread-friendly."""
    metadata = extract_metadata(source_path)
    generate_preview(source_path, preview_path)
    return metadata


async def process_dicom_file_async(
    source_path: str | Path, preview_path: str | Path
) -> DicomMetadata:
    """Run the CPU-heavy pipeline in a worker thread to avoid blocking the loop."""
    return await asyncio.to_thread(process_dicom_file, source_path, preview_path)
