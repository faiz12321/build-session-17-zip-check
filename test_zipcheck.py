import io
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import make_sample
import zipcheck


def run(path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = zipcheck.main(["zipcheck.py", str(path)])
    return code, buf.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.sample = make_sample.make(self.dir / "sample")

    def zip(self, name, entries, method=zipfile.ZIP_STORED):
        p = self.dir / name
        with zipfile.ZipFile(p, "w", method) as z:
            for n, d in entries:
                z.writestr(n, d)
        return p


class OddName(unittest.TestCase):
    def test_plain(self):
        self.assertIsNone(zipcheck.odd_name("notes/a.txt"))

    def test_dotdot(self):
        self.assertTrue(zipcheck.odd_name("../a.txt"))

    def test_dotdot_middle(self):
        self.assertTrue(zipcheck.odd_name("a/../../b.txt"))

    def test_dotdot_backslash(self):
        self.assertTrue(zipcheck.odd_name("a\\..\\b.txt"))

    def test_rooted(self):
        self.assertTrue(zipcheck.odd_name("/etc/x"))

    def test_drive(self):
        self.assertTrue(zipcheck.odd_name("C:/x.txt"))

    def test_dots_in_name_are_fine(self):
        self.assertIsNone(zipcheck.odd_name("v1..2/notes..txt"))


class Reports(Base):
    def test_good(self):
        code, out = run(self.sample / "good.zip")
        self.assertEqual(code, 0)
        self.assertIn("Files: 2", out)
        self.assertIn("found no bad file", out)
        self.assertIn("Nothing was unpacked or changed.", out)

    def test_unsafe(self):
        code, out = run(self.sample / "unsafe.zip")
        self.assertEqual(code, 1)
        self.assertIn("'../outside.txt' contains ..", out)
        self.assertIn("'/rooted.txt' starts like an absolute path", out)
        self.assertIn("Do not unpack", out)

    def test_damaged(self):
        code, out = run(self.sample / "damaged.zip")
        self.assertEqual(code, 1)
        self.assertIn("first bad file is 'notes/b.txt'", out)
        self.assertNotIn("Nothing was unpacked", out)

    def test_fake(self):
        code, out = run(self.sample / "fake.zip")
        self.assertEqual(code, 1)
        self.assertIn("Not a ZIP file", out)

    def test_truncated(self):
        raw = (self.sample / "good.zip").read_bytes()
        p = self.dir / "cut.zip"
        p.write_bytes(raw[: len(raw) // 2])
        code, out = run(p)
        self.assertEqual(code, 1)
        self.assertIn("Not a ZIP file", out)

    def test_empty_file(self):
        p = self.dir / "empty.zip"
        p.write_bytes(b"")
        code, out = run(p)
        self.assertEqual(code, 1)

    def test_empty_archive(self):
        p = self.zip("none.zip", [])
        code, out = run(p)
        self.assertEqual(code, 0)
        self.assertIn("Files: 0", out)

    def test_folder_entries_counted(self):
        p = self.zip("d.zip", [("docs/", ""), ("docs/a.txt", "hi")])
        r = zipcheck.check(p)
        self.assertEqual((r["files"], r["folders"]), (1, 1))

    def test_compressed_archive(self):
        p = self.zip("c.zip", [("a.txt", "abc" * 1000)], zipfile.ZIP_DEFLATED)
        r = zipcheck.check(p)
        self.assertEqual(r["declared"], 3000)
        self.assertLess(r["packed"], 3000)
        self.assertIsNone(r["bad"])

    def test_lists_first_ten_only(self):
        p = self.zip("many.zip", [("f%02d.txt" % i, "x") for i in range(14)])
        code, out = run(p)
        self.assertIn("f09.txt", out)
        self.assertNotIn("f10.txt", out)
        self.assertIn("and 4 more", out)

    def test_missing_file(self):
        code, out = run(self.dir / "nope.zip")
        self.assertEqual(code, 2)
        self.assertIn("Could not read", out)

    def test_usage(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = zipcheck.main(["zipcheck.py"])
        self.assertEqual(code, 2)


class Limits(Base):
    def test_large_declared_size_skips_test(self):
        p = self.zip("a.zip", [("a.txt", "hello")])
        old = zipcheck.TEST_LIMIT
        zipcheck.TEST_LIMIT = 2
        self.addCleanup(setattr, zipcheck, "TEST_LIMIT", old)
        code, out = run(p)
        self.assertIn("were not tested", out)
        self.assertNotIn("found no bad file", out)

    def test_encrypted_flag_skips_test(self):
        p = self.zip("e.zip", [("a.txt", "hello")])
        raw = bytearray(p.read_bytes())
        # set the encryption bit in the central directory entry's flags
        at = raw.index(b"PK\x01\x02") + 8
        raw[at] |= 1
        p.write_bytes(bytes(raw))
        r = zipcheck.check(p)
        self.assertFalse(r["tested"])
        self.assertEqual(r["encrypted"], ["a.txt"])


class ReadOnly(Base):
    def test_nothing_written_or_unpacked(self):
        before = sorted(p.name for p in self.dir.rglob("*"))
        for name in ("good", "unsafe", "damaged", "fake"):
            run(self.sample / (name + ".zip"))
        self.assertEqual(sorted(p.name for p in self.dir.rglob("*")), before)

    def test_unsafe_names_not_created(self):
        run(self.sample / "unsafe.zip")
        self.assertFalse((self.dir / "outside.txt").exists())
        self.assertFalse((self.sample.parent / "outside.txt").exists())

    def test_bytes_and_time_unchanged(self):
        p = self.sample / "good.zip"
        b, t = p.read_bytes(), os.stat(p).st_mtime_ns
        run(p)
        self.assertEqual(p.read_bytes(), b)
        self.assertEqual(os.stat(p).st_mtime_ns, t)


class Sample(Base):
    def test_sample_files_exist(self):
        self.assertEqual(sorted(p.name for p in self.sample.iterdir()),
                         ["damaged.zip", "fake.zip", "good.zip", "unsafe.zip"])

    def test_damaged_differs_by_one_byte(self):
        a = (self.sample / "good.zip").read_bytes()
        b = (self.sample / "damaged.zip").read_bytes()
        self.assertEqual(len(a), len(b))
        self.assertEqual(sum(x != y for x, y in zip(a, b)), 1)



class SafeSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sample = self.root / 'sample'

    def test_existing_folder_preserves_nested_bytes_and_mtime(self):
        (self.sample / 'nested').mkdir(parents=True)
        keep = self.sample / 'nested' / 'keep'
        keep.write_bytes(b'KEEP')
        before = keep.read_bytes(), keep.stat().st_mtime_ns
        with self.assertRaises(FileExistsError):
            make_sample.make(self.sample)
        self.assertEqual(before, (keep.read_bytes(), keep.stat().st_mtime_ns))

    def test_existing_file_preserved(self):
        self.sample.write_bytes(b'KEEP')
        before = self.sample.read_bytes(), self.sample.stat().st_mtime_ns
        with self.assertRaises(FileExistsError):
            make_sample.make(self.sample)
        self.assertEqual(before, (self.sample.read_bytes(), self.sample.stat().st_mtime_ns))

    def test_repeat_preserves_every_output(self):
        make_sample.make(self.sample)
        before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.sample.iterdir()}
        with self.assertRaises(FileExistsError):
            make_sample.make(self.sample)
        self.assertEqual(before, {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.sample.iterdir()})

    def test_cli_repeat_preserves_every_output(self):
        import subprocess, sys
        script = self.root / 'make_sample.py'
        shutil.copyfile(Path(make_sample.__file__).resolve(), script)
        make_sample.make(self.sample)
        before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.sample.iterdir()}
        result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('sample already exists', result.stderr)
        self.assertEqual(before, {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.sample.iterdir()})


class InputSafety(Base):
    def test_hardlink_refused_preserves_target(self):
        target = self.sample / 'good.zip'
        before = target.read_bytes(), target.stat().st_mtime_ns
        link = self.dir / 'hard.zip'
        os.link(target, link)
        code, out = run(link)
        self.assertEqual(code, 2)
        self.assertIn('singly linked', out)
        self.assertEqual(before, (target.read_bytes(), target.stat().st_mtime_ns))

    def test_directory_refused(self):
        code, out = run(self.sample)
        self.assertEqual(code, 2)
        self.assertIn('regular file', out)

    def test_fifo_refused_without_blocking(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('Unix named pipes unavailable')
        import subprocess, sys
        pipe = self.dir / 'pipe.zip'
        os.mkfifo(pipe)
        result = subprocess.run([sys.executable, str(Path(zipcheck.__file__).resolve()), str(pipe)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('regular file', result.stdout)

    def test_existing_and_dangling_file_symlinks_refused(self):
        target = self.sample / 'good.zip'
        before = target.read_bytes(), target.stat().st_mtime_ns
        link = self.dir / 'link.zip'
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        code, out = run(link)
        self.assertEqual(code, 2)
        self.assertIn('Links/reparse', out)
        link.unlink()
        missing = self.dir / 'absent.zip'
        link.symlink_to(missing)
        code, out = run(link)
        self.assertEqual(code, 2)
        self.assertFalse(missing.exists())
        self.assertEqual(before, (target.read_bytes(), target.stat().st_mtime_ns))

    def test_parent_directory_symlink_refused(self):
        link = self.dir / 'linked'
        try:
            link.symlink_to(self.sample, target_is_directory=True)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        code, out = run(link / 'good.zip')
        self.assertEqual(code, 2)
        self.assertIn('Links/reparse', out)

    def test_parent_traversal_refused(self):
        path = self.sample / '..' / 'sample' / 'good.zip'
        code, out = run(path)
        self.assertEqual(code, 2)
        self.assertIn('Parent-traversal', out)

    def test_self_loop_symlink_refused(self):
        link = self.dir / 'loop'
        try:
            link.symlink_to(link)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        code, out = run(link)
        self.assertEqual(code, 2)
        self.assertIn('Links/reparse', out)


if __name__ == "__main__":
    unittest.main()
