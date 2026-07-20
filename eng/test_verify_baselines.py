import unittest

import verify_baselines as vb

BASELINES = {
    "stable_compile": {"nuget_version": "10.5.0"},
    "next_compile": {"nuget_version": "10.6.0-rc.1"},
}

PROPS = "<Project><PropertyGroup><AbpVersion>10.5.0</AbpVersion></PropertyGroup></Project>"
# runtime/ now uses central package management too, so its baseline is the <AbpVersion>.
RUNTIME_PROPS = "<Project><PropertyGroup><AbpVersion>10.5.0</AbpVersion></PropertyGroup></Project>"
PACKAGE_JSON = '{"dependencies": {"@abp/ng.core": "10.5.0", "@angular/core": "20.0.0"}}'
README = (
    "| Plugin | Version | Compile-tested ABP |\n"
    "| --- | --- | --- |\n"
    "| `abp-cli` | 1.0.0 | 10.5.0 |\n"
    "| `abp-api` | 1.0.0 | 10.5.0 |\n"
    "| `abp-data-access` | EF Core / MongoDB / Dapper, seeding. |\n"  # desc table row, ignored
)
WORKFLOWS = {
    "validate.yml": "run: dotnet build compat/AbpSkillsCompat.slnx -p:AbpVersion=10.6.0-rc.1 -p:AbpNext=true",
}


class ParsersTest(unittest.TestCase):
    def test_props_version(self):
        self.assertEqual(vb.props_abp_version(PROPS), "10.5.0")

    def test_ng_core(self):
        self.assertEqual(vb.ng_core_version(PACKAGE_JSON), "10.5.0")

    def test_readme_ignores_description_table(self):
        # only the 3-col rows whose last cell is a version count
        self.assertEqual(vb.readme_compile_tested_versions(README), ["10.5.0", "10.5.0"])

    def test_workflow_next(self):
        self.assertEqual(vb.workflow_next_versions(WORKFLOWS["validate.yml"]), ["10.6.0-rc.1"])


class BaselineErrorsTest(unittest.TestCase):
    def test_consistent_is_clean(self):
        errs = vb.baseline_errors(BASELINES, PROPS, RUNTIME_PROPS, PACKAGE_JSON, README, WORKFLOWS)
        self.assertEqual(errs, [])

    def test_props_drift_flagged(self):
        bad = PROPS.replace("10.5.0", "10.4.0")
        errs = vb.baseline_errors(BASELINES, bad, RUNTIME_PROPS, PACKAGE_JSON, README, WORKFLOWS)
        self.assertTrue(any("compat/Directory.Packages.props" in e for e in errs))

    def test_runtime_drift_flagged(self):
        bad = RUNTIME_PROPS.replace("10.5.0", "10.4.0")
        errs = vb.baseline_errors(BASELINES, PROPS, bad, PACKAGE_JSON, README, WORKFLOWS)
        self.assertTrue(any("runtime/Directory.Packages.props" in e for e in errs))

    def test_ng_core_drift_flagged(self):
        bad = PACKAGE_JSON.replace("10.5.0", "10.4.0")
        errs = vb.baseline_errors(BASELINES, PROPS, RUNTIME_PROPS, bad, README, WORKFLOWS)
        self.assertTrue(any("@abp/ng.core" in e for e in errs))

    def test_readme_drift_flagged(self):
        bad = README.replace("| `abp-api` | 1.0.0 | 10.5.0 |", "| `abp-api` | 1.0.0 | 10.4.0 |")
        errs = vb.baseline_errors(BASELINES, PROPS, RUNTIME_PROPS, PACKAGE_JSON, bad, WORKFLOWS)
        self.assertTrue(any("README compile-tested" in e for e in errs))

    def test_workflow_next_drift_flagged(self):
        bad = {"validate.yml": WORKFLOWS["validate.yml"].replace("10.6.0-rc.1", "10.6.0-rc.2")}
        errs = vb.baseline_errors(BASELINES, PROPS, RUNTIME_PROPS, PACKAGE_JSON, README, bad)
        self.assertTrue(any("next" in e for e in errs))

    def test_missing_workflow_step_flagged(self):
        bad = {"validate.yml": "run: dotnet build compat/AbpSkillsCompat.slnx"}
        errs = vb.baseline_errors(BASELINES, PROPS, RUNTIME_PROPS, PACKAGE_JSON, README, bad)
        self.assertTrue(any("no -p:AbpVersion=<next>" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
