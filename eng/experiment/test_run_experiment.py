import sys
import tempfile
import unittest
from pathlib import Path

import run_experiment


class AddedCodeScoringTests(unittest.TestCase):
    def test_fixture_markers_are_excluded_but_agent_additions_are_scored(self):
        before = {
            "Product.cs": (
                "public class Product : FullAuditedAggregateRoot<Guid>\n"
                "{\n"
                "    protected Product() { }\n"
                "}\n"
            )
        }
        after = {
            **before,
            "ProductDataService.cs": (
                "public sealed class ProductDataService\n"
                "{\n"
                "    private readonly IDataFilter _dataFilter;\n"
                "}\n"
            ),
        }

        added_text, _ = run_experiment.added_text_and_diff(before, after)
        score = run_experiment.score_markers(
            added_text,
            idiom_markers=["AggregateRoot", "protected ", "IDataFilter"],
            anti_markers=[],
        )

        self.assertNotIn("AggregateRoot", added_text)
        self.assertNotIn("protected ", added_text)
        self.assertEqual(score["idiom"], 1)
        self.assertEqual(score["idiom_hits"], ["IDataFilter"])

    def test_existing_file_counts_only_inserted_lines(self):
        before = {"Service.cs": "public class Service\n{\n}\n"}
        after = {
            "Service.cs": (
                "public class Service\n"
                "{\n"
                "    private readonly IDataFilter _dataFilter;\n"
                "}\n"
            )
        }

        added_text, diff = run_experiment.added_text_and_diff(before, after)

        self.assertEqual(added_text, "    private readonly IDataFilter _dataFilter;\n")
        self.assertIn("+    private readonly IDataFilter _dataFilter;", diff)

    def test_marker_matching_requires_token_boundaries(self):
        score = run_experiment.score_markers(
            "public class CustomAbpInterceptorBase { }\n",
            idiom_markers=["AbpInterceptor"],
            anti_markers=[],
        )

        self.assertEqual(score["idiom"], 0)
        self.assertEqual(score["idiom_hits"], [])


class RunStatusTests(unittest.TestCase):
    def test_agent_error_does_not_run_build_or_enter_build_rate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            artifacts = root / "artifacts"
            workspace.mkdir()
            artifacts.mkdir()
            (artifacts / "stale.txt").write_text("old run")
            (workspace / "Seed.cs").write_text("public class Seed { }\n")
            build_sentinel = root / "build-ran"
            before = run_experiment.snapshot_cs_files(workspace)

            run = run_experiment.execute_workspace(
                workspace=workspace,
                before=before,
                prompt="test prompt",
                spec={"idiom": ["IDataFilter"], "anti": []},
                artifact_dir=artifacts,
                provenance={"test": True},
                agent_command=[sys.executable, "-c", "raise SystemExit(7)"],
                build_command=[
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(build_sentinel)!r}).touch()",
                ],
            )

            aggregate = run_experiment.aggregate([run])

            self.assertEqual(run["status"], "agent_error")
            self.assertEqual(run["agent_status"], "agent_error")
            self.assertEqual(run["build_status"], "not_run")
            self.assertFalse(run["build"]["ran"])
            self.assertFalse(build_sentinel.exists())
            self.assertEqual(aggregate["build_eligible_runs"], 0)
            self.assertEqual(aggregate["build_fail"], 0)
            self.assertIsNone(aggregate["build_pass_rate"])
            self.assertEqual(aggregate["agent_error"], 1)
            self.assertTrue((artifacts / "agent.stdout.log").is_file())
            self.assertTrue((artifacts / "agent.stderr.log").is_file())
            self.assertTrue((artifacts / "agent.json").is_file())
            self.assertTrue((artifacts / "changes.diff").is_file())
            self.assertTrue((artifacts / "after_cs" / "Seed.cs").is_file())
            self.assertTrue((artifacts / "build.log").is_file())
            self.assertTrue((artifacts / "build.json").is_file())
            self.assertTrue((artifacts / "provenance.json").is_file())
            self.assertTrue((artifacts / "result.json").is_file())
            self.assertFalse((artifacts / "stale.txt").exists())

    def test_agent_timeout_does_not_run_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "Seed.cs").write_text("public class Seed { }\n")
            build_sentinel = root / "build-ran"

            run = run_experiment.execute_workspace(
                workspace=workspace,
                before=run_experiment.snapshot_cs_files(workspace),
                prompt="test prompt",
                spec={"idiom": [], "anti": []},
                artifact_dir=root / "artifacts",
                provenance={"test": True},
                agent_command=[sys.executable, "-c", "import time; time.sleep(1)"],
                build_command=[
                    sys.executable,
                    "-c",
                    f"from pathlib import Path; Path({str(build_sentinel)!r}).touch()",
                ],
                agent_timeout=0.01,
            )

            self.assertEqual(run["status"], "agent_timeout")
            self.assertEqual(run["agent_status"], "agent_timeout")
            self.assertEqual(run["build_status"], "not_run")
            self.assertFalse(build_sentinel.exists())

    def test_agent_ok_records_build_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "Seed.cs").write_text("public class Seed { }\n")

            run = run_experiment.execute_workspace(
                workspace=workspace,
                before=run_experiment.snapshot_cs_files(workspace),
                prompt="test prompt",
                spec={"idiom": ["IDataFilter"], "anti": []},
                artifact_dir=root / "artifacts",
                provenance={"test": True},
                agent_command=[
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('Added.cs').write_text('IDataFilter value;\\n')",
                ],
                build_command=[sys.executable, "-c", "raise SystemExit(0)"],
            )

            aggregate = run_experiment.aggregate([run])

            self.assertEqual(run["status"], "build_pass")
            self.assertEqual(run["agent_status"], "agent_ok")
            self.assertEqual(run["build_status"], "build_pass")
            self.assertEqual(run["idiom"], 1)
            self.assertEqual(aggregate["build_pass_rate"], 1.0)
            self.assertEqual(aggregate["scored_runs"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
