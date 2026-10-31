"""Unit tests for tools/tron.py (offline, no network)."""
import unittest

from tools import tron


class TronCodecTests(unittest.TestCase):
    def test_round_trip(self):
        for a in ["TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ", "TEcDijvKSXcfWT7S6rd44H5vNgufm7Y4XC", tron.USDT]:
            self.assertEqual(tron.to_base58(tron.to_hex(a)), a)

    def test_known_usdt_hex(self):
        self.assertEqual(tron.to_hex(tron.USDT), "41a614f803b6fd780986a42c78ec9c7f77e6ded13c")

    def test_evm_style_hex_accepted(self):
        self.assertEqual(tron.to_base58("0xe092bce6dc52c38fbf7441edc8ea5b89b48a8a5a"),
                         "TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ")

    def test_bad_checksum(self):
        with self.assertRaises(ValueError):
            tron.to_hex("TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BA")

    def test_note_text(self):
        memo = "=:b:bc1qjqda2hp3yajkkm74t8j9rz7ljghfp8akyyqv55:956838369/0/4397:sto:0"
        self.assertEqual(tron.note_text(memo.encode().hex()), memo)
        # binary vault-swap notes are not text
        self.assertIsNone(tron.note_text("1206e092bce6dc52c38fbf7441edc8ea5b89b48a8a5a0081"))
        self.assertIsNone(tron.note_text(""))


if __name__ == "__main__":
    unittest.main()
