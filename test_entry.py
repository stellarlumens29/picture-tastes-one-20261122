"""Tests for picture-tastes-one: PNG validity, size, dims, determinism.

Stdlib only. Run: python3 test_entry.py  (or pytest test_entry.py)
"""

import hashlib
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_BYTES = 1_048_576


def run_main(out_dir):
    env = dict(os.environ, MAKEFUN_OUTPUT_DIR=str(out_dir))
    r = subprocess.run([sys.executable, str(HERE / "main.py")],
                       env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"main.py failed: {r.stderr}"
    return Path(out_dir) / "entry.png"


def read_png_info(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG signature"
    w, h = struct.unpack(">II", data[16:24])
    assert data[12:16] == b"IHDR", "missing IHDR"
    return data, w, h


def test_png_valid_size_dims():
    with tempfile.TemporaryDirectory() as td:
        p = run_main(td)
        data, w, h = read_png_info(p)
        assert (w, h) == (1024, 1024), f"dims {(w, h)} != (1024, 1024)"
        assert len(data) <= MAX_BYTES, f"{len(data)} bytes > 1MB limit"
        print(f"OK: {len(data)} bytes, {w}x{h}")


def test_deterministic():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        pa, pb = run_main(a), run_main(b)
        ha = hashlib.sha256(pa.read_bytes()).hexdigest()
        hb = hashlib.sha256(pb.read_bytes()).hexdigest()
        assert ha == hb, f"non-deterministic: {ha} != {hb}"
        print(f"OK: deterministic sha256 {ha}")


if __name__ == "__main__":
    test_png_valid_size_dims()
    test_deterministic()
    print("ALL TESTS PASSED")
