"""Unit tests for tools/chainflip.py (offline)."""
import unittest

from tools import chainflip, tron

NOTE = ("1206e092bce6dc52c38fbf7441edc8ea5b89b48a8a5a0081010164000000e092bce6dc52c38fbf7441edc8ea5b89b48a8a5a"
        "0000000000000000000000000000000000000000000000000000000000000000000000000101010101010101010101010101"
        "010101010101010101010101010101010101000000")


class ChainflipTests(unittest.TestCase):
    def test_vault_swap_note(self):
        n = chainflip.vault_swap_note(NOTE)
        b = tron.to_hex("TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ")[2:]
        self.assertEqual((n["output_asset"], n["output_chain"], n["destination"], n["ccm"]), ("TrxUsdt", "Tron", b, False))
        self.assertEqual((n["cf_parameters_version"], n["retry_duration"], n["refund_address"]), (1, 100, b))

    def test_ss58_account(self):
        self.assertEqual(chainflip.ss58("989a52719b5bac3bd736a9449060159769390e7c756f52e087a94076f0e3b41d"),
                         "cFMKZx5J8NkiJ6JxHatodMRumCnzvmVtF62FGWMnWcspg58bs")

    def test_all_batch(self):
        data = chainflip.SELECTOR_ALL_BATCH + "11" * 32 + f"{5338:064x}" + "00" * 12 + "22" * 20
        self.assertEqual(chainflip.all_batch(data)["nonce"], 5338)
        with self.assertRaises(ValueError):
            chainflip.all_batch("a9059cbb" + "00" * 96)


if __name__ == "__main__":
    unittest.main()
