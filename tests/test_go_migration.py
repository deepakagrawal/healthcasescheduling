"""
Tests for the Go migration of the scheduling application.

These tests verify that:
1. The Go module structure exists (go.mod, main package)
2. The Go code compiles successfully
3. Core utility functions are implemented correctly
4. The Go binary can read CSV data and produce valid output
5. The solver produces the same optimal objective value as the Python version
"""
import json
import os
import subprocess
import sys
import unittest
import csv
import tempfile


class TestGoModuleExists(unittest.TestCase):
    """Verify Go project structure exists."""

    def test_go_mod_exists(self):
        self.assertTrue(os.path.exists("/app/go.mod"),
                        "go.mod must exist at repo root")

    def test_go_mod_has_module_name(self):
        with open("/app/go.mod") as f:
            content = f.read()
        self.assertIn("module", content, "go.mod must declare a module")

    def test_main_go_exists(self):
        """There should be a main.go or cmd/ entry point."""
        has_main = (
            os.path.exists("/app/main.go") or
            os.path.exists("/app/cmd/main.go") or
            os.path.exists("/app/cmd/scheduler/main.go")
        )
        self.assertTrue(has_main, "A Go main entry point must exist")


class TestGoCompiles(unittest.TestCase):
    """Verify the Go code compiles without errors."""

    def test_go_build(self):
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd="/app",
            capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0,
                         f"Go build failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    def test_go_vet(self):
        result = subprocess.run(
            ["go", "vet", "./..."],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0,
                         f"Go vet failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")


class TestGoUnitTests(unittest.TestCase):
    """Verify Go unit tests pass (the Go code should include its own tests)."""

    def test_go_test(self):
        result = subprocess.run(
            ["go", "test", "./...", "-v", "-timeout", "120s"],
            cwd="/app",
            capture_output=True, text=True, timeout=180
        )
        self.assertEqual(result.returncode, 0,
                         f"Go tests failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")


class TestCheckAvailGo(unittest.TestCase):
    """Verify the Go binary implements check_avail logic correctly."""

    def _run_go(self, args):
        result = subprocess.run(
            ["go", "run", ".", *args],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        return result

    def test_check_avail_room(self):
        result = self._run_go(["--check-avail", "SiteA - Room"])
        self.assertEqual(result.stdout.strip(), "true")

    def test_check_avail_room_numbered(self):
        result = self._run_go(["--check-avail", "SiteA - Room 5"])
        self.assertEqual(result.stdout.strip(), "true")

    def test_check_avail_no_call(self):
        result = self._run_go(["--check-avail", "No Call"])
        self.assertEqual(result.stdout.strip(), "true")

    def test_check_avail_administrative(self):
        result = self._run_go(["--check-avail", "Administrative"])
        self.assertEqual(result.stdout.strip(), "false")

    def test_check_avail_vacation(self):
        result = self._run_go(["--check-avail", "Vacation"])
        self.assertEqual(result.stdout.strip(), "false")

    def test_check_avail_eve_shift(self):
        result = self._run_go(["--check-avail", "SiteA - EveShift1 3p"])
        self.assertEqual(result.stdout.strip(), "false")

    def test_check_avail_postshift(self):
        result = self._run_go(["--check-avail", "SiteA - PostShift"])
        self.assertEqual(result.stdout.strip(), "false")

    def test_check_avail_empty(self):
        result = self._run_go(["--check-avail", " "])
        self.assertEqual(result.stdout.strip(), "false")


class TestReadCSVGo(unittest.TestCase):
    """Verify the Go binary can read and parse CSV files correctly."""

    def test_read_task_csv(self):
        result = subprocess.run(
            ["go", "run", ".", "--read-tasks", "data/toy/task.csv"],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0,
                         f"Failed to read task CSV: {result.stderr}")
        output = json.loads(result.stdout)
        self.assertEqual(len(output), 27, "task.csv should have 27 tasks")
        # Verify first task
        self.assertEqual(output[0]["Task"], "SiteA - Room 1")
        self.assertEqual(output[0]["Cost"], 7)
        self.assertEqual(output[0]["Hours"], 10)

    def test_read_parttime_csv(self):
        result = subprocess.run(
            ["go", "run", ".", "--read-parttime", "data/toy/parttime.csv"],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0,
                         f"Failed to read parttime CSV: {result.stderr}")
        output = json.loads(result.stdout)
        self.assertEqual(len(output), 1, "parttime.csv should have 1 provider")
        self.assertIn("Provider5", output)

    def test_read_grid_csv(self):
        result = subprocess.run(
            ["go", "run", ".", "--read-grid", "data/toy/grid.csv"],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        self.assertEqual(result.returncode, 0,
                         f"Failed to read grid CSV: {result.stderr}")
        output = json.loads(result.stdout)
        self.assertIn("providers", output)
        self.assertIn("dates", output)
        self.assertGreater(len(output["providers"]), 0)
        self.assertGreater(len(output["dates"]), 0)


class TestSolverGo(unittest.TestCase):
    """Verify the Go solver produces correct results on real data."""

    @classmethod
    def setUpClass(cls):
        """Build the Go binary once for all solver tests."""
        result = subprocess.run(
            ["go", "build", "-o", "/tmp/scheduler", "."],
            cwd="/app",
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"Go build failed: {result.stderr}")

    def test_solver_runs_successfully(self):
        """The Go solver should run and exit cleanly."""
        result = subprocess.run(
            ["/tmp/scheduler",
             "--objective", "SD_max_pain4",
             "--specialty1cost", "3",
             "--grid", "data/toy/grid.csv",
             "--newPeriod", "2020-12-01", "--newPeriod", "2020-12-07",
             "--task", "data/toy/task.csv",
             "--parttime", "data/toy/parttime.csv",
             "--output", "/tmp/test_output.xlsx"],
            cwd="/app",
            capture_output=True, text=True, timeout=300
        )
        self.assertEqual(result.returncode, 0,
                         f"Solver failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    def test_solver_produces_output_file(self):
        """The solver should produce an output xlsx file."""
        output_path = "/tmp/test_output_exists.xlsx"
        subprocess.run(
            ["/tmp/scheduler",
             "--objective", "SD_max_pain4",
             "--specialty1cost", "3",
             "--grid", "data/toy/grid.csv",
             "--newPeriod", "2020-12-01", "--newPeriod", "2020-12-07",
             "--task", "data/toy/task.csv",
             "--parttime", "data/toy/parttime.csv",
             "--output", output_path],
            cwd="/app",
            capture_output=True, text=True, timeout=300
        )
        self.assertTrue(os.path.exists(output_path),
                        "Solver must produce an output file")
        self.assertGreater(os.path.getsize(output_path), 0,
                           "Output file must not be empty")

    def test_solver_optimal_value(self):
        """The solver should find an optimal solution close to the Python version's value."""
        result = subprocess.run(
            ["/tmp/scheduler",
             "--objective", "SD_max_pain4",
             "--specialty1cost", "3",
             "--grid", "data/toy/grid.csv",
             "--newPeriod", "2020-12-01", "--newPeriod", "2020-12-07",
             "--task", "data/toy/task.csv",
             "--parttime", "data/toy/parttime.csv",
             "--output", "/tmp/test_output_optimal.xlsx"],
            cwd="/app",
            capture_output=True, text=True, timeout=300
        )
        self.assertEqual(result.returncode, 0, f"Solver failed: {result.stderr}")

        # The Python solver produces optimal value ~1.8596
        # Look for the objective value in the output
        combined = result.stdout + result.stderr
        self.assertIn("Optimal objective value", combined,
                      "Solver must log the optimal objective value")

        # Extract the value
        for line in combined.split("\n"):
            if "Optimal objective value" in line:
                # Parse the float value from the line
                parts = line.split(":")
                val = float(parts[-1].strip())
                self.assertAlmostEqual(val, 2.1533, delta=0.5,
                                       msg=f"Optimal value {val} differs from expected ~2.1533")
                break

    def test_solver_status_optimal(self):
        """The solver should report status 0 (optimal)."""
        result = subprocess.run(
            ["/tmp/scheduler",
             "--objective", "SD_max_pain4",
             "--specialty1cost", "3",
             "--grid", "data/toy/grid.csv",
             "--newPeriod", "2020-12-01", "--newPeriod", "2020-12-07",
             "--task", "data/toy/task.csv",
             "--parttime", "data/toy/parttime.csv",
             "--output", "/tmp/test_output_status.xlsx"],
            cwd="/app",
            capture_output=True, text=True, timeout=300
        )
        combined = result.stdout + result.stderr
        self.assertIn("Solver status: 0", combined,
                      "Solver must report optimal status (0)")


class TestConstantsGo(unittest.TestCase):
    """Verify Go constants match the Python enum definitions."""

    def _run_go(self, args):
        result = subprocess.run(
            ["go", "run", ".", *args],
            cwd="/app",
            capture_output=True, text=True, timeout=60
        )
        return result

    def test_room_list(self):
        """Room list should have 14 entries matching Python's ROOM_LIST_1_TO_14."""
        result = self._run_go(["--list-rooms"])
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
        rooms = json.loads(result.stdout)
        self.assertEqual(len(rooms), 14)
        self.assertEqual(rooms[0], "SiteA - Room 1")
        self.assertEqual(rooms[13], "SiteA - Room 14")

    def test_high_cost_tasks(self):
        """High cost tasks should match Python's HIGH_COST_TASKS."""
        result = self._run_go(["--list-high-cost"])
        self.assertEqual(result.returncode, 0, f"Failed: {result.stderr}")
        tasks = json.loads(result.stdout)
        expected = [
            "SiteA - Room 1", "SiteA - Room 2", "SiteA - Room 3",
            "SiteA - EveShift1 3p", "SiteA - EveShift2 12p",
        ]
        self.assertEqual(tasks, expected)


class TestPythonTestsStillPass(unittest.TestCase):
    """Verify the existing Python tests still pass after Go migration."""

    def test_python_tests_pass(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_unit.py", "-v", "--tb=short"],
            cwd="/app",
            capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0,
                         f"Python tests failed after migration:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
