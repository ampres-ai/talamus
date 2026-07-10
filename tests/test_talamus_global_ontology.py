"""One ontology across all brains.

The learned relation-type schema is machine-wide by default: a type promoted in
one brain immediately types matching surfaces in every other brain. Evidence
stays per brain; `ontology_scope: "brain"` restores the historical isolation.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from talamus.ontology_lab import (
    RelationType,
    load_schema,
    save_schema,
    schema_path,
)
from talamus.paths import TalamusPaths


def _brain(tmp: Path, name: str) -> TalamusPaths:
    paths = TalamusPaths(tmp / name)
    paths.ensure_directories()
    return paths


def _type(type_id: str, status: str = "active") -> RelationType:
    from talamus.ontology_lab import surface_key

    name = type_id.removeprefix("rel:")
    return RelationType(
        id=type_id,
        name=name,
        definition="d",
        surfaces=[surface_key(name)],  # the lab stores stemmed surface keys
        status=status,
    )


class GlobalOntologyTests(unittest.TestCase):
    def test_schema_is_shared_across_brains_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                beta = _brain(Path(tmp), "beta")
                schema = load_schema(alpha)
                schema.relation_types.append(_type("rel:feeds"))
                save_schema(alpha, schema)

                seen_from_beta = load_schema(beta)
        self.assertIsNotNone(seen_from_beta.by_id("rel:feeds"))

    def test_global_schema_lives_under_talamus_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                target = schema_path(alpha)
        self.assertTrue(str(target).startswith(str(home)))

    def test_brain_scope_keeps_the_historical_isolation(self) -> None:
        from dataclasses import replace

        from talamus.config import TalamusConfig, save_config

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                beta = _brain(Path(tmp), "beta")
                for paths in (alpha, beta):
                    save_config(
                        paths.config_path,
                        replace(TalamusConfig.default(), ontology_scope="brain"),
                    )
                schema = load_schema(alpha)
                schema.relation_types.append(_type("rel:feeds"))
                save_schema(alpha, schema)

                self.assertIsNone(load_schema(beta).by_id("rel:feeds"))
                self.assertIsNotNone(load_schema(alpha).by_id("rel:feeds"))

    def test_existing_local_schema_seeds_the_global_one_on_first_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                # a pre-global brain: schema saved locally (the historical layout)
                local = alpha.cache / "ontology" / "schema.json"
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text(
                    json.dumps(
                        {
                            "version": 1,
                            "schema_id": "schema-legacy",
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "relation_types": [_type("rel:legacy").to_dict()],
                        }
                    ),
                    encoding="utf-8",
                )

                migrated = load_schema(alpha)
                self.assertIsNotNone(migrated.by_id("rel:legacy"))
                # and the seed is persisted globally: another brain sees it too
                beta = _brain(Path(tmp), "beta")
                self.assertIsNotNone(load_schema(beta).by_id("rel:legacy"))

    def test_global_file_wins_over_a_stale_local_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                schema = load_schema(alpha)
                schema.relation_types.append(_type("rel:global-truth"))
                save_schema(alpha, schema)
                # a stale local file must NOT shadow the shared schema
                local = alpha.cache / "ontology" / "schema.json"
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_text(json.dumps({"version": 1, "relation_types": []}), encoding="utf-8")

                self.assertIsNotNone(load_schema(alpha).by_id("rel:global-truth"))

    def test_promotion_in_one_brain_types_edges_in_another(self) -> None:
        from talamus.ontology import normalize_relation
        from talamus.ontology_lab import active_surface_map

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            with patch.dict(os.environ, {"TALAMUS_HOME": str(home)}):
                alpha = _brain(Path(tmp), "alpha")
                beta = _brain(Path(tmp), "beta")
                schema = load_schema(alpha)
                schema.relation_types.append(_type("rel:feeds"))
                save_schema(alpha, schema)

                # the OTHER brain's runtime surface map now carries the shared type
                surfaces = active_surface_map(beta)
                self.assertEqual(normalize_relation("feeds", surfaces), "feeds")


if __name__ == "__main__":
    unittest.main()
