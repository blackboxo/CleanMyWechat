# Repository Guidelines

## Project Structure & Module Organization

This is a small Windows desktop utility built with Python and PyQt5. The main application entry point is `main.py`, which loads UI files and coordinates cleanup workflows. Helper modules live in `utils/`, including deletion threads, WeChat path detection, and generated Qt resources. Static UI assets, icons, `.ui` files, and Qt resource definitions are in `images/`. `config.json` is a sample/runtime configuration file. `build/` and `dist/` are PyInstaller outputs and should not be edited by hand.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app locally:

```powershell
python main.py
```

Build a Windows executable with PyInstaller:

```powershell
pyinstaller -F -i images/icon.ico -w main.py
```

After packaging, copy `images/` into `dist/` so the executable can load UI and image assets.

## Coding Style & Naming Conventions

Follow the existing Python style: 4-space indentation, PyQt classes in `PascalCase`, and functions, variables, and module files in `snake_case` or the existing mixed-case pattern used in `utils/`. Keep UI behavior in `main.py` unless a helper is clearly reusable. Avoid broad refactors when changing cleanup logic; these paths touch user files and should remain easy to review.

## Testing Guidelines

There is currently no automated test suite. For changes to deletion, path discovery, or configuration handling, add focused tests under a new `tests/` directory when practical. At minimum, run `python main.py` and manually verify account discovery, option persistence, and that deleted files go to the recycle bin via `send2trash` rather than being permanently removed.

## Commit & Pull Request Guidelines

Recent history uses short, direct messages such as `Version 2.1: fix logic and bugs` and `Update readme.md`. Keep commits concise and imperative, for example `Fix cleanup progress calculation` or `Update packaging assets`. Pull requests should describe the user-visible change, list manual verification steps, link related issues, and include screenshots or screen recordings for UI changes.

## Security & Configuration Tips

Do not commit personal WeChat paths, private account IDs, generated archives, or packaged binaries. Treat `config.json` as local runtime data unless intentionally updating the sample format. Be especially careful with cleanup code: prefer `send2trash`, validate discovered paths, and avoid permanent deletion APIs.
