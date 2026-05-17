# Offline wheel bundle

`whisper-dictate/client/wheels.tar.gz` is a pip-downloaded snapshot of all client dependencies, built for **macOS arm64 / Python 3.13**. It lets the corp Mac install without hitting pypi (which Zscaler often blocks).

## Use

On the target Mac:

```bash
cd whisper-dictate/client
tar xzf wheels.tar.gz
python3 -m venv .venv && source .venv/bin/activate
pip install --no-index --find-links=wheels -r requirements.txt
```

## Rebuild

When `requirements.txt` changes, or for a different target (different Python version, x86_64, etc.):

```bash
cd whisper-dictate/client
rm -rf wheels wheels.tar.gz
pip download -r requirements.txt -d wheels \
  --platform macosx_11_0_arm64 \
  --python-version 3.13 \
  --only-binary=:all:
tar czf wheels.tar.gz wheels/
# commit wheels.tar.gz; `wheels/` is gitignored
```

Adjust `--platform` and `--python-version` to match the target Mac's `uname -m` and `python3 --version`. Common targets:

- macOS Apple Silicon, Python 3.13: `--platform macosx_11_0_arm64 --python-version 3.13`
- macOS Apple Silicon, Python 3.12: `--platform macosx_11_0_arm64 --python-version 3.12`
- macOS Intel, Python 3.13: `--platform macosx_10_13_x86_64 --python-version 3.13`

## Notes

- Run `pip download` on a Mac where pypi works.
- `--only-binary=:all:` forces prebuilt wheels — fails fast if any dep needs source build.
- Tarball is ~17 MB. Well under GitHub's 100 MB file limit.
