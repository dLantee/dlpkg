import pytest

from dlpkg.publisher import publish_folder


def test_publish_folder(tmp_path):
    # Setup a fake project structure
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text("[project]\nname = 'MyProject'\nversion = '0.1.0'")
    (project_dir / "dist").mkdir()
    (project_dir / "dist" / "my_project-0.1.0-py3-none-any.whl").write_text("fake wheel content")

    # Target directory for publishing
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    # Call the publish function
    publish_folder(project_dir, target_dir)

    # Verify that the wheel file was copied to the target directory
    published_file = target_dir / "my_project-0.1.0-py3-none-any.whl"
    assert published_file.exists()
    assert published_file.read_text() == "fake wheel content"