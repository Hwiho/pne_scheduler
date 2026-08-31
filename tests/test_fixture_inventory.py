from pathlib import Path
from zipfile import ZipFile

import pytest


EXAMPLE_ROOT = Path(__file__).resolve().parents[1] / "example"
ARCHIVE_ROOT = EXAMPLE_ROOT / "archives"
EXPECTED_ARCHIVE_COUNTS = {
    "9)Bimodal_SJ1300_6040_NCN_capacheck.zip": 8,
    "sch.zip": 93,
}
HPPC_FIXTURE = EXAMPLE_ROOT / "fixtures" / "hppc" / "HPPC_Full range.sch"


@pytest.mark.parametrize(
    ("archive_name", "expected_count"),
    EXPECTED_ARCHIVE_COUNTS.items(),
)
def test_schedule_archive_inventory(archive_name: str, expected_count: int) -> None:
    archive_path = ARCHIVE_ROOT / archive_name
    assert archive_path.is_file(), f"Missing fixture archive: {archive_path}"

    with ZipFile(archive_path) as archive:
        schedules = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename.lower().endswith(".sch")
        ]

    assert len(schedules) == expected_count
    assert all(member.file_size > 0 for member in schedules)


def test_total_reference_schedule_count() -> None:
    archive_count = 0
    for archive_name in EXPECTED_ARCHIVE_COUNTS:
        with ZipFile(ARCHIVE_ROOT / archive_name) as archive:
            archive_count += sum(
                not member.is_dir() and member.filename.lower().endswith(".sch")
                for member in archive.infolist()
            )

    assert HPPC_FIXTURE.is_file()
    assert HPPC_FIXTURE.stat().st_size > 0
    assert archive_count + 1 == 102
