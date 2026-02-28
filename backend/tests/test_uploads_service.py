from pathlib import Path

from app.core.config import Settings
from app.features.uploads.service import UploadsService, sanitize_filename


def test_sanitize_filename_blocks_path_traversal_and_special_chars() -> None:
    assert sanitize_filename("../my cat?.png") == "my_cat.png"
    assert sanitize_filename("..\\evil.gif") == "evil.gif"
    assert sanitize_filename("..") == "file"
    assert sanitize_filename("котик.png") == "file.png"
    assert sanitize_filename("_____") == "file"


def test_unique_filename_generation(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    (uploads_dir / "image.png").write_bytes(b"one")
    (uploads_dir / "image-1.png").write_bytes(b"two")

    settings = Settings(uploads_dir=str(uploads_dir))
    service = UploadsService(settings=settings)

    assert service._build_unique_filename("image.png") == "image-2.png"


def test_rename_uploaded_file_keeps_extension_and_uniqueness(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    (uploads_dir / "cat.png").write_bytes(b"img")
    (uploads_dir / "new_name.png").write_bytes(b"existing")

    settings = Settings(uploads_dir=str(uploads_dir))
    service = UploadsService(settings=settings)

    renamed = service.rename_uploaded_file(filename="cat.png", new_filename="new name")

    assert renamed.filename == "new_name-1.png"
    assert (uploads_dir / "new_name-1.png").exists()


def test_delete_uploaded_file(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / "to_delete.png"
    target.write_bytes(b"img")

    settings = Settings(uploads_dir=str(uploads_dir))
    service = UploadsService(settings=settings)

    deleted = service.delete_uploaded_file("to_delete.png")

    assert deleted.deleted is True
    assert deleted.filename == "to_delete.png"
    assert not target.exists()
