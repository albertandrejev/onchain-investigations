"""Write-up structure lint (tools/casedoc.py) and incident-graph diagrams (tools/diagrams.py)."""
import unittest
from pathlib import Path

from tools import casedoc, diagrams
from risk.model import load

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = (ROOT / "docs" / "CASE_TEMPLATE.md").read_text()
CASES = sorted(p.parent for p in (ROOT / "cases").glob("*/README.md"))


def case_text(no="07", passed=12):
    """The template filled just enough to pass as a real case."""
    return (TEMPLATE.replace("# Case NN:", f"# Case {no}:")
            .replace("| Checks | <N> passed", f"| Checks | {passed} passed")
            .replace("CN-xx", f"C{int(no)}-01"))


class TemplateTest(unittest.TestCase):
    def test_template_passes(self):
        self.assertEqual(casedoc.lint_text(TEMPLATE), [])

    def test_filled_template_passes_as_case(self):
        self.assertEqual(casedoc.lint_text(case_text(), "07", {"C7-01"}, 12), [])


class RulesTest(unittest.TestCase):
    def lint(self, text):
        return casedoc.lint_text(text, "07", {"C7-01"}, 12)

    def assertFlags(self, text, fragment):
        errs = self.lint(text)
        self.assertTrue(any(fragment in e for e in errs), f"expected '{fragment}' in {errs}")

    def test_missing_required_section(self):
        t = case_text()
        start, end = t.index("## Limitations"), t.index("## Open leads")
        self.assertFlags(t[:start] + t[end:], "missing required section '## Limitations'")

    def test_wrong_order(self):
        t = case_text()
        a, b, c = t.index("## Risk scoring"), t.index("## Confidence assessment"), t.index("## Limitations")
        swapped = t[:a] + t[b:c] + t[a:b] + t[c:]
        self.assertFlags(swapped, "must come before")

    def test_unknown_section(self):
        self.assertFlags(case_text().replace("## Open leads", "## What I would do next"), "unknown section")

    def test_subtitle_allowed(self):
        self.assertEqual(self.lint(case_text().replace("## Background (optional)", "## Background: why")), [])

    def test_case_number_must_match_folder(self):
        self.assertFlags(case_text(no="08"), "does not match the folder")

    def test_checks_count_must_match_report(self):
        self.assertFlags(case_text(passed=11), "'Checks' must start with 12")

    def test_case_card_rows(self):
        self.assertFlags(case_text().replace("| Outcome |", "| Result |"), "case card rows")

    def test_cited_id_must_exist(self):
        self.assertFlags(case_text() + "\nSee (C7-99).\n", "C7-99 is cited but is not in")

    def test_other_case_id(self):
        self.assertFlags(case_text() + "\nAs in case 01 (C1-02).\n", "another case's check")

    def test_needs_flowchart_and_timeline(self):
        t = case_text()
        no_timeline = t.replace("```mermaid\ntimeline", "```mermaid\npie")
        self.assertFlags(no_timeline, "timeline")
        no_flow = t.replace("```mermaid\nflowchart LR", "```mermaid\nsequenceDiagram")
        self.assertFlags(no_flow, "flowchart")

    def test_unknown_mermaid_type(self):
        self.assertFlags(case_text() + "\n```mermaid\nmindmap\n  root\n```\n", "unknown type 'mindmap'")

    def test_timeline_rejects_colon(self):
        self.assertFlags(case_text().replace("D Mon : HH.MM what happened\n  section Attack",
                                             "D Mon : 01:44 what happened\n  section Attack"),
                         "timeline entry cannot contain ':'")

    def test_step_numbering(self):
        self.assertFlags(case_text().replace("### 2. ", "### 3. "), "numbered 1, 2, 3")

    def test_confidence_order(self):
        t = case_text()
        a = t.index("| **Strong** |")
        b = t.index("| **Moderate** |")
        c = t.index("| **Suspicion** |")
        self.assertFlags(t[:a] + t[b:c] + t[a:b] + t[c:], "confidence levels must be in the order")

    def test_draft_title(self):
        t = case_text().replace("# Case 07:", "# [DRAFT] Case 07:")
        self.assertEqual(self.lint(t), [])
        self.assertTrue(casedoc.is_draft(t))
        self.assertFalse(casedoc.is_draft(case_text()))

    def test_draft_title_number_must_match_folder(self):
        self.assertFlags(case_text(no="08").replace("# Case 08:", "# [DRAFT] Case 08:"), "does not match the folder")

    def test_draft_label_only_as_prefix(self):
        self.assertFlags(case_text().replace("# Case 07:", "# DRAFT Case 07:"), "title must be")

    def test_index_label_matches_draft(self):
        index = ("| [[DRAFT] Case 07: X](cases/07-x/) | a |\n"
                 "| [Case 08: Y](cases/08-y/) | b |\n")
        self.assertEqual(casedoc.lint_index("07-x", True, index), [])
        self.assertEqual(casedoc.lint_index("08-y", False, index), [])
        self.assertTrue(casedoc.lint_index("07-x", False, index))
        self.assertTrue(casedoc.lint_index("08-y", True, index))
        self.assertIn("no row", casedoc.lint_index("09-z", False, index)[0])

    def test_heading_inside_code_is_ignored(self):
        t = case_text().replace("## Lessons learned", "```\n## Not a heading\n```\n\n## Lessons learned")
        self.assertEqual(self.lint(t), [])


class CasesTest(unittest.TestCase):
    def test_every_case_passes(self):
        for d in CASES:
            with self.subTest(case=d.name):
                self.assertEqual(casedoc.lint_case(d), [])


class DiagramsTest(unittest.TestCase):
    def test_short(self):
        self.assertEqual(diagrams.short("neutron1dd25c4sshelrpfs0433apg24c5phrhk8l6n605"), "neutron1dd25c…n605")
        self.assertEqual(diagrams.short("0x9c7a63fadc892df1236f959f76cd0f686de14697"), "0x9c7a…4697")
        self.assertEqual(diagrams.short("TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ"), "TWSe9Z…o2BZ")

    def test_escape(self):
        self.assertEqual(diagrams.esc('wallet #1 "x" <y>'), "wallet #35;1 #quot;x#quot; #lt;y#gt;")

    def test_deterministic_and_complete(self):
        for d in CASES:
            g = load(d)
            with self.subTest(case=d.name):
                a, b = diagrams.render_markdown(g), diagrams.render_markdown(g)
                self.assertEqual(a, b)
                self.assertEqual(a.count('["'), len(g["nodes"]) + a.count("subgraph"))
                self.assertEqual(a.count("|\""), len(g["edges"]))

    def test_same_key_cluster_and_infra_dashes(self):
        g = load(ROOT / "cases" / "02-neutron-governance-attack")
        md = diagrams.render(g)
        self.assertIn('subgraph k0["same account key', md)
        self.assertIn(":::infra", md)
        self.assertIn("-.->", md)


if __name__ == "__main__":
    unittest.main()
