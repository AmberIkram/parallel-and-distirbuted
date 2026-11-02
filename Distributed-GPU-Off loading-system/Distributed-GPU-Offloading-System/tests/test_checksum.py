# tests/test_checksum.py
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.utils.checksum import calculate_checksum, verify_checksum


def test_checksum_consistency():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"hello distributed GPU system")
        path = f.name
    try:
        cs1 = calculate_checksum(path)
        cs2 = calculate_checksum(path)
        assert cs1 == cs2, "Checksum must be deterministic"
    finally:
        os.unlink(path)


def test_checksum_verify_match():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"test data 1234")
        path = f.name
    try:
        cs = calculate_checksum(path)
        assert verify_checksum(path, cs), "Checksum should match"
    finally:
        os.unlink(path)


def test_checksum_verify_mismatch():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(b"test data 1234")
        path = f.name
    try:
        assert not verify_checksum(path, "deadbeef" * 8), "Wrong checksum should fail"
    finally:
        os.unlink(path)


def test_checksum_known_value():
    import hashlib
    data = b"gpu offloading benchmark"
    expected = hashlib.sha256(data).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(data)
        path = f.name
    try:
        actual = calculate_checksum(path)
        assert actual == expected
    finally:
        os.unlink(path)
