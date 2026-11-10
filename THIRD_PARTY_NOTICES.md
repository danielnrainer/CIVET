# Third-Party Notices

CIVET itself is licensed under the BSD 3-Clause License (see [LICENSE](LICENSE)).
The pre-built CIVET executables bundle the third-party components listed below, which remain
under their own licences.

## Qt for Python (PySide6, Shiboken6) and the Qt libraries

- **Licence:** GNU Lesser General Public License v3 (LGPL-3.0). The LGPL-3.0 adds terms to the
  GNU General Public License v3, so both texts are included:
  [licenses/LGPL-3.0.txt](licenses/LGPL-3.0.txt) and [licenses/GPL-3.0.txt](licenses/GPL-3.0.txt).
- **Copyright:** The Qt Company Ltd. and other contributors.
- **Source code:** https://code.qt.io/cgit/pyside/pyside-setup.git (PySide6/Shiboken6) and
  https://code.qt.io/cgit/qt/ (Qt). Prebuilt wheels: https://pypi.org/project/PySide6/
  The exact PySide6 and Qt versions bundled in a given CIVET release are shown under
  **Help → About** and in that release's notes. If you cannot get the source code for that
  version from the links above, open an issue at https://github.com/danielnrainer/CIVET/issues
  and it will be provided.
- **Use in CIVET:** CIVET uses PySide6 and the Qt libraries without modification, and only
  through their public API (via the [qtpy](https://github.com/spyder-ide/qtpy) abstraction
  layer).

### Using your own version of PySide6/Qt

The LGPL lets you run CIVET with a modified or different version of PySide6/Qt. You can do this
in any of these ways:

1. **Run from source.** CIVET's complete source code is available at
   https://github.com/danielnrainer/CIVET. Install any compatible PySide6 build you like (for
   example `pip install ./your-pyside6.whl`), then run `python src/main.py`.
2. **Build a one-folder executable.** Run `pyinstaller CIVET.spec` with the environment variable
   `CIVET_ONEDIR=1` set. This produces `dist/CIVET/`, where the PySide6/Qt libraries are separate
   files that you can replace.
3. **Rebuild the standard executable** with `pyinstaller CIVET.spec` after installing your own
   PySide6 build.

## qtpy

- **Licence:** MIT License. Copyright © 2011- The Spyder Development Team.
- **Source code:** https://github.com/spyder-ide/qtpy

## requests (and its dependencies urllib3, idna, charset-normalizer, certifi)

- **Licences:** requests: Apache License 2.0. urllib3, charset-normalizer: MIT. idna: BSD
  3-Clause. certifi: MPL-2.0.
- **Source code:** https://github.com/psf/requests

## Python

- **Licence:** Python Software Foundation License Version 2.
- **Source code:** https://www.python.org/
