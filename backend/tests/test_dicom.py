from PIL import Image

from app.services.dicom import (
    extract_metadata,
    generate_preview,
    is_valid_dicom,
    process_dicom_file,
)


def test_is_valid_dicom(sample_dicom, tmp_path):
    assert is_valid_dicom(sample_dicom) is True
    bogus = tmp_path / "notdicom.bin"
    bogus.write_bytes(b"this is not a dicom file")
    assert is_valid_dicom(bogus) is False


def test_extract_metadata(sample_dicom):
    meta = extract_metadata(sample_dicom)
    assert meta.modality == "CR"
    assert meta.body_part == "CHEST"
    assert meta.accession_number == "ACC001"
    assert meta.study_date == "20260101"
    assert meta.patient_id == "TEST123"
    assert meta.study_instance_uid


def test_generate_preview(sample_dicom, tmp_path):
    out = tmp_path / "preview.jpg"
    generate_preview(sample_dicom, out, max_size=128)
    assert out.exists()
    with Image.open(out) as img:
        assert img.format == "JPEG"
        assert max(img.size) <= 128


def test_process_dicom_file(sample_dicom, tmp_path):
    out = tmp_path / "p.jpg"
    meta = process_dicom_file(sample_dicom, out)
    assert meta.modality == "CR"
    assert out.exists()
