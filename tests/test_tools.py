"""Unit tests (stdlib unittest). Run: python -m unittest discover -s tests"""
import base64
import unittest

from tools import bech32, cctp
from risk.model import score_graph


class Bech32Tests(unittest.TestCase):
    def test_bip173_vectors(self):
        for v in ["A12UEL5L", "an83characterlonghumanreadablepartthatcontainsthenumber1andtheexcludedcharactersbio1tt5tgs",
                  "abcdef1qpzry9x8gf2tvdw0s3jn54khce6mua7lmqqqxw", "split1checkupstagehandshakeupstreamerranterredcaperred2y9e3w"]:
            bech32.decode(v)  # must not raise

    def test_bad_checksum(self):
        with self.assertRaises(ValueError):
            bech32.decode("juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea1")

    def test_same_key_across_chains(self):
        juno = "juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0"
        self.assertEqual(bech32.convert(juno, "noble"), "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za")
        self.assertEqual(bech32.convert(juno, "osmo"), "osmo1pqardc39d558mr58nx5m2wgmy448pv9487ajvp")
        self.assertTrue(bech32.same_key(juno, "neutron1pqardc39d558mr58nx5m2wgmy448pv94t68qq5"))
        self.assertFalse(bech32.same_key(juno, "secret1j2n0znmwyy95jc8auvdr7ydk05ff97sgd8t7rn"))

    def test_contract_payload_is_not_a_key(self):
        c = "neutron1zlf3hutsa4qnmue53lz2tfxrutp8y2e3rj4nkghg3rupgl4mqy8s5jgxsn"
        self.assertEqual(len(bech32.decode(c)[1]), 32)
        self.assertFalse(bech32.same_key(c, bech32.convert(c, "cosmos")))


class CCTPTests(unittest.TestCase):
    def test_outbound_solana_recipient(self):
        msg = {"from": "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za", "amount": "3115769", "destination_domain": 5,
               "mint_recipient": "Anv2vC3EMcIaGG3yDh4W47XlGb9dAQNCvhIsIKOGKlc=",
               "destination_caller": "T6iiTX0dDAj20/FvjjtLKCjtLcy5XQ4dTO6NFHPaG1U="}
        d = cctp.decode_deposit_for_burn(msg)
        self.assertEqual(d["mint_recipient"], "AhT5WaWAAoMF48nPssaSFEoygCfsq1N2qq7BTUJqEer")
        self.assertEqual(d["destination_caller"], "6MxMEeH2MQTjk7Cd4JDbJSnTvtpoKJuv374KpQYKJ3Rv")

    def test_outbound_ethereum_recipient(self):
        msg = {"amount": "1", "destination_domain": 0, "mint_recipient": "AAAAAAAAAAAAAAAA4UkxDrixs9nEcczYGBnTk2Ifulw="}
        self.assertEqual(cctp.decode_deposit_for_burn(msg)["mint_recipient"], "0xe149310eb8b1b3d9c471ccd81819d393621fba5c")

    def test_inbound_message_sender(self):
        # Synthetic message: Solana(5) -> Noble(4), sender = 39CA... (base58), recipient = noble1pqard...
        b58decode = cctp.b58decode
        hdr = (0).to_bytes(4, "big") + (5).to_bytes(4, "big") + (4).to_bytes(4, "big") + (1).to_bytes(8, "big") + b"\0" * 96
        rec = b"\0" * 12 + bech32.decode("noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za")[1]
        body = (0).to_bytes(4, "big") + b58decode("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v") + rec + \
            (587924).to_bytes(32, "big") + b58decode("39CAqAK85xu24YbTw7LbqnphG1QqReL4PHkcmTX3v1HC")
        d = cctp.decode_message(base64.b64encode(hdr + body).decode())
        self.assertEqual(d["message_sender"], "39CAqAK85xu24YbTw7LbqnphG1QqReL4PHkcmTX3v1HC")
        self.assertEqual(d["mint_recipient"], "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za")
        self.assertEqual(d["amount"], 587924)


class RiskTests(unittest.TestCase):
    G = {"id": "t", "title": "t", "incident_time": "2026-01-02T00:00:00Z",
         "nodes": [{"address": "juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0", "flags": ["seed"]},
                   {"address": "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za"},
                   {"address": "osmo1m8wg4vxkefhs374qxmmqpyusgz289wmulex5qdwpfx7jnrxzer5s9cv83q", "entity": "infrastructure"},
                   {"address": "W1", "label": "direct receiver"},
                   {"address": "W2", "label": "second hop", "flags": ["dormant_accumulation"]},
                   {"address": "W3", "label": "resolved", "flags": ["established"], "resolution": "returned funds"}],
         "edges": [{"from": "juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0", "to": "W1", "usd": 10000},
                   {"from": "W1", "to": "W2", "usd": 9000},
                   {"from": "osmo1m8wg4vxkefhs374qxmmqpyusgz289wmulex5qdwpfx7jnrxzer5s9cv83q", "to": "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za", "usd": 1},
                   {"from": "juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0", "to": "W3", "usd": 1000}]}

    def test_rules(self):
        r = {x.address: x for x in score_graph(self.G)}
        self.assertEqual(r["juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0"].score, 100)
        self.assertEqual(r["noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za"].score, 95)      # same key
        self.assertEqual(r["osmo1m8wg4vxkefhs374qxmmqpyusgz289wmulex5qdwpfx7jnrxzer5s9cv83q"].score, 0)  # infra
        self.assertEqual(r["W1"].band, "HIGH")
        self.assertGreaterEqual(r["W2"].score, 60)                                         # taint propagates
        self.assertEqual(r["W3"].band, "RESOLVED")


if __name__ == "__main__":
    unittest.main()
