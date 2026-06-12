"""Batched domain induction at book scale (found on the real AI Engineering run:
the single full-partition prompt collapses at 243 notes -> everything in Varie).

The batched path uses BOUNDED calls: giant clusters get a dedicated split,
mid clusters are named echoing only a numeric index, strays are assigned in
batches. A malformed answer hurts only its own slice, never the whole brain."""

import json
import unittest

from talamus.domains import (
    MIN_NAMED_CLUSTER,
    SPLIT_CLUSTER_THRESHOLD,
    _name_domains_batched,
)
from tests.support import FakeLLMProvider


def _summaries(titles: list[str]) -> dict[str, str]:
    return {t: f"riassunto di {t}" for t in titles}


class BatchedDomainsTests(unittest.TestCase):
    def test_giant_cluster_split_mid_named_strays_assigned(self) -> None:
        giant = [f"Nota{i}" for i in range(SPLIT_CLUSTER_THRESHOLD + 5)]
        mid = ["Alfa", "Beta", "Gamma"]
        assert len(mid) >= MIN_NAMED_CLUSTER
        strays = ["Sola", "Persa"]
        clusters = [giant, mid, [strays[0]], [strays[1]]]
        summaries = _summaries(giant + mid + strays)

        split_answer = json.dumps(
            [
                {"name": "Prima metà", "description": "d1", "members": giant[:15]},
                {"name": "Seconda metà", "description": "d2", "members": giant[15:]},
            ]
        )
        naming_answer = json.dumps(
            [{"cluster": 0, "name": "Greche", "description": "lettere greche"}]
        )
        assign_answer = json.dumps(
            [
                {"title": "Sola", "domain": "Greche"},
                {"title": "Persa", "domain": "Prima metà"},
            ]
        )
        llm = FakeLLMProvider([split_answer, naming_answer, assign_answer])

        domains = _name_domains_batched(clusters, summaries, llm)

        by_name = {d["name"]: d for d in domains}
        self.assertEqual(
            set(by_name), {"Prima metà", "Seconda metà", "Greche"}
        )  # niente Varie: tutto assegnato
        self.assertIn("Sola", by_name["Greche"]["members"])
        self.assertIn("Persa", by_name["Prima metà"]["members"])
        # ogni nota esattamente una volta
        all_members = [m for d in domains for m in d["members"]]
        self.assertEqual(sorted(all_members), sorted(summaries))
        self.assertEqual(len(llm.prompts), 3)  # 1 split + 1 naming + 1 lotto randagi

    def test_malformed_answers_hurt_only_their_slice(self) -> None:
        """The original failure mode: a broken answer must not sink the brain."""
        giant = [f"G{i}" for i in range(SPLIT_CLUSTER_THRESHOLD)]
        mid = ["Alfa", "Beta", "Gamma"]
        clusters = [giant, mid, ["Sola"]]
        summaries = _summaries(giant + mid + ["Sola"])

        # split malformato, naming malformato, assegnazione malformata
        llm = FakeLLMProvider(["NON-JSON", "{rotto", "..."])
        domains = _name_domains_batched(clusters, summaries, llm)

        by_name = {d["name"]: d for d in domains}
        # il cluster medio sopravvive col fallback deterministico (primo titolo)
        self.assertIn("Alfa", by_name)
        self.assertEqual(by_name["Alfa"]["members"], mid)
        # solo lo slice rotto finisce in Varie, MAI l'intero brain
        self.assertIn("Varie", by_name)
        self.assertEqual(sorted(by_name["Varie"]["members"]), sorted([*giant, "Sola"]))
        all_members = [m for d in domains for m in d["members"]]
        self.assertEqual(sorted(all_members), sorted(summaries))

    def test_no_domains_at_all_falls_back_to_varie(self) -> None:
        clusters = [["Sola"], ["Persa"]]
        summaries = _summaries(["Sola", "Persa"])
        llm = FakeLLMProvider([])
        domains = _name_domains_batched(clusters, summaries, llm)
        self.assertEqual(len(domains), 1)
        self.assertEqual(domains[0]["name"], "Varie")
        self.assertEqual(llm.prompts, [])  # niente domini -> niente lotti da assegnare


if __name__ == "__main__":
    unittest.main()
