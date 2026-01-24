import pytest
import pathlib

@pytest.fixture
def project_root(pytestconfig: pytest.Config) -> pathlib.Path:
    """Return the project root as pathlib Path object."""
    return pytestconfig.rootpath.resolve()
