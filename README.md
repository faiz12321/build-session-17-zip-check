# Look inside a ZIP file without unpacking it

A small read-only Python tool built step by step. Give it a ZIP file and it opens it with Python's `zipfile` module, counts the files, lists the first ten names, flags names that start like an absolute path or contain `..`, and asks Python to read every file back and compare it with its stored checksum. It does not unpack anything and has no code that writes to disk.

## Run it

    python make_sample.py                  # creates four fictional files only in a NEW sample/ folder
    python zipcheck.py sample/damaged.zip  # report on one file
    python -m unittest -v                  # 37 temporary-fixture tests

On Windows, if `python` is not found, use `py`.

## Files

- `zipcheck.py` - the tool
- `make_sample.py` - makes four made-up files: a good ZIP, one with unusual names, one with a changed byte, and a text file with a .zip name
- `test_zipcheck.py` - tests

## Setup and filesystem safety

Use a new empty lesson folder. Setup refuses an existing sample file/folder,
creates outputs exclusively and never resets old data. An interruption may leave
a partial new folder. Use a different new lesson folder rather than deleting old
work to force a retry. Linked/reparse parents are refused.

The checker now refuses file/ancestor symlinks and Windows reparse points,
hard-linked inputs, folders and special filesystem entries before opening ZIP
bytes. These checks are not a hostile-race guarantee. Keep the tree still. Parent-traversal input spellings are refused.
The archive's own stored link metadata is not a safe-extraction validator.

## Notes

- It reports the first damaged file only. The checksum test is Python's `testzip()`.
- Checksum testing decompresses data and uses CPU, time and memory. Central-directory
  entries and declared sizes are untrusted; the200MiB skip is not a security limit.
  This is not a ZIP-bomb defense, malware scanner or sandbox.
- Sizes are the ones the ZIP file declares about itself. The file can be wrong about them.
- Over 200 MiB declared (the existing report labels this MB), or with password-protected files, the contents are not tested and the tool says so.
- Names are checked by simple rules: a leading slash or backslash, a drive letter, or a `..` part. Other tricks are not looked for.
- A clean report is not a safety check. It does not look at what the files contain.
- A text file renamed to .zip, and a ZIP cut in half, are both reported as "Not a ZIP file, or too damaged to open."
- Tests check that nothing is created next to the ZIP file, and that its bytes and modified time stay the same.
- Tested only on small made-up files. Python 3.10 and 3.12 on Linux, and, by GitHub Actions, Python 3.12 on Windows and Ubuntu. Not tested on a Windows 10 or 11 desktop.
- Educational example, no warranty. Use at your own risk.
- Code is MIT licensed (see LICENSE). Python is a separate project with its own license; this repository does not include it.

## Repair evidence

Four added setup collision/repeat/CLI tests and seven filesystem-input tests bring
the suite to37. Symlink tests can skip where unavailable; the Unix FIFO test
skips on Windows. Local37tests pass. Two Windows and two Ubuntu full replays pass37tests. Per-platform pairs
differ only in unittest time. Windows skips the Unix FIFO test; Ubuntu runs it.
Existing archive-check rules are preserved; filesystem-input refusal is new.

Sources:
- https://docs.python.org/3/library/zipfile.html
- https://docs.python.org/3/library/pathlib.html
- https://docs.python.org/3/library/stat.html
