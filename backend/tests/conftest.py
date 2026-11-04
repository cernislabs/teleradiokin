"""Shared pytest fixtures."""
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_storage
from app.infrastructure.database import get_session
from app.infrastructure.models import Base
from app.infrastructure.storage import LocalFilesystemStorage
from app.main import create_app


@pytest.fixture
async def _engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def _maker(_engine):
    return async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(_maker):
    async with _maker() as session:
        yield session


@pytest.fixture
def tmp_storage(tmp_path):
    return LocalFilesystemStorage(str(tmp_path / "storage"))


@pytest.fixture
def app(_maker, tmp_storage):
    application = create_app()

    async def _override_get_session():
        async with _maker() as session:
            yield session

    application.dependency_overrides[get_session] = _override_get_session
    application.dependency_overrides[get_storage] = lambda: tmp_storage
    # Background tasks use the test DB + storage.
    application.state.session_factory = _maker
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _build_dicom_dataset():
    ds = Dataset()
    ds.PatientID = "TEST123"
    ds.Modality = "CR"
    ds.StudyDate = "20260101"
    ds.BodyPartExamined = "CHEST"
    ds.AccessionNumber = "ACC001"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.1"

    rng = np.random.default_rng(42)
    pixels = (rng.random((32, 32)) * 4095).astype(np.uint16)
    ds.Rows, ds.Columns = 32, 32
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 16
    ds.BitsStored = 12
    ds.HighBit = 11
    ds.PixelRepresentation = 0
    ds.PixelData = pixels.tobytes()

    fm = FileMetaDataset()
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta = fm
    return ds


@pytest.fixture
def sample_dicom(tmp_path):
    """Write a minimal valid single-frame MONOCHROME2 DICOM and return its path."""
    path = tmp_path / "sample.dcm"
    _build_dicom_dataset().save_as(str(path), enforce_file_format=True)
    return path


@pytest.fixture
def sample_dicom_bytes():
    """Return bytes of a minimal valid DICOM (for upload tests)."""
    import io

    buffer = io.BytesIO()
    _build_dicom_dataset().save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


@pytest.fixture
def sample_png_bytes():
    """Return bytes of a small valid PNG (for non-DICOM image upload tests)."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (48, 48), (30, 90, 160)).save(buffer, format="PNG")
    return buffer.getvalue()
