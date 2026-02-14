![A local image example](.\images\dlpkg_wallpaper.png)

# dlpkg

`dlpkg` is a command line tool to help with Python package development, versioning, building, and installation.

### Installation

Install dlpkg locally for development for your active Python environment.
From inside the `dlpkg/` repo:
```commandline
py -m pip install -e .
```


### Usage

Navigate to your package root (`cd path/to/your/package`).
The tool expects a standard Python package structure:
```
your_package/
├── src/your_package/
│   └── __init__.py
└── pyproject.toml
```

#### Bump version (patch/minor/major)

It expects the following format: `<major>.<minor>.<patch>[-<dev-tag>]`

Flags:
- --part : Specify which part of the version to bump: patch, minor, or major. (default: patch)
- --repo-root : Optional, specify the root of the git repository (default is current directory).
- --source-dir : Optional, specify the source folder name (If it is different from the package name).

```commandline
dlpkg bumpversion --part minor
dlpkg bumpversion --repo_root D:\dev\your_pacakge --source-dir your_import_dir --part major
```


#### Build distributions

Build both `sdist` and `wheel` distributions for your package.

Flags:
- --out-dir : Optional, specify the output directory for the built distributions (default: `./dist`).
- --repo-root : Optional, specify the root of the git repository (default is current directory).

```commandline
dlpkg build --out-dir dist
```

#### Install package

Install the package to a target directory with versioned folder names.
This creates: `X:\target_folder\rel-x.y.z\`

Flags:
- --target : Specify the target directory where the package should be installed.
- --channel : Optional, specify the release channel (default: rel, available: rel, dev).
- --dev-tag : Optional, specify the dev tag if installing a dev version.
- --version : Optional, override version (default: read from pyproject).
- --cleanup : Optional, do clean the build artifacts after installation (default: False).
- --repo-root : Optional, specify the root of the git repository (default is current directory).
- --source-dir : Optional, specify the source folder name (If it is different from the package name).
- --target : Specify the target directory where the package should be installed.
- --write-mod : Optional, write a mod file with the installed version and channel information (default: False).

```commandline
dlpkg install --target D:\package_publishes
dlpkg install --target D:\package_publishes --channel dev --dev-tag dev14+feature.a1b2c3d
```

### Contributing
Home page: https://github.com/dLantee/dlpkg \
Report issues here: https://github.com/dLantee/dlpkg/issues




