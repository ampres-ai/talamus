from __future__ import annotations

import sys
from pathlib import Path

from talamus.adapters.llm import LLMProvider
from talamus.cli._common import (
    _ensure_utf8_output,
    _resolve_root,
    _router_for,
)
from talamus.cli.dashboard import _cmd_panel, _cmd_quickstart, _cmd_ui, _cmd_where
from talamus.cli.groups import (
    _cmd_brains_group,
    _cmd_jobs_group,
    _cmd_ontology_group,
    _cmd_review_group,
)
from talamus.cli.lifecycle import (
    _cmd_completion,
    _cmd_curator,
    _cmd_demo,
    _cmd_doctor,
    _cmd_export,
    _cmd_hook,
    _cmd_hook_retry,
    _cmd_hook_run,
    _cmd_import,
    _cmd_init,
    _cmd_mcp_install,
    _cmd_reindex,
    _cmd_setup,
    _cmd_status,
    _cmd_status_json,
)
from talamus.cli.parser import build_parser
from talamus.cli.pipeline import (
    _cmd_consolidate,
    _cmd_enrich,
    _cmd_import_vault,
    _cmd_ingest,
    _cmd_overview,
    _cmd_scan,
    _cmd_supersede,
    _cmd_verify,
    _cmd_verify_batch,
    _cmd_watch,
)
from talamus.cli.query import (
    _cmd_ask,
    _cmd_eval,
    _cmd_eval_scale,
    _cmd_history,
    _cmd_neighbors,
    _cmd_read,
    _cmd_recall,
    _cmd_relations,
    _cmd_remember,
    _cmd_search,
    _cmd_timeline,
)
from talamus.errors import TalamusError
from talamus.log import configure
from talamus.routing import StaticRouter
from talamus.scan import (
    build_plan,
    format_plan,
)
from talamus.scope import (
    resolve_brain,
    resolve_init_root,
)


def main(argv: list[str] | None = None, llm: LLMProvider | None = None) -> int:
    _ensure_utf8_output()
    args = build_parser().parse_args(argv)
    configure(getattr(args, "verbose", False))
    command = args.command
    if command is None:
        return _cmd_panel(resolve_brain(None, None, False))
    if command == "quickstart":
        return _cmd_quickstart()
    if command == "brains":
        return _cmd_brains_group(args)
    if command == "completion":
        return _cmd_completion(args.shell)

    if command == "setup":
        resolved = resolve_init_root(args.root, args.brain, args.use_global)
        return _cmd_setup(
            resolved.root,
            args.engine,
            args.capture,
            router=StaticRouter(llm) if llm is not None else None,
            verify=args.verify_engine,
        )

    if command == "init":
        resolved = resolve_init_root(args.root, args.brain, args.use_global)
        code = _cmd_init(resolved.root, args.engine, resolved.scope)
        if code == 0 and getattr(args, "scan", False):
            plan = build_plan(Path.cwd(), profile=args.profile)
            print()
            print(format_plan(plan))
            print("\n(no LLM call made; review the plan, then run `talamus scan . --yes`)")
        return code

    if command == "status" and bool(getattr(args, "json", False)):
        return _cmd_status_json(args.root, args.brain, args.use_global)

    root = _resolve_root(
        getattr(args, "root", None),
        getattr(args, "brain", None),
        getattr(args, "use_global", False),
    )
    json_out = bool(getattr(args, "json", False))
    policy = "all" if getattr(args, "all_brains", False) else getattr(args, "scope", None)

    def _build_router():
        """Router for the LLM commands, built LAZILY: non-LLM commands (doctor,
        search without --smart, ...) must keep working on a malformed or missing
        config. A test-injected provider is pinned via StaticRouter; otherwise the
        brain's config drives per-task tiering."""
        return StaticRouter(llm) if llm is not None else _router_for(root)

    try:
        if command == "where":
            return _cmd_where(resolve_brain(args.root, args.brain, args.use_global), json_out)
        if command == "export":
            return _cmd_export(root, args.file)
        if command == "import":
            return _cmd_import(args.file, root)
        if command == "import-vault":
            return _cmd_import_vault(root, args.directory, json_out)
        if command == "ontology":
            return _cmd_ontology_group(args, root, _build_router())
        if command == "jobs":
            return _cmd_jobs_group(args, root)
        if command == "review":
            return _cmd_review_group(args, root)
        if command == "demo":
            return _cmd_demo(root)
        if command == "ui":
            return _cmd_ui(root, args.web, args.port)
        if command == "mcp":
            return _cmd_mcp_install(root, args.agent)
        if command == "hook":
            if args.retry:
                return _cmd_hook_retry(root)
            return _cmd_hook(root, args.install)
        if command == "hook-run":
            return _cmd_hook_run(root)
        if command == "status":
            return _cmd_status(root, json_out)
        if command == "curator":
            return _cmd_curator(
                bool(getattr(args, "fix", False)), json_out, bool(getattr(args, "deep", False))
            )
        if command == "doctor":
            return _cmd_doctor(root)
        if command == "reindex":
            return _cmd_reindex(root, json_out)
        if command == "search":
            return _cmd_search(
                root,
                args.query,
                json_out,
                args.limit,
                policy,
                args.smart,
                # lazy: only --smart needs an engine; _cmd_search falls back on its own
                StaticRouter(llm) if llm is not None else None,
                passes=args.passes,
            )
        if command == "read":
            return _cmd_read(root, args.title, json_out, args.as_of)
        if command == "timeline":
            return _cmd_timeline(root, args.title, json_out)
        if command == "history":
            return _cmd_history(root, args.title, args.as_of, json_out)
        if command == "recall":
            return _cmd_recall(root, args.question, json_out, args.limit, policy)
        if command == "eval":
            if args.scale:
                return _cmd_eval_scale(args.sizes, json_out)
            if not args.cases:
                print("error: pass --cases FILE or --scale", file=sys.stderr)
                return 1
            return _cmd_eval(root, args.cases, args.k, json_out, args.category)
        if command == "neighbors":
            return _cmd_neighbors(
                root, args.concept, json_out, include_inferred=not args.no_inferred
            )
        if command == "relations":
            return _cmd_relations(root, args.prune, json_out)
        if command == "scan":
            return _cmd_scan(root, args.target, _build_router(), args)
        if command == "watch":
            return _cmd_watch(
                root, args.directory, _build_router(), args.interval, args.cap, args.once
            )
        if command == "ingest":
            return _cmd_ingest(root, args.target, _build_router(), json_out, args.yes)
        if command == "consolidate":
            return _cmd_consolidate(root, args.apply, _build_router(), json_out)
        if command == "enrich":
            return _cmd_enrich(root, args.yes, _build_router(), json_out)
        if command == "supersede":
            return _cmd_supersede(root, args.old, args.by)
        if command == "verify":
            if args.all or args.stale or args.source:
                return _cmd_verify_batch(root, _build_router(), args.stale, args.source, json_out)
            if not args.title:
                print("error: pass a note title, or --all / --stale / --source", file=sys.stderr)
                return 1
            return _cmd_verify(root, args.title, args.apply, _build_router(), json_out)
        if command == "overview":
            return _cmd_overview(root, _build_router(), json_out, args.rebuild, policy)
        if command == "ask":
            return _cmd_ask(
                root, args.question, _build_router(), json_out, policy, args.trace, args.as_of
            )
        if command == "remember":
            return _cmd_remember(root, args.transcript, args.diff, _build_router(), json_out)
    except TalamusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    raise ValueError(f"unknown command {command}")
