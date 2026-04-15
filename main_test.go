package main

import (
	"testing"
)

func TestCheckAvailRoom(t *testing.T) {
	if !CheckAvail("SiteA - Room") {
		t.Error("SiteA - Room should be available")
	}
}

func TestCheckAvailRoomNumbered(t *testing.T) {
	if !CheckAvail("SiteA - Room 5") {
		t.Error("SiteA - Room 5 should be available")
	}
}

func TestCheckAvailNoCall(t *testing.T) {
	if !CheckAvail("No Call") {
		t.Error("No Call should be available")
	}
}

func TestCheckAvailAdministrative(t *testing.T) {
	if CheckAvail("Administrative") {
		t.Error("Administrative should not be available")
	}
}

func TestCheckAvailVacation(t *testing.T) {
	if CheckAvail("Vacation") {
		t.Error("Vacation should not be available")
	}
}

func TestCheckAvailEveShift(t *testing.T) {
	if CheckAvail("SiteA - EveShift1 3p") {
		t.Error("EveShift should not be available")
	}
}

func TestCheckAvailEmpty(t *testing.T) {
	if CheckAvail("") {
		t.Error("Empty string should not be available")
	}
}

func TestCheckAssignedOR(t *testing.T) {
	ors := []string{"SiteA - Room 1", "SiteA - Room 2", "SiteA - Lead"}
	base := map[string]int{"SiteA - Room 1": 0, "SiteA - Room 2": 0, "SiteA - Lead": 0}
	result := CheckAssigned([]string{"SiteA - Room 1"}, base, ors)
	if result["SiteA - Room 1"] != 1 {
		t.Error("Room 1 should be assigned")
	}
	if result["SiteA - Room 2"] != 0 {
		t.Error("Room 2 should not be assigned")
	}
}

func TestCheckAssignedCoordinator(t *testing.T) {
	ors := []string{"SiteA - Lead"}
	base := map[string]int{"SiteA - Lead": 0}
	result := CheckAssigned([]string{"SiteA - Coordinator 7a-3p"}, base, ors)
	if result["SiteA - Lead"] != 1 {
		t.Error("Lead should be assigned when coordinator is present")
	}
}

func TestCheckAssignedNoMutation(t *testing.T) {
	ors := []string{"SiteA - Room 1"}
	base := map[string]int{"SiteA - Room 1": 0}
	CheckAssigned([]string{"SiteA - Room 1"}, base, ors)
	if base["SiteA - Room 1"] != 0 {
		t.Error("Original map should not be mutated")
	}
}

func TestRoomFunc(t *testing.T) {
	if Room(7) != "SiteA - Room 7" {
		t.Errorf("Room(7) = %s, want SiteA - Room 7", Room(7))
	}
	if Room(10) != "SiteA - Room 10" {
		t.Errorf("Room(10) = %s, want SiteA - Room 10", Room(10))
	}
}

func TestRoomList(t *testing.T) {
	if len(RoomList1To14) != 14 {
		t.Errorf("RoomList1To14 has %d items, want 14", len(RoomList1To14))
	}
	if RoomList1To14[0] != TaskRoom1 {
		t.Errorf("First room = %s, want %s", RoomList1To14[0], TaskRoom1)
	}
}

func TestHighCostTasks(t *testing.T) {
	if len(HighCostTasks) != 5 {
		t.Errorf("HighCostTasks has %d items, want 5", len(HighCostTasks))
	}
}

func TestReadTaskCSV(t *testing.T) {
	tasks, err := ReadTaskCSV("data/December/task.csv")
	if err != nil {
		t.Fatalf("Failed to read task CSV: %v", err)
	}
	if len(tasks) != 27 {
		t.Errorf("Got %d tasks, want 27", len(tasks))
	}
	if tasks[0].Task != "SiteA - Room 1" {
		t.Errorf("First task = %s, want SiteA - Room 1", tasks[0].Task)
	}
	if tasks[0].Cost != 7 {
		t.Errorf("First task cost = %f, want 7", tasks[0].Cost)
	}
}

func TestReadParttimeCSV(t *testing.T) {
	providers, err := ReadParttimeCSV("data/December/parttime.csv")
	if err != nil {
		t.Fatalf("Failed to read parttime CSV: %v", err)
	}
	if len(providers) != 3 {
		t.Errorf("Got %d providers, want 3", len(providers))
	}
}

func TestReadGridCSV(t *testing.T) {
	grid, err := ReadGridCSV("data/December/grid_v5.3.4.csv")
	if err != nil {
		t.Fatalf("Failed to read grid CSV: %v", err)
	}
	if len(grid.Providers) == 0 {
		t.Error("No providers found")
	}
	if len(grid.Dates) == 0 {
		t.Error("No dates found")
	}
}
