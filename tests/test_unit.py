"""
Unit tests for the ResourceScheduling project.

Because src/inputs.py calls parse_args() at module level, we must patch
sys.argv before importing anything from src.main.
"""
import sys
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

# Patch sys.argv so that importing src.inputs doesn't fail
sys.argv = ["main.py", "--objective", "avg_pain",
            "--grid", "data/December/grid_v5.3.4.csv",
            "--task", "data/December/task.csv",
            "--parttime", "data/December/parttime.csv",
            "--newPeriod", "2020-12-01", "2020-12-31"]

from src.main import (
    check_avail,
    check_assigned,
    checkKey,
    checkIfAssigned,
    checkIfInRefX,
    clean_grid,
    get_avail_assigned,
    get_sol,
    get_optimal_pain,
    Room_list,
)
from src.utils import read_file, write_output


# ---------------------------------------------------------------------------
# check_avail
# ---------------------------------------------------------------------------
class TestCheckAvail(unittest.TestCase):
    """Tests for check_avail: determines if a schedule string means the
    provider is available for room assignment."""

    def test_uh_or_available(self):
        self.assertTrue(check_avail("SiteA - Room"))

    def test_uh_or_numbered_available(self):
        self.assertTrue(check_avail("SiteA - Room 5"))

    def test_no_call_available(self):
        self.assertTrue(check_avail("No Call"))

    def test_administrative_not_available(self):
        self.assertFalse(check_avail("Administrative"))

    def test_vacation_not_available(self):
        self.assertFalse(check_avail("Vacation"))

    def test_specialty2_oncall_not_available(self):
        self.assertFalse(check_avail("SiteA - Specialty2 OnCall -Weekday"))

    def test_post_call_not_available(self):
        self.assertFalse(check_avail("SiteA - PostShift"))

    def test_sitec_not_available(self):
        self.assertFalse(check_avail("SiteC - Center"))

    def test_personal_not_available(self):
        self.assertFalse(check_avail("Personal"))

    def test_late_shift_not_available(self):
        # Late shifts do not contain "SiteA - Room" or "No Call"
        self.assertFalse(check_avail("SiteA - EveShift1 3p"))
        self.assertFalse(check_avail("SiteA - EveShift2 12p"))

    def test_uh_or8_variant(self):
        # "SiteA - Room8" contains "SiteA - Room" so should be available
        self.assertTrue(check_avail("SiteA - Room8"))

    def test_board_runner_not_available(self):
        self.assertFalse(check_avail("SiteA - Coordinator 7a-3p"))

    def test_empty_string(self):
        self.assertFalse(check_avail(""))


# ---------------------------------------------------------------------------
# check_assigned
# ---------------------------------------------------------------------------
class TestCheckAssigned(unittest.TestCase):
    """Tests for check_assigned: marks which ORs/tasks are pre-assigned
    based on the assignment list from the grid."""

    def setUp(self):
        self.ors = np.array([
            "SiteA - Room 1", "SiteA - Room 2", "SiteA - Room 3", "SiteA - Room 4", "SiteA - Room 5",
            "SiteA - Room 6", "SiteA - Room 7", "SiteA - Room 8", "SiteA - Lead",
            "SiteA - EveShift1 3p", "SiteA - EveShift2 12p", "SiteA - Backup1", "SiteA - Backup2",
        ])
        self.base_assigned = {k: 0 for k in self.ors}

    def test_no_assignment(self):
        result = check_assigned(["SiteA - Room"], self.base_assigned, self.ors)
        # "SiteA - Room" is not in ors (it's just availability marker), so nothing set
        self.assertEqual(sum(result.values()), 0)

    def test_or_directly_assigned(self):
        result = check_assigned(["SiteA - Room 3"], self.base_assigned, self.ors)
        self.assertEqual(result["SiteA - Room 3"], 1)
        # Others remain 0
        self.assertEqual(result["SiteA - Room 1"], 0)

    def test_coordination_maps_to_lead(self):
        result = check_assigned(
            ["SiteA - Coordinator 7a-3p"], self.base_assigned, self.ors
        )
        self.assertEqual(result["SiteA - Lead"], 1)

    def test_nan_skipped(self):
        result = check_assigned([float("nan")], self.base_assigned, self.ors)
        self.assertEqual(sum(result.values()), 0)

    def test_multiple_assignments(self):
        result = check_assigned(
            ["SiteA - Room 1", "SiteA - Backup1"], self.base_assigned, self.ors
        )
        self.assertEqual(result["SiteA - Room 1"], 1)
        self.assertEqual(result["SiteA - Backup1"], 1)
        self.assertEqual(result["SiteA - Room 2"], 0)

    def test_does_not_mutate_input(self):
        original = self.base_assigned.copy()
        check_assigned(["SiteA - Room 5"], self.base_assigned, self.ors)
        self.assertEqual(self.base_assigned, original)

    def test_unrecognized_assignment_ignored(self):
        result = check_assigned(["Holiday", "Vacation"], self.base_assigned, self.ors)
        self.assertEqual(sum(result.values()), 0)

    def test_late_shift_assigned(self):
        result = check_assigned(["SiteA - EveShift1 3p"], self.base_assigned, self.ors)
        self.assertEqual(result["SiteA - EveShift1 3p"], 1)

    def test_3rd_call_assigned(self):
        result = check_assigned(["SiteA - Backup2"], self.base_assigned, self.ors)
        self.assertEqual(result["SiteA - Backup2"], 1)


# ---------------------------------------------------------------------------
# checkKey
# ---------------------------------------------------------------------------
class TestCheckKey(unittest.TestCase):
    """Tests for checkKey: checks if ANY provider has a given (date, room)
    already in the reference dict."""

    def setUp(self):
        self.providers = np.array(["P1", "P2", "P3"])

    def test_no_match(self):
        refX = {}
        result = checkKey(self.providers, refX, ["P1", "2020-12-01", "SiteA - Room 7"],
                          ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_exact_match(self):
        refX = {("P1", "2020-12-01", "SiteA - Room 7"): 1}
        result = checkKey(self.providers, refX, ["P1", "2020-12-01", "SiteA - Room 7"],
                          ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_different_provider_same_date_or(self):
        # checkKey iterates all providers for the given (date, room),
        # so if P2 has it, the check returns 1 even when key_list[0] is P1
        refX = {("P2", "2020-12-01", "SiteA - Room 7"): 1}
        result = checkKey(self.providers, refX, ["P1", "2020-12-01", "SiteA - Room 7"],
                          ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_different_date_no_match(self):
        refX = {("P1", "2020-12-02", "SiteA - Room 7"): 1}
        result = checkKey(self.providers, refX, ["P1", "2020-12-01", "SiteA - Room 7"],
                          ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_different_or_no_match(self):
        refX = {("P1", "2020-12-01", "SiteA - Room 8"): 1}
        result = checkKey(self.providers, refX, ["P1", "2020-12-01", "SiteA - Room 7"],
                          ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# checkIfAssigned
# ---------------------------------------------------------------------------
class TestCheckIfAssigned(unittest.TestCase):
    """Tests for checkIfAssigned: checks if a given provider on a given day
    already has ANY room assignment in the reference dict."""

    def setUp(self):
        self.providers = np.array(["P1", "P2", "P3"])

    def test_no_match(self):
        refX = {}
        result = checkIfAssigned(self.providers, refX,
                                 ["P1", "2020-12-01", "SiteA - Room 7"],
                                 ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_same_provider_different_or(self):
        # Provider P1 on same date but different room => still assigned
        refX = {("P1", "2020-12-01", "SiteA - Room 3"): 1}
        result = checkIfAssigned(self.providers, refX,
                                 ["P1", "2020-12-01", "SiteA - Room 7"],
                                 ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_different_provider_not_matched(self):
        # checkIfAssigned only checks the provider in key_list[0]
        refX = {("P2", "2020-12-01", "SiteA - Room 3"): 1}
        result = checkIfAssigned(self.providers, refX,
                                 ["P1", "2020-12-01", "SiteA - Room 7"],
                                 ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_different_date_not_matched(self):
        refX = {("P1", "2020-12-02", "SiteA - Room 3"): 1}
        result = checkIfAssigned(self.providers, refX,
                                 ["P1", "2020-12-01", "SiteA - Room 7"],
                                 ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_custom_or_list(self):
        custom_ors = ["SiteA - Room 1", "SiteA - Room 2"]
        refX = {("P1", "2020-12-01", "SiteA - Room 5"): 1}
        # Room 5 not in custom list, so not found
        result = checkIfAssigned(self.providers, refX,
                                 ["P1", "2020-12-01", "SiteA - Room 5"],
                                 ("P1", "2020-12-01", "SiteA - Room 5"),
                                 RoomListToCheck=custom_ors)
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# checkIfInRefX
# ---------------------------------------------------------------------------
class TestCheckIfInRefX(unittest.TestCase):
    """Tests for checkIfInRefX: combines checkKey and checkIfAssigned.
    Returns 0 if neither finds a match, 1 if either does."""

    def setUp(self):
        self.providers = np.array(["P1", "P2", "P3"])

    def test_nothing_in_ref(self):
        result = checkIfInRefX(self.providers, {},
                               ["P1", "2020-12-01", "SiteA - Room 7"],
                               ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)

    def test_provider_has_same_or(self):
        refX = {("P1", "2020-12-01", "SiteA - Room 7"): 1}
        result = checkIfInRefX(self.providers, refX,
                               ["P1", "2020-12-01", "SiteA - Room 7"],
                               ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_provider_has_different_or_same_day(self):
        # checkIfAssigned will find it (same provider, same date, any room)
        refX = {("P1", "2020-12-01", "SiteA - Room 3"): 1}
        result = checkIfInRefX(self.providers, refX,
                               ["P1", "2020-12-01", "SiteA - Room 7"],
                               ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_other_provider_same_date_or(self):
        # checkKey will find it (any provider, same date+room)
        refX = {("P2", "2020-12-01", "SiteA - Room 7"): 1}
        result = checkIfInRefX(self.providers, refX,
                               ["P1", "2020-12-01", "SiteA - Room 7"],
                               ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 1)

    def test_completely_different_date(self):
        refX = {("P1", "2020-12-05", "SiteA - Room 7"): 1}
        result = checkIfInRefX(self.providers, refX,
                               ["P1", "2020-12-01", "SiteA - Room 7"],
                               ("P1", "2020-12-01", "SiteA - Room 7"))
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# clean_grid
# ---------------------------------------------------------------------------
class TestCleanGrid(unittest.TestCase):
    """Tests for clean_grid: transforms the wide-format grid into a long
    format with derived columns for availability and assignment flags."""

    def setUp(self):
        self.tasks = pd.DataFrame({
            "Task": ["SiteA - Room 1", "SiteA - Room 2", "SiteA - Lead",
                     "SiteA - EveShift1 3p", "SiteA - Backup1", "SiteA - Backup2"],
            "Hours": [10, 9, 10, 7, 4, 3],
            "Cost": [7, 5, 10, 4, 2, 4],
        })
        self.new_period = [date(2020, 12, 1), date(2020, 12, 3)]

    def _make_grid(self, data):
        return pd.DataFrame(data)

    def test_basic_shape(self):
        grid = self._make_grid({
            "ProviderID": ["P1", "P2"],
            "12/01/20": ["SiteA - Room", "Administrative"],
            "12/02/20": ["SiteA - Room", "SiteA - Room"],
            "12/03/20": ["No Call", "SiteC - Center"],
        })
        result, n_room = clean_grid(grid, self.tasks, self.new_period)
        # Should have ProviderID, Date, Assignment, avail, and derived columns
        self.assertIn("avail", result.columns)
        self.assertIn("assigned", result.columns)
        self.assertIn("specialty1_assigned", result.columns)
        self.assertIn("no_call_assigned", result.columns)
        self.assertIn("uhor_count", result.columns)

    def test_availability_count(self):
        grid = self._make_grid({
            "ProviderID": ["P1", "P2"],
            "12/01/20": ["SiteA - Room", "Administrative"],
            "12/02/20": ["SiteA - Room", "SiteA - Room"],
        })
        result, n_room = clean_grid(grid, self.tasks, self.new_period)
        # P1 available both days, P2 available only 12/02
        p1 = result[result.ProviderID == "P1"]
        self.assertEqual(p1["avail"].sum(), 2)
        p2 = result[result.ProviderID == "P2"]
        self.assertEqual(p2["avail"].sum(), 1)

    def test_n_room_is_max_daily_availability(self):
        grid = self._make_grid({
            "ProviderID": ["P1", "P2", "P3"],
            "12/01/20": ["SiteA - Room", "SiteA - Room", "Administrative"],
            "12/02/20": ["SiteA - Room", "SiteA - Room", "SiteA - Room"],
        })
        _, n_room = clean_grid(grid, self.tasks, self.new_period)
        # On 12/02 all 3 are available, so n_room = 3
        self.assertEqual(n_room, 3)

    def test_specialty1_flag(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["SiteA - Specialty1 OnCall"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        self.assertTrue(result["specialty1_assigned"].any())

    def test_specialty2_flag(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["SiteA - Specialty2 OnCall -Weekday"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        self.assertTrue(result["specialty2_assigned"].any())

    def test_sitec_flag(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["SiteC - Center"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        self.assertTrue(result["sitec_assigned"].any())

    def test_no_call_flag(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["No Call"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        self.assertTrue(result["no_call_assigned"].any())

    def test_uhor_count_flag(self):
        grid = self._make_grid({
            "ProviderID": ["P1", "P2"],
            "12/01/20": ["SiteA - Room", "Administrative"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        p1 = result[result.ProviderID == "P1"]
        p2 = result[result.ProviderID == "P2"]
        self.assertTrue(p1["uhor_count"].all())
        self.assertFalse(p2["uhor_count"].any())

    def test_dates_converted_to_date_objects(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["SiteA - Room"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        self.assertIsInstance(result["Date"].iloc[0], date)

    def test_pre_assigned_or_detected(self):
        grid = self._make_grid({
            "ProviderID": ["P1"],
            "12/01/20": ["SiteA - Room 1"],
        })
        result, _ = clean_grid(grid, self.tasks, self.new_period)
        assigned_dict = result["assigned"].iloc[0]
        self.assertEqual(assigned_dict["SiteA - Room 1"], 1)
        self.assertEqual(assigned_dict["SiteA - Room 2"], 0)


# ---------------------------------------------------------------------------
# get_avail_assigned
# ---------------------------------------------------------------------------
class TestGetAvailAssigned(unittest.TestCase):
    """Tests for get_avail_assigned: pivots the cleaned grid into
    (provider, date) -> availability and (provider, date, room) -> assigned dicts."""

    def _make_cleaned_grid(self):
        ors = ["SiteA - Room 1", "SiteA - Room 2"]
        return pd.DataFrame({
            "ProviderID": ["P1", "P1", "P2", "P2"],
            "Date": [date(2020, 12, 1), date(2020, 12, 2),
                     date(2020, 12, 1), date(2020, 12, 2)],
            "avail": [1, 0, 1, 1],
            "assigned": [
                {"SiteA - Room 1": 0, "SiteA - Room 2": 0},
                {"SiteA - Room 1": 0, "SiteA - Room 2": 0},
                {"SiteA - Room 1": 1, "SiteA - Room 2": 0},
                {"SiteA - Room 1": 0, "SiteA - Room 2": 1},
            ],
        })

    def test_avail_dict_structure(self):
        grid = self._make_cleaned_grid()
        avail, _ = get_avail_assigned(grid)
        self.assertEqual(avail[("P1", date(2020, 12, 1))], 1)
        self.assertEqual(avail[("P1", date(2020, 12, 2))], 0)
        self.assertEqual(avail[("P2", date(2020, 12, 2))], 1)

    def test_assigned_dict_structure(self):
        grid = self._make_cleaned_grid()
        _, assigned = get_avail_assigned(grid)
        # P2 has Room 1 assigned on 12/01
        self.assertEqual(assigned[("P2", date(2020, 12, 1), "SiteA - Room 1")], 1)
        self.assertEqual(assigned[("P2", date(2020, 12, 1), "SiteA - Room 2")], 0)
        # P2 has Room 2 assigned on 12/02
        self.assertEqual(assigned[("P2", date(2020, 12, 2), "SiteA - Room 2")], 1)

    def test_unassigned_provider(self):
        grid = self._make_cleaned_grid()
        _, assigned = get_avail_assigned(grid)
        # P1 has nothing assigned
        self.assertEqual(assigned[("P1", date(2020, 12, 1), "SiteA - Room 1")], 0)
        self.assertEqual(assigned[("P1", date(2020, 12, 1), "SiteA - Room 2")], 0)


# ---------------------------------------------------------------------------
# read_file / write_output
# ---------------------------------------------------------------------------
class TestReadFile(unittest.TestCase):
    """Tests for read_file utility."""

    def test_read_csv(self):
        df = read_file(Path("data/December/task.csv"))
        self.assertIn("Task", df.columns)
        self.assertIn("Cost", df.columns)
        self.assertGreater(len(df), 0)

    def test_read_csv_has_expected_tasks(self):
        df = read_file(Path("data/December/task.csv"))
        tasks = df.Task.tolist()
        self.assertIn("SiteA - Room 1", tasks)
        self.assertIn("SiteA - Lead", tasks)
        self.assertIn("SiteA - Backup1", tasks)

    def test_read_nonexistent_raises(self):
        with self.assertRaises(Exception):
            read_file(Path("nonexistent.csv"))

    def test_read_unsupported_type_raises(self):
        with self.assertRaises(NotImplementedError):
            read_file(Path("data.json"))

    def test_read_multiple_csvs(self):
        # read_file supports a list of Paths, merging on ProviderID
        df = read_file([
            Path("data/December/grid_v5.3.4.csv"),
            Path("data/December/grid_v5.4.csv"),
        ])
        self.assertIn("ProviderID", df.columns)


class TestWriteOutput(unittest.TestCase):
    """Tests for write_output utility."""

    def test_write_and_read_back(self):
        import tempfile
        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"X": [5.123, 6.456]})
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = Path(f.name)
        try:
            write_output({"sheet1": df1, "sheet2": df2}, path)
            # Verify file exists and has the right sheets
            import openpyxl
            wb = openpyxl.load_workbook(path)
            self.assertEqual(set(wb.sheetnames), {"sheet1", "sheet2"})
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# get_sol (with mock solver variables)
# ---------------------------------------------------------------------------
class TestGetSol(unittest.TestCase):
    """Tests for get_sol: extracts the assignment solution into a DataFrame."""

    def _mock_var(self, val):
        m = MagicMock()
        m.solution_value.return_value = val
        return m

    def test_basic_solution(self):
        providers = ["P1", "P2"]
        days = [date(2020, 12, 1), date(2020, 12, 2)]
        ors = ["SiteA - Room 1", "SiteA - Room 2"]

        x = {}
        assigned = {}
        for i in providers:
            for j in days:
                for k in ors:
                    x[i, j, k] = self._mock_var(0)
                    assigned[i, j, k] = 0

        # Assign P1 to Room 1 on 12/01 via solver
        x["P1", date(2020, 12, 1), "SiteA - Room 1"] = self._mock_var(1)
        # Assign P2 to Room 2 on 12/02 via pre-assignment
        assigned["P2", date(2020, 12, 2), "SiteA - Room 2"] = 1

        df = get_sol(x, assigned, days, providers)
        self.assertEqual(df.loc["P1", date(2020, 12, 1)], "SiteA - Room 1")
        self.assertEqual(df.loc["P2", date(2020, 12, 2)], "SiteA - Room 2")

    def test_call_assignments_excluded(self):
        """2nd Call and 3rd Call should not appear in the solution grid."""
        providers = ["P1"]
        days = [date(2020, 12, 1)]
        ors = ["SiteA - Room 1", "SiteA - Backup1"]

        x = {}
        assigned = {}
        for k in ors:
            x["P1", date(2020, 12, 1), k] = self._mock_var(1)
            assigned["P1", date(2020, 12, 1), k] = 0

        df = get_sol(x, assigned, days, providers)
        # Room 1 should be assigned, but Backup1 should be excluded
        self.assertEqual(df.loc["P1", date(2020, 12, 1)], "SiteA - Room 1")

    def test_no_double_assignment(self):
        """If solver=1 and assigned=1, sum=2 != 1, so it's NOT placed."""
        providers = ["P1"]
        days = [date(2020, 12, 1)]
        ors = ["SiteA - Room 1"]

        x = {("P1", date(2020, 12, 1), "SiteA - Room 1"): self._mock_var(1)}
        assigned = {("P1", date(2020, 12, 1), "SiteA - Room 1"): 1}

        df = get_sol(x, assigned, days, providers)
        self.assertTrue(pd.isna(df.loc["P1", date(2020, 12, 1)]))


# ---------------------------------------------------------------------------
# get_optimal_pain (with mock solver variables)
# ---------------------------------------------------------------------------
class TestGetOptimalCost(unittest.TestCase):
    """Tests for get_optimal_pain: computes pain metrics per provider."""

    def _mock_var(self, val):
        m = MagicMock()
        m.solution_value.return_value = val
        return m

    def _setup(self):
        providers = ["P1", "P2"]
        days = np.array([date(2020, 12, 1), date(2020, 12, 2)])
        # Must include Room 1-5 because get_optimal_pain hardcodes lookups for these columns
        ors = np.array(["SiteA - Room 1", "SiteA - Room 2", "SiteA - Room 3", "SiteA - Room 4", "SiteA - Room 5"])
        cost = {"SiteA - Room 1": 7, "SiteA - Room 2": 5, "SiteA - Room 3": 3, "SiteA - Room 4": 2, "SiteA - Room 5": 1}
        specialty1_cost = {"P1": 0, "P2": 3}

        x = {}
        assigned = {}
        avail = {}
        for i in providers:
            for j in days:
                avail[i, j] = 1
                for k in ors:
                    x[i, j, k] = self._mock_var(0)
                    assigned[i, j, k] = 0

        return providers, days, ors, cost, specialty1_cost, x, assigned, avail

    def test_zero_assignments_still_has_specialty1_cost(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # P2 has specialty1_cost=3, no room assignments, so Total Cost = 3
        self.assertEqual(df.loc["P2", "Total Cost"], 3)
        self.assertEqual(df.loc["P2", "Total SiteA Room Cost"], 0)

    def test_pain_calculation_with_assignment(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        # P1 assigned to Room 1 on day 1 via solver
        x["P1", date(2020, 12, 1), "SiteA - Room 1"] = self._mock_var(1)
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # P1: Total SiteA Room Cost = 7 * 1 = 7, specialty1_cost = 0, Total Cost = 7
        self.assertEqual(df.loc["P1", "Total SiteA Room Cost"], 7)
        self.assertEqual(df.loc["P1", "Total Cost"], 7)

    def test_room_days_count(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        # P1 available both days
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        self.assertEqual(df.loc["P1", "SiteA Room days"], 2)

    def test_avg_pain_computation(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        x["P1", date(2020, 12, 1), "SiteA - Room 1"] = self._mock_var(1)
        x["P1", date(2020, 12, 2), "SiteA - Room 2"] = self._mock_var(1)
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # Total Cost = 7 + 5 = 12, OR days = 2, Avg = 6
        self.assertEqual(df.loc["P1", "Avg. Cost"], 6)

    def test_unavailable_provider_excluded(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        # Make P1 unavailable
        for j in days:
            avail["P1", j] = 0
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # P1 should have NaN (room_days=0 so skipped)
        self.assertTrue(pd.isna(df.loc["P1", "Total Cost"]))

    def test_pre_assigned_counted_in_pain(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        # P1 has OR 2 pre-assigned on day 1
        assigned["P1", date(2020, 12, 1), "SiteA - Room 2"] = 1
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # Total SiteA Room Cost = 5 * 1 = 5
        self.assertEqual(df.loc["P1", "Total SiteA Room Cost"], 5)

    def test_or_specific_columns(self):
        providers, days, ors, cost, specialty1_cost, x, assigned, avail = self._setup()
        x["P1", date(2020, 12, 1), "SiteA - Room 1"] = self._mock_var(1)
        x["P1", date(2020, 12, 2), "SiteA - Room 1"] = self._mock_var(1)
        df = get_optimal_pain(x, providers, days, ors, cost, specialty1_cost, avail, assigned)
        # P1 assigned to Room 1 on both days
        self.assertEqual(df.loc["P1", "SiteA - Room 1"], 2)
        self.assertEqual(df.loc["P1", "SiteA - Room 2"], 0)


# ---------------------------------------------------------------------------
# Integration: end-to-end with real data files
# ---------------------------------------------------------------------------
class TestIntegration(unittest.TestCase):
    """Integration tests that run the full pipeline on the real data files
    to verify nothing is broken end-to-end."""

    @classmethod
    def setUpClass(cls):
        cls.task_df = read_file(Path("data/December/task.csv"))
        cls.grid_df = read_file(Path("data/December/grid_v5.3.4.csv"))
        cls.parttime_df = read_file(Path("data/December/parttime.csv"))
        cls.new_period = [date(2020, 12, 1), date(2020, 12, 31)]

    def test_clean_grid_on_real_data(self):
        cleaned, n_room = clean_grid(
            self.grid_df.copy(), self.task_df, self.new_period
        )
        self.assertGreater(len(cleaned), 0)
        self.assertGreater(n_room, 0)
        # Verify expected columns exist
        for col in ["avail", "assigned", "specialty1_assigned", "specialty2_assigned",
                     "sitec_assigned", "no_call_assigned", "uhor_count"]:
            self.assertIn(col, cleaned.columns)

    def test_get_avail_assigned_on_real_data(self):
        cleaned, _ = clean_grid(
            self.grid_df.copy(), self.task_df, self.new_period
        )
        avail, assigned = get_avail_assigned(cleaned)
        # Should have entries for all provider-date combos
        self.assertGreater(len(avail), 0)
        self.assertGreater(len(assigned), 0)
        # All avail values should be 0 or 1+
        for v in avail.values():
            self.assertGreaterEqual(v, 0)

    def test_cost_dict_from_task_file(self):
        cost = dict(zip(self.task_df.Task, self.task_df.Cost))
        self.assertEqual(cost["SiteA - Room 1"], 7)
        self.assertEqual(cost["SiteA - Room 2"], 5)
        self.assertEqual(cost["SiteA - Lead"], 10)
        self.assertIn("SiteA - Backup1", cost)
        self.assertIn("SiteA - Backup2", cost)

    def test_parttime_providers_in_grid(self):
        parttime_ids = self.parttime_df.ProviderID.values
        grid_ids = self.grid_df.ProviderID.unique()
        # All parttime providers should exist in the grid
        for pid in parttime_ids:
            self.assertIn(pid, grid_ids,
                          f"Part-time provider {pid} not found in grid")

    def test_task_pain_roomdering(self):
        """OR 1 should have the highest pain, decreasing for higher-numbered ORs."""
        cost = dict(zip(self.task_df.Task, self.task_df.Cost))
        self.assertGreater(cost["SiteA - Room 1"], cost["SiteA - Room 2"])
        self.assertGreater(cost["SiteA - Room 2"], cost["SiteA - Room 3"])
        self.assertGreater(cost["SiteA - Room 3"], cost["SiteA - Room 4"])

    def test_all_dates_in_december_2020(self):
        cleaned, _ = clean_grid(
            self.grid_df.copy(), self.task_df, self.new_period
        )
        for d in cleaned.Date.unique():
            self.assertEqual(d.year, 2020)
            self.assertEqual(d.month, 12)


if __name__ == "__main__":
    unittest.main()
