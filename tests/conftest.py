"""공용 pytest 설정 (Lead 소유). 역할별 fixture는 각자 test 파일 안에 둔다."""

import pytest

from contracts.deps import DataPaths


@pytest.fixture
def data_paths(tmp_path) -> DataPaths:
    """빈 COACH_DATA_DIR. 실제 data/를 건드리지 않는다."""
    (tmp_path / "docs").mkdir()
    return DataPaths(tmp_path)
