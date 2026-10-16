"""Looks inside a ZIP file without unpacking anything.

Run: python zipcheck.py FILE.zip
Exit code: 0 = no problem found in performed checks, 1 = problem found,
2 = could not read or refused filesystem input.
Read-only, not a malware scanner or safe-extraction guarantee.
ZIP checksum testing decompresses data and can use CPU, memory and time.
Declared sizes are untrusted; the 200 MiB skip is not a security limit.
Keep the tree still. Filesystem links/reparse points and hardlinks are refused;
no protection against hostile concurrent changes is promised.
"""
import sys
import zipfile
from pathlib import PurePosixPath, Path
import os
import stat

# The test below reads every file inside the archive, so skip it for a very
# large archive (by the sizes the ZIP file itself declares).
TEST_LIMIT = 200 * 1024 * 1024


def odd_name(name):
    """Return a reason if a stored name could point outside a folder, else None."""
    flat = name.replace("\\", "/")
    if flat.startswith("/") or (len(flat) > 1 and flat[1] == ":"):
        return "starts like an absolute path"
    if ".." in PurePosixPath(flat).parts:
        return "contains .."
    return None


def regular_input(path):
    """Reject links, reparse points, special files and hard-linked inputs.

    This check is not a hostile-race guarantee. Keep the file/tree still.
    """
    path = Path(path).absolute()
    if ".." in path.parts:
        raise OSError("Parent-traversal input paths are not supported.")
    for part in [*reversed(path.parents), path]:
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise OSError("Links/reparse points are not supported.")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
        raise OSError("Input must be an ordinary, singly linked regular file.")
    return path


def check(path):
    path = regular_input(path)
    open(path, "rb").close()  # a missing or unreadable file raises OSError here
    if not zipfile.is_zipfile(path):
        return {"error": "Not a ZIP file, or too damaged to open."}
    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            files = [i for i in infos if not i.is_dir()]
            declared = sum(i.file_size for i in files)
            odd = [(i.filename, odd_name(i.filename)) for i in infos if odd_name(i.filename)]
            encrypted = [i.filename for i in infos if i.flag_bits & 0x1]
            if encrypted:
                bad, tested = None, False
                note = "Some files are password protected, so their contents were not tested."
            elif declared > TEST_LIMIT:
                bad, tested = None, False
                note = "The declared size is over 200 MB, so the contents were not tested."
            else:
                bad, tested = z.testzip(), True
                note = ""
            return {"error": None, "files": len(files), "folders": len(infos) - len(files),
                    "declared": declared, "packed": sum(i.compress_size for i in files),
                    "odd": odd, "encrypted": encrypted, "tested": tested, "bad": bad,
                    "note": note, "names": [i.filename for i in infos]}
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError) as e:
        return {"error": "Could not read inside it: " + str(e)}


def report(r):
    if r["error"]:
        print(r["error"])
        return 1
    print("Files:", r["files"], " Folders:", r["folders"])
    print("Declared size when unpacked:", r["declared"], "bytes. Stored size:", r["packed"], "bytes.")
    for name in r["names"][:10]:
        print("  " + name)
    if len(r["names"]) > 10:
        print("  ... and", len(r["names"]) - 10, "more. Showing the first 10.")
    problems = 0
    for name, why in r["odd"]:
        print("Unusual name:", repr(name), why)
        problems += 1
    if r["tested"]:
        if r["bad"] is not None:
            print("Damaged: the first bad file is", repr(r["bad"]))
            problems += 1
        else:
            print("Python's test found no bad file (it checks each file against its stored checksum).")
    else:
        print(r["note"])
    if r["odd"]:
        print("Do not unpack this unless you know where it came from.")
    if r["tested"] and r["bad"] is not None:
        print("Get a fresh copy of the file if you can.")
    if problems:
        return 1
    print("Nothing was unpacked or changed.")
    return 0


def main(argv):
    if len(argv) != 2:
        print("Usage: python zipcheck.py FILE.zip")
        return 2
    try:
        r = check(argv[1])
    except OSError as e:
        print("Could not read the file:", e)
        return 2
    return report(r)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
