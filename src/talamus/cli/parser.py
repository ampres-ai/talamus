from __future__ import annotations

import argparse

from talamus import __version__
from talamus.scan import (
    PROFILES,
)
from talamus.scope import (
    SCOPE_POLICIES,
)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root", default=None, help="Explicit brain directory (overrides scoping)."
    )
    common.add_argument("--brain", default=None, help="Named global brain under TALAMUS_HOME.")
    common.add_argument(
        "--global", dest="use_global", action="store_true", help="Use the default global brain."
    )
    common.add_argument("--verbose", action="store_true", help="Verbose diagnostics to stderr.")
    common.add_argument(
        "--plain",
        "--no-color",
        dest="plain",
        action="store_true",
        help="Plain output (no ANSI color; honored by default — output is already plain).",
    )
    common.add_argument("--json", action="store_true", help="Machine-readable JSON output.")

    parser = argparse.ArgumentParser(
        prog="talamus",
        description="Local-first knowledge compiler.",
        epilog=(
            "examples:\n"
            "  talamus init --scan             brain here + repo scan plan (dry-run)\n"
            '  talamus ask "how does X work?"  cited answer from your notes\n'
            "  talamus search ontology --all-brains\n"
            '  talamus ask "..." --as-of 2026-01 --trace\n'
            "  talamus ontology induce         grow the emergent type system"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"talamus {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    setup = sub.add_parser(
        "setup", parents=[common], help="one-command onboarding: brain + engine + MCP + hook"
    )
    setup.add_argument("--engine", default=None, help="LLM engine (else best detected)")
    init = sub.add_parser("init", parents=[common], help="initialize a brain here")
    init.add_argument("--engine", default=None, help="LLM engine (else auto-detected).")
    init.add_argument(
        "--scan", action="store_true", help="after init, show the repo scan plan (dry-run)"
    )
    init.add_argument("--profile", choices=list(PROFILES), default="all")
    sub.add_parser("demo", parents=[common], help="create a small example brain")
    ui = sub.add_parser("ui", parents=[common], help="launch the workbench (needs the 'ui' extra)")
    ui.add_argument("--web", action="store_true", help="open in the browser (test mode, F9.1)")
    ui.add_argument("--port", type=int, default=8550, help="port for --web (default 8550)")
    for name in ("status", "doctor", "reindex"):
        sub.add_parser(name, parents=[common], help=f"{name} the brain")
    sub.add_parser("quickstart", help="print the essential commands")
    brains = sub.add_parser("brains", help="manage the brain registry")
    brains_sub = brains.add_subparsers(dest="brains_cmd")
    brains_sub.add_parser("list", parents=[common], help="list registered brains")
    b_use = brains_sub.add_parser("use", parents=[common], help="select the default global brain")
    b_use.add_argument("name")
    b_info = brains_sub.add_parser("info", parents=[common], help="show one brain's record")
    b_info.add_argument("name")
    b_rename = brains_sub.add_parser("rename", parents=[common], help="rename a registered brain")
    b_rename.add_argument("old")
    b_rename.add_argument("new")
    b_delete = brains_sub.add_parser(
        "delete", parents=[common], help="unregister a brain (files are preserved)"
    )
    b_delete.add_argument("name")
    b_register = brains_sub.add_parser(
        "register", parents=[common], help="register an existing brain"
    )
    b_register.add_argument("path")
    b_register.add_argument("--name", default=None)
    b_register.add_argument("--type", default="project", choices=["project", "central", "archive"])
    b_set = brains_sub.add_parser("set", parents=[common], help="set federation/privacy flags")
    b_set.add_argument("name")
    b_set.add_argument("--federated", choices=["true", "false"], default=None)
    b_set.add_argument("--sensitive", choices=["true", "false"], default=None)
    b_index = brains_sub.add_parser(
        "index", parents=[common], help="build or inspect the federated index"
    )
    b_index.add_argument("action", nargs="?", default="build", choices=["build", "status"])
    b_index.add_argument("--rebuild", action="store_true", help="force a full rebuild")
    b_promote = brains_sub.add_parser(
        "promote", parents=[common], help="promote a note between brains"
    )
    b_promote.add_argument("note")
    b_promote.add_argument("--from", dest="from_brain", required=True)
    b_promote.add_argument("--to", dest="to_brain", default="default")
    sub.add_parser("where", parents=[common], help="print the resolved brain path")
    onto = sub.add_parser("ontology", help="the emergent type system: induce, review, promote")
    onto_sub = onto.add_subparsers(dest="ontology_cmd")
    onto_sub.add_parser("status", parents=[common], help="schema version, types, coverage")
    o_induce = onto_sub.add_parser(
        "induce", parents=[common], help="induce candidate relation types from the corpus"
    )
    o_induce.add_argument("--min-support", type=int, default=3, help="evidence per candidate")
    onto_sub.add_parser("review", parents=[common], help="list candidate types with evidence")
    o_apply = onto_sub.add_parser("apply", parents=[common], help="promote a candidate to active")
    o_apply.add_argument("type_id")
    o_apply.add_argument("--force", action="store_true", help="override promotion thresholds")
    o_reject = onto_sub.add_parser("reject", parents=[common], help="reject a candidate (kept)")
    o_reject.add_argument("type_id")
    o_reject.add_argument("--reason", default="")
    o_depr = onto_sub.add_parser("deprecate", parents=[common], help="deprecate an active type")
    o_depr.add_argument("type_id")
    o_depr.add_argument("--reason", default="")
    o_eval = onto_sub.add_parser(
        "eval", parents=[common], help="retrieval lift: fixed baseline vs active schema"
    )
    o_eval.add_argument("--cases", required=True)
    o_eval.add_argument("-k", type=int, default=5)
    o_stab = onto_sub.add_parser("stability", parents=[common], help="cluster stability (Jaccard)")
    o_stab.add_argument("--runs", type=int, default=3)
    onto_sub.add_parser("history", parents=[common], help="schema change events")
    onto_sub.add_parser("export", parents=[common], help="print the full schema JSON")
    jobs = sub.add_parser("jobs", help="inspect and control long-running jobs")
    jobs_sub = jobs.add_subparsers(dest="jobs_cmd")
    jobs_sub.add_parser("list", parents=[common], help="list jobs")
    for jobs_action in ("status", "resume", "cancel", "logs"):
        j_parser = jobs_sub.add_parser(jobs_action, parents=[common], help=f"{jobs_action} a job")
        j_parser.add_argument("job_id")
    review = sub.add_parser("review", help="review queue: pending decisions")
    review_sub = review.add_subparsers(dest="review_cmd")
    r_list = review_sub.add_parser("list", parents=[common], help="list pending review items")
    r_list.add_argument("--all", action="store_true", help="include applied/rejected items")
    for review_action in ("show", "apply"):
        r_parser = review_sub.add_parser(
            review_action, parents=[common], help=f"{review_action} a review item"
        )
        r_parser.add_argument("item_id")
    r_reject = review_sub.add_parser("reject", parents=[common], help="reject a review item")
    r_reject.add_argument("item_id")
    r_reject.add_argument("--reason", default="", help="why it was rejected (kept in the log)")
    export = sub.add_parser("export", parents=[common], help="export the brain to a zip")
    export.add_argument("file")
    importer = sub.add_parser("import", parents=[common], help="import a brain from a zip")
    importer.add_argument("file")
    vault = sub.add_parser(
        "import-vault",
        parents=[common],
        help="import a Markdown/Obsidian vault 1:1 (no LLM, wikilinks preserved)",
    )
    vault.add_argument("directory", help="the vault folder (Obsidian vault or md export)")
    completion = sub.add_parser("completion", help="print a shell completion script")
    completion.add_argument("shell", nargs="?", default="bash", choices=["bash", "zsh"])
    mcp = sub.add_parser("mcp", parents=[common], help="set up the MCP server config (.mcp.json)")
    mcp.add_argument("action", nargs="?", default="install", choices=["install"])
    sub.add_parser("hook", parents=[common], help="print the Claude Code capture-hook config")
    sub.add_parser("hook-run", parents=[common], help="run the capture hook (reads stdin)")

    ingest = sub.add_parser("ingest", parents=[common], help="add a file, folder, or URL")
    ingest.add_argument("target", help="a file, a folder (recursive), or a URL")
    ingest.add_argument(
        "--yes", action="store_true", help="confirm a multi-chunk ingest (big documents)"
    )
    scan = sub.add_parser(
        "scan", parents=[common], help="compile an existing repository (plan first, spend later)"
    )
    scan.add_argument("target", nargs="?", default=".", help="repository root (default: here)")
    scan.add_argument("--dry-run", action="store_true", help="show the plan only (no LLM cost)")
    scan.add_argument("--yes", action="store_true", help="execute the plan")
    scan.add_argument("--background", action="store_true", help="queue a resumable job instead")
    scan.add_argument("--profile", choices=list(PROFILES), default="all")
    scan.add_argument("--max-files", type=int, default=None)
    scan.add_argument("--include", action="append", default=[], metavar="GLOB")
    scan.add_argument("--exclude", action="append", default=[], metavar="GLOB")
    scan.add_argument(
        "--allow-secrets",
        action="store_true",
        help="proceed despite flagged secrets (content is redacted before the LLM)",
    )
    consolidate = sub.add_parser("consolidate", parents=[common], help="merge duplicate concepts")
    consolidate.add_argument("--apply", action="store_true", help="actually merge (default: list)")

    enrich = sub.add_parser(
        "enrich", parents=[common], help="add symptom phrasings to retrieval_text"
    )
    enrich.add_argument("--yes", action="store_true", help="run the batches (default: estimate)")
    verify = sub.add_parser("verify", parents=[common], help="check a note against its source")
    verify.add_argument("title", nargs="?", default=None)
    verify.add_argument("--apply", action="store_true", help="apply the correction")
    verify.add_argument("--all", action="store_true", help="batch: every note (LLM per note)")
    verify.add_argument(
        "--stale", action="store_true", help="batch: provenance health only (no LLM)"
    )
    verify.add_argument("--source", default=None, help="batch: only notes from this source")
    overview = sub.add_parser("overview", parents=[common], help="show the domain overview")
    overview.add_argument("--rebuild", action="store_true", help="re-induce the domains")
    ask = sub.add_parser("ask", parents=[common], help="ask the brain (cited answer)")
    ask.add_argument("question")
    ask.add_argument(
        "--trace", action="store_true", help="explain the route: domains, candidates, tokens"
    )
    ask.add_argument(
        "--as-of", dest="as_of", default=None, help="answer from the brain as it was at this time"
    )
    search = sub.add_parser("search", parents=[common], help="find relevant notes")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5, help="max results (default 5)")
    search.add_argument(
        "--smart",
        action="store_true",
        help="expand the query with the LLM before searching (cached); breaks the lexical ceiling",
    )
    for scoped in (overview, ask, search):
        scoped.add_argument(
            "--scope", choices=list(SCOPE_POLICIES), default=None, help="brain scope policy"
        )
        scoped.add_argument(
            "--all-brains",
            dest="all_brains",
            action="store_true",
            help="alias for --scope all (search every registered brain)",
        )
    read = sub.add_parser("read", parents=[common], help="print a note by title")
    read.add_argument("title")
    read.add_argument("--as-of", dest="as_of", default=None, help="version current at this time")
    tl = sub.add_parser("timeline", parents=[common], help="both timelines of a note")
    tl.add_argument("title")
    history = sub.add_parser("history", parents=[common], help="show a note's past versions")
    history.add_argument("title")
    history.add_argument("--as-of", default=None, help="version current at this ISO time")
    recall = sub.add_parser("recall", parents=[common], help="retrieve context for a question")
    recall.add_argument("question")
    recall.add_argument("--limit", type=int, default=5, help="max notes of context (default 5)")
    recall.add_argument(
        "--scope", choices=list(SCOPE_POLICIES), default=None, help="brain scope policy"
    )
    recall.add_argument(
        "--all-brains", dest="all_brains", action="store_true", help="alias for --scope all"
    )
    ev = sub.add_parser("eval", parents=[common], help="measure retrieval quality on a cases file")
    ev.add_argument("--cases", default=None, help='JSON: [{"question","relevant":[titles]}]')
    ev.add_argument("-k", type=int, default=5, help="cutoff for recall@k (default 5)")
    ev.add_argument("--category", default=None, help="run only cases of this category")
    ev.add_argument("--scale", action="store_true", help="latency benchmark at growing sizes")
    ev.add_argument("--sizes", default=None, help="comma-separated note counts for --scale")
    neighbors = sub.add_parser("neighbors", parents=[common], help="show a concept's connections")
    neighbors.add_argument("concept")
    relations = sub.add_parser("relations", parents=[common], help="list/prune typed relations")
    relations.add_argument(
        "--prune", type=float, default=None, metavar="MIN", help="drop below MIN"
    )
    remember = sub.add_parser("remember", parents=[common], help="capture an agent session")
    remember.add_argument("--transcript", required=True)
    remember.add_argument("--diff", default=None)
    return parser
