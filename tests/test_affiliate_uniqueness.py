import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def dni(value):
    return "".join(character for character in str(value) if character.isdigit())


class AtomicAffiliateRegistry:
    """Small concurrency model of the client-side Firestore transaction contract."""

    def __init__(self):
        self.lock = threading.Lock()
        self.by_id = {}
        self.dni_owner = {}
        self.number_owner = {}
        self.next_number = 1

    def sync(self, affiliate_id, document, mutation_id):
        with self.lock:
            current = self.by_id.get(affiliate_id)
            if current and current["mutation"] == mutation_id:
                return current
            normalized = dni(document["dni"])
            owner = self.dni_owner.get(normalized)
            if owner and owner != affiliate_id:
                raise ValueError("dni-conflict")
            number = str(document["number"])
            owner = self.number_owner.get(number)
            if owner and owner != affiliate_id:
                while str(self.next_number) in self.number_owner:
                    self.next_number += 1
                number = str(self.next_number)
            self.next_number = max(self.next_number, int(number) + 1)
            saved = {**document, "id": affiliate_id, "dni": normalized, "number": number, "mutation": mutation_id}
            self.by_id[affiliate_id] = saved
            self.dni_owner[normalized] = affiliate_id
            self.number_owner[number] = affiliate_id
            return saved


class AffiliateUniquenessTests(unittest.TestCase):
    def test_source_uses_automatic_local_and_atomic_online_allocation(self):
        source = (ROOT / "index.html").read_text(encoding="utf-8")
        rules = (ROOT / "firestore.rules").read_text(encoding="utf-8")
        for marker in (
            'id="form-number" required readonly',
            "reserveNextLocalAffiliateNumber",
            "affiliateSaveInProgress",
            "validateAffiliateLocally",
            "affiliateSequenceRef",
            "migrateAffiliateUniquenessIndex",
            "await affiliateUniquenessReady",
            "error.code = 'dni-conflict'",
            "syncStatus = 'conflict'",
        ):
            self.assertIn(marker, source)
        self.assertIn("public/config/affiliate_sequence/state", rules)
        self.assertIn("allow update: if false;", rules)

    def test_normalized_dni_and_number_are_unique(self):
        registry = AtomicAffiliateRegistry()
        first = registry.sync("a", {"dni": "12.345.678", "number": "1"}, "mutation-a")
        self.assertEqual(first["dni"], "12345678")
        with self.assertRaisesRegex(ValueError, "dni-conflict"):
            registry.sync("b", {"dni": "12345678", "number": "2"}, "mutation-b")

    def test_two_computers_with_same_provisional_number_are_renumbered_atomically(self):
        registry = AtomicAffiliateRegistry()
        results = []
        barrier = threading.Barrier(2)

        def create(affiliate_id, document_dni):
            barrier.wait()
            results.append(registry.sync(affiliate_id, {"dni": document_dni, "number": "1"}, f"mutation-{affiliate_id}"))

        threads = [threading.Thread(target=create, args=("a", "11111111")), threading.Thread(target=create, args=("b", "22222222"))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual({item["number"] for item in results}, {"1", "2"})

    def test_repeated_sync_is_idempotent(self):
        registry = AtomicAffiliateRegistry()
        document = {"dni": "33333333", "number": "1"}
        first = registry.sync("a", document, "same-mutation")
        second = registry.sync("a", document, "same-mutation")
        self.assertEqual(first, second)
        self.assertEqual(len(registry.by_id), 1)

    def test_offline_conflict_is_preserved_for_review(self):
        registry = AtomicAffiliateRegistry()
        registry.sync("online", {"dni": "44444444", "number": "1"}, "online-mutation")
        pending = {"id": "offline", "data": {"dni": "44.444.444", "number": "1"}, "conflict": False}
        try:
            registry.sync(pending["id"], pending["data"], "offline-mutation")
        except ValueError as error:
            pending.update(conflict=True, reason=str(error))
        self.assertTrue(pending["conflict"])
        self.assertEqual(pending["reason"], "dni-conflict")
        self.assertNotIn("offline", registry.by_id)

    def test_consecutive_affiliates_remain_unique_after_recovery(self):
        registry = AtomicAffiliateRegistry()
        pending = [{"dni": str(50_000_000 + index), "number": "1"} for index in range(20)]
        saved = [registry.sync(str(index), item, f"mutation-{index}") for index, item in enumerate(pending)]
        self.assertEqual(len({item["dni"] for item in saved}), 20)
        self.assertEqual(len({item["number"] for item in saved}), 20)


if __name__ == "__main__":
    unittest.main()
