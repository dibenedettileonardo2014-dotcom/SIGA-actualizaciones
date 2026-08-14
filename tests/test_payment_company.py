import re
import unicodedata
import unittest


def normalize(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    return "".join(char for char in text if unicodedata.category(char) != "Mn").upper().strip()


def identity(affiliate_id, period, concept=None):
    return "\0".join((affiliate_id, normalize(period), normalize(concept or "CUOTA SINDICAL")))


def document_id(affiliate_id, period, concept):
    safe = re.sub(r"[^A-Z0-9]+", "_", normalize(f"{period}_{concept}")).strip("_")[:100]
    return f"cuota_{affiliate_id}_{safe}"


class PaymentCompanyTests(unittest.TestCase):
    affiliates = [
        {"id": "a1", "company": "Ácidos del Sur", "name": "Uno"},
        {"id": "a2", "company": "Ácidos del Sur", "name": "Dos"},
        {"id": "b1", "company": "Laboratorios Norte", "name": "Tres"},
    ]

    def test_company_search_is_accent_insensitive(self):
        query = normalize("acidos")
        result = [item for item in self.affiliates if query in normalize(item["company"])]
        self.assertEqual([item["id"] for item in result], ["a1", "a2"])

    def test_bulk_scope_requires_exact_company(self):
        selected = "Ácidos del Sur"
        result = [item for item in self.affiliates if normalize(item["company"]) == normalize(selected)]
        self.assertEqual([item["id"] for item in result], ["a1", "a2"])

    def test_period_and_concept_are_unique_per_affiliate(self):
        first = identity("a1", "AGOSTO 2026", "CUOTA SINDICAL")
        same = identity("a1", "agosto 2026", "cuota sindical")
        other_affiliate = identity("a2", "AGOSTO 2026", "CUOTA SINDICAL")
        other_concept = identity("a1", "AGOSTO 2026", "APORTE EXTRAORDINARIO")
        self.assertEqual(first, same)
        self.assertNotEqual(first, other_affiliate)
        self.assertNotEqual(first, other_concept)

    def test_legacy_payment_without_concept_uses_default(self):
        self.assertEqual(
            identity("a1", "JULIO 2026", None),
            identity("a1", "JULIO 2026", "CUOTA SINDICAL"),
        )

    def test_document_id_is_deterministic_for_two_computers(self):
        self.assertEqual(
            document_id("a1", "AGOSTO 2026", "CUOTA SINDICAL"),
            document_id("a1", "agosto 2026", "cuota sindical"),
        )


if __name__ == "__main__":
    unittest.main()
