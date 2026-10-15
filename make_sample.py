"""Makes four small made-up ZIP files to practise on.

Run: python make_sample.py
"""
import zipfile
from pathlib import Path


def build(path, entries):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for name, data in entries:
            z.writestr(name, data)


def make(folder):
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    notes = [("notes/a.txt", "first note\n" * 20), ("notes/b.txt", "second note\n" * 20)]
    build(folder / "good.zip", notes)
    build(folder / "unsafe.zip", [("../outside.txt", "x\n"), ("/rooted.txt", "y\n")] + notes[:1])
    build(folder / "damaged.zip", notes)
    raw = bytearray((folder / "damaged.zip").read_bytes())
    at = raw.index(b"second note")
    raw[at] ^= 0x01  # change one letter inside the second file
    (folder / "damaged.zip").write_bytes(bytes(raw))
    (folder / "fake.zip").write_text("This is plain text with a .zip name.\n", encoding="utf-8")
    return folder


if __name__ == "__main__":
    make("sample")
    print("Made sample/good.zip, unsafe.zip, damaged.zip and fake.zip")
