"""Ontology admin: review the typed relations and prune the weak ones.

Relations carry a confidence; low-confidence ones add noise to the graph. Pruning
rewrites the affected notes through the store, so the prior versions stay in history.
"""

from __future__ import annotations

import dataclasses

from talamus.paths import TalamusPaths
from talamus.store import load_notes, overwrite_note_json, rebuild_indexes


def list_relations(paths: TalamusPaths) -> list[dict]:
    """Every typed relation across the brain (source, relation, target, confidence)."""
    out: list[dict] = []
    for note in load_notes(paths):
        for relation in note.relations:
            out.append(
                {
                    "source": relation.source,
                    "relation": relation.relation,
                    "target": relation.target,
                    "confidence": relation.confidence,
                }
            )
    return out


def prune_relations(paths: TalamusPaths, min_confidence: float) -> int:
    """Drop relations below `min_confidence` from all notes. Returns how many were removed."""
    changed: list = []
    pruned = 0
    for note in load_notes(paths):
        keep = [r for r in note.relations if r.confidence >= min_confidence]
        if len(keep) != len(note.relations):
            pruned += len(note.relations) - len(keep)
            changed.append(dataclasses.replace(note, relations=keep))
    for note in changed:
        overwrite_note_json(paths, note)
    if changed:
        rebuild_indexes(paths)
    return pruned
