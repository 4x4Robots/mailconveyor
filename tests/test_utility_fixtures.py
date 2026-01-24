import pytest
import pathlib

@pytest.fixture
def project_root(pytestconfig: pytest.Config) -> pathlib.Path:
    """Return the project root as pathlib Path object."""
    return pytestconfig.rootpath

def test_project_root(project_root: pathlib.Path):
    """Does the project_root fixture return a valid path?"""
    assert project_root.exists()
    assert str(project_root).endswith("mailconveyor")
