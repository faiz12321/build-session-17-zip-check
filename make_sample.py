"""Makes four small made-up ZIP files to practise on.

Run: python make_sample.py
Creates only a NEW sample folder and exclusive fictional outputs.
An interrupted setup may leave a partial new folder. Use another new lesson
folder rather than deleting old data to force a retry.
"""
import io
import os
import stat
import zipfile
from pathlib import Path


def build(path, entries):
    with zipfile.ZipFile(path, "x", zipfile.ZIP_STORED) as z:
        for name, data in entries:
            z.writestr(name, data)


def make(folder):
    folder = Path(folder).absolute()
    if ".." in folder.parts:
        raise OSError("Parent-traversal setup paths are not supported.")
    for parent in reversed(folder.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise OSError("Linked/reparse parents are not supported.")
    folder.mkdir()
    notes = [("notes/a.txt", "first note\n" * 20), ("notes/b.txt", "second note\n" * 20)]
    build(folder / "good.zip", notes)
    build(folder / "unsafe.zip", [("../outside.txt", "x\n"), ("/rooted.txt", "y\n")] + notes[:1])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as z:
        for name, data in notes:
            z.writestr(name, data)
    raw = bytearray(buffer.getvalue())
    at = raw.index(b"second note")
    raw[at] ^= 0x01  # change one letter inside the second file
    with (folder / "damaged.zip").open("xb") as handle:
        handle.write(raw)
    with (folder / "fake.zip").open("x", encoding="utf-8") as handle:
        handle.write("This is plain text with a .zip name.\n")
    return folder


if __name__ == "__main__":
    try:
        make(Path(__file__).absolute().parent / "sample")
    except FileExistsError:
        raise SystemExit("Stopped: sample already exists. Nothing was replaced or deleted.")
    print("Made sample/good.zip, unsafe.zip, damaged.zip and fake.zip")
