import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContainerPackageTests(unittest.TestCase):
    def test_container_runs_the_mcp_server_as_non_root(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER talamus", dockerfile)
        self.assertIn('ENTRYPOINT ["talamus-mcp"]', dockerfile)
        self.assertIn('CMD ["--root", "/data"]', dockerfile)
        self.assertIn('VOLUME ["/data"]', dockerfile)

    def test_docker_context_is_allowlisted(self) -> None:
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual("*", dockerignore[0])
        self.assertIn("!src/**", dockerignore)
        self.assertNotIn("!benchmarks/**", dockerignore)

    def test_container_workflow_runs_protocol_smoke_before_push(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "container.yml").read_text(encoding="utf-8")
        smoke = workflow.index("Initialize container and discover tools")
        push = workflow.index("Publish versioned container")
        self.assertLess(smoke, push)
        self.assertIn("scripts/smoke_mcp_stdio.py", workflow)


if __name__ == "__main__":
    unittest.main()
