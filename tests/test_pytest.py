import pathlib

def test_project_root(project_root: pathlib.Path):
    """Does the project_root fixture return a valid path?"""
    assert project_root.exists()
    assert str(project_root).endswith("mailconveyor")
