import pytest
import tomlkit
from pathlib import Path


def make_pyproject_toml() -> str:
    doc = tomlkit.document()

    # -------------------------
    # [build-system]
    # -------------------------
    build_system = tomlkit.table()
    build_system.add("requires", ["setuptools>=68", "wheel"])
    build_system.add("build-backend", "setuptools.build_meta")
    doc.add("build-system", build_system)

    doc.add(tomlkit.nl())

    # -------------------------
    # [project]
    # -------------------------
    project = tomlkit.table()
    project.add("name", "my_project_name")
    project.add("version", "1.2.5")
    project.add("description", "Test package description")
    project.add("readme", "README.md")
    project.add("authors", [{"name": "John Doe", "email": "asd@qwe.com"}])
    project.add("requires-python", ">=3.11")

    deps = tomlkit.array()
    deps.multiline(True)
    deps.append("tomlkit>=0.14.0")
    project.add("dependencies", deps)

    doc.add("project", project)

    doc.add(tomlkit.nl())
    doc.add(tomlkit.nl())

    # -------------------------
    # [tool.setuptools]
    # -------------------------
    tool = tomlkit.table()
    setuptools_tbl = tomlkit.table()

    pkg_dir = tomlkit.inline_table()
    pkg_dir.add("", "src")
    setuptools_tbl.add("package-dir", pkg_dir)

    tool.add("setuptools", setuptools_tbl)
    doc.add("tool", tool)

    doc.add(tomlkit.nl())

    # -------------------------
    # [tool.setuptools.packages.find]
    # -------------------------
    packages_tbl = tomlkit.table()
    find_tbl = tomlkit.table()

    where_arr = tomlkit.array()
    where_arr.multiline(True)
    where_arr.append("src")
    find_tbl.add("where", where_arr)

    exclude_arr = tomlkit.array()
    exclude_arr.multiline(True)
    exclude_arr.extend(
        [
            "tests*",
            "docs*",
            "examples*",
            "images*",
            "README*",
            "LICENSE*",
            "*.toml",
            "dist*",
            "build*",
        ]
    )
    find_tbl.add("exclude", exclude_arr)

    packages_tbl.add("find", find_tbl)
    setuptools_tbl.add("packages", packages_tbl)

    return doc.as_string()


@pytest.fixture
def published_versions_dir(tmp_path):
    """Creates <tmp_path>/publishes/my_package/{rel,dev}-<version> folders for `dlpkg list` tests.
    Includes out-of-order versions (to verify sorting) and malformed folder names (to verify
    they're skipped).
    """
    base = tmp_path / "publishes"
    pkg_dir = base / "my_package"
    pkg_dir.mkdir(parents=True)
    for v in ["1.0.0", "1.2.5", "2.0.0", "1.9.0", "1.10.0"]:
        (pkg_dir / f"rel-{v}").mkdir()
    for v in ["1.2.3-alpha.1", "2.0.0-beta.1"]:
        (pkg_dir / f"dev-{v}").mkdir()
    (pkg_dir / "not-a-valid-format-here").mkdir()  # channel not in {rel, dev} -> skipped
    (pkg_dir / "rel-not-semver").mkdir()           # unparsable version -> skipped
    return base


@pytest.fixture
def temp_toml_package(tmp_path):
    # Create a temporary package structure
    root_dir = tmp_path / "test_package"
    root_dir.mkdir()
    src_dir = root_dir / "src"
    src_dir.mkdir()
    readme_path = root_dir / "README.md"
    readme_path.touch()
    package_dir = src_dir / "my_package"
    package_dir.mkdir()
    init_file = package_dir / "__init__.py"
    init_file.write_text("__version__ = '1.2.5'", encoding="utf-8")
    # Create pyproject.toml with the expected structure
    doc_str = make_pyproject_toml()
    pyproject = root_dir / "pyproject.toml"
    pyproject.write_text(doc_str, encoding="utf-8")
    return root_dir


# @pytest.fixture
# def temp_toml_package_missing_pyproject(tmp_path):
#     # Create a temporary package structure
#     root_dir = tmp_path / "test_package"
#     root_dir.mkdir()
#     src_dir = root_dir / "src"
#     src_dir.mkdir()
#     readme_path = root_dir / "README.md"
#     readme_path.touch()
#     init_file = src_dir / "__init__.py"
#     init_file.write_text("__version__ = '1.2.5'", encoding="utf-8")
#     return root_dir
#
# @pytest.fixture
# def temp_toml_package_multiple_src_name(tmp_path):
#     # Create a temporary package structure
#     root_dir = tmp_path / "test_package"
#     root_dir.mkdir()
#     src_dir = root_dir / "src"
#     src_dir.mkdir()
#     init_file = src_dir / "__init__.py"
#     init_file.write_text("__version__ = '1.2.5'", encoding="utf-8")
#     return root_dir