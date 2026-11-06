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

    def test_usdt_blacklist_events_paginates_and_decodes(self):
        """Pages are followed via meta.links.next; _user is decoded to base58; rows sorted by time."""
        b_hex = "0x" + tron.to_hex("TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ")[2:]
        pages = {
            "p1": {"data": [{"result": {"_user": "0xd7628706bf2b6ca9f3c131b26fa18ee9292777ac"},
                             "block_timestamp": 1757700000000, "transaction_id": "aa"}],
                   "meta": {"links": {"next": tron.TRONGRID + "/p2"}}},
            "/p2": {"data": [{"result": {"_user": b_hex}, "block_timestamp": 1757600000000,
                              "transaction_id": "bb"}], "meta": {}},
        }
        calls = []

        def fake_get(path):
            calls.append(path)
            return pages["p1"] if "event_name=AddedBlackList" in path else pages.get(path, {"data": []})

        orig_get, orig_sleep = tron.get, tron.time.sleep
        tron.get, tron.time.sleep = fake_get, lambda _s: None
        try:
            rows = tron.usdt_blacklist_events("2026-09-11T00:00", "2026-11-06T00:00", names=("AddedBlackList",))
        finally:
            tron.get, tron.time.sleep = orig_get, orig_sleep
        self.assertEqual(calls[1], "/p2")
        self.assertEqual([r["txid"] for r in rows], ["bb", "aa"])
        self.assertEqual(rows[0]["user"], "TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ")
        self.assertIn("min_block_timestamp=1789084800000", calls[0])
        self.assertIn("max_block_timestamp=1793923200000", calls[0])


if __name__ == "__main__":
    unittest.main()
