package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"sort"
	"strings"
	"time"
)

func main() {
	// Diagnostic/utility flags
	checkAvailFlag := flag.String("check-avail", "", "Check availability for a string")
	readTasksFlag := flag.String("read-tasks", "", "Read and output task CSV as JSON")
	readParttimeFlag := flag.String("read-parttime", "", "Read and output parttime CSV as JSON")
	readGridFlag := flag.String("read-grid", "", "Read and output grid CSV summary as JSON")
	listRoomsFlag := flag.Bool("list-rooms", false, "List room constants as JSON")
	listHighCostFlag := flag.Bool("list-high-cost", false, "List high cost tasks as JSON")

	// Solver flags
	objective := flag.String("objective", "avg_pain", "Objective function")
	specialty1cost := flag.Int("specialty1cost", 5, "Fixed specialty cost per month")
	gridPath := flag.String("grid", "", "Grid CSV path")
	taskPath := flag.String("task", "", "Task CSV path")
	parttimePath := flag.String("parttime", "", "Parttime CSV path")
	outputPath := flag.String("output", "", "Output xlsx path")
	var newPeriod periodFlag
	flag.Var(&newPeriod, "newPeriod", "New period start and end dates")
	action := flag.String("action", "assign", "Action: assign or evaluate_grid")

	flag.Parse()

	// Handle utility flags
	if *checkAvailFlag != "" || flag.NArg() > 0 && os.Args[1] == "--check-avail" {
		val := *checkAvailFlag
		if val == "" && flag.NArg() > 0 {
			val = flag.Arg(0)
		}
		fmt.Println(CheckAvail(val))
		return
	}

	if *readTasksFlag != "" {
		tasks, err := ReadTaskCSV(*readTasksFlag)
		if err != nil {
			log.Fatal(err)
		}
		enc := json.NewEncoder(os.Stdout)
		enc.Encode(tasks)
		return
	}

	if *readParttimeFlag != "" {
		providers, err := ReadParttimeCSV(*readParttimeFlag)
		if err != nil {
			log.Fatal(err)
		}
		enc := json.NewEncoder(os.Stdout)
		enc.Encode(providers)
		return
	}

	if *readGridFlag != "" {
		grid, err := ReadGridCSV(*readGridFlag)
		if err != nil {
			log.Fatal(err)
		}
		dateStrs := make([]string, len(grid.Dates))
		for i, d := range grid.Dates {
			dateStrs[i] = d.Format("2006-01-02")
		}
		result := map[string]interface{}{
			"providers": grid.Providers,
			"dates":     dateStrs,
		}
		enc := json.NewEncoder(os.Stdout)
		enc.Encode(result)
		return
	}

	if *listRoomsFlag {
		enc := json.NewEncoder(os.Stdout)
		enc.Encode(RoomList1To14)
		return
	}

	if *listHighCostFlag {
		enc := json.NewEncoder(os.Stdout)
		enc.Encode(HighCostTasks)
		return
	}

	// Solver mode
	if *action != "assign" {
		log.Fatal("Only 'assign' action is supported")
	}
	if *gridPath == "" || *taskPath == "" || *parttimePath == "" || *outputPath == "" {
		log.Fatal("--grid, --task, --parttime, --output, and --newPeriod are required")
	}
	if len(newPeriod.dates) != 2 {
		log.Fatal("--newPeriod requires exactly 2 dates")
	}

	_ = *objective // used for logging

	// Read input files
	tasks, err := ReadTaskCSV(*taskPath)
	if err != nil {
		log.Fatalf("Error reading tasks: %v", err)
	}
	grid, err := ReadGridCSV(*gridPath)
	if err != nil {
		log.Fatalf("Error reading grid: %v", err)
	}
	parttime, err := ReadParttimeCSV(*parttimePath)
	if err != nil {
		log.Fatalf("Error reading parttime: %v", err)
	}

	// Build task names and costs
	ors := make([]string, len(tasks))
	cost := make(map[string]float64)
	for i, t := range tasks {
		ors[i] = t.Task
		cost[t.Task] = t.Cost
	}

	// Sort dates
	sortedDates := make([]time.Time, len(grid.Dates))
	copy(sortedDates, grid.Dates)
	sort.Slice(sortedDates, func(i, j int) bool { return sortedDates[i].Before(sortedDates[j]) })

	// Process grid: compute avail, assigned, flags
	avail := make(map[string]int)
	assigned := make(map[string]int)
	specialty1Assigned := make(map[string]int)
	specialty2Assigned := make(map[string]int)
	sitecAssigned := make(map[string]int)
	specialty3Assigned := make(map[string]int)
	noCallAssigned := make(map[string]int)
	maxRoom := make(map[string]int)

	orsAssignedBase := make(map[string]int)
	for _, t := range tasks {
		orsAssignedBase[t.Task] = 0
	}

	// Initialize all assigned to 0
	for _, p := range grid.Providers {
		for _, d := range sortedDates {
			ds := dateStr(d)
			avail[key2(p, ds)] = 0
			for _, t := range tasks {
				assigned[key3(p, ds, t.Task)] = 0
			}
		}
	}

	// Process grid entries
	for _, p := range grid.Providers {
		for _, d := range sortedDates {
			ds := dateStr(d)
			assignments := grid.Entries[p][ds]

			// Compute availability
			av := 0
			for _, a := range assignments {
				if CheckAvail(a) {
					av++
				}
			}
			if av > avail[key2(p, ds)] {
				avail[key2(p, ds)] = av
			}

			// Compute assigned
			assignedMap := CheckAssigned(assignments, orsAssignedBase, ors)
			for k, v := range assignedMap {
				if v == 1 {
					assigned[key3(p, ds, k)] = 1
				}
			}

			// Detection flags
			for _, a := range assignments {
				if strings.Contains(a, DetectSpecialty1) {
					specialty1Assigned[p]++
				}
				if strings.Contains(a, DetectSpecialty2OnCall) {
					specialty2Assigned[p]++
				}
				if strings.Contains(a, DetectSiteC) {
					sitecAssigned[p]++
				}
				if strings.Contains(a, DetectSpecialty3) {
					specialty3Assigned[p]++
				}
				if strings.Contains(a, GridNoCall) {
					noCallAssigned[key2(p, ds)] = 1
				}
			}

			// UH-OR count for max rooms
			for _, a := range assignments {
				if a == GridRoom || a == GridNoCall || a == GridRoom8 {
					maxRoom[ds]++
				}
			}
		}
	}

	// Compute specialty1 cost per provider
	specialty1CostMap := make(map[string]float64)
	for _, p := range grid.Providers {
		if specialty1Assigned[p] >= 1 || sitecAssigned[p] >= 3 || specialty3Assigned[p] >= 3 {
			specialty1CostMap[p] = float64(*specialty1cost)
		} else {
			specialty1CostMap[p] = 0
		}
	}

	fmt.Fprintf(os.Stderr, "INFO:SchedulingApp:max_rooms computed\n")

	// Build solver input
	solverInput := &SolverInput{
		Cost:           cost,
		Avail:          avail,
		Assigned:       assigned,
		Specialty1Cost: specialty1CostMap,
		Providers:      grid.Providers,
		Days:           sortedDates,
		Ors:            ors,
		HighCostRooms:  []string{TaskRoom1, TaskRoom3},
		Objective:      *objective,
		Parttime:       parttime,
		NewPeriod:      [2]time.Time{newPeriod.dates[0], newPeriod.dates[1]},
		NoCallAssigned: noCallAssigned,
		MaxRoom:        maxRoom,
	}

	result := Solve(solverInput)

	fmt.Fprintf(os.Stderr, "INFO:SchedulingApp:Solver status: %d\n", result.Status)
	fmt.Fprintf(os.Stderr, "INFO:SchedulingApp:Time = %d milliseconds\n", result.WallTimeMs)
	fmt.Fprintf(os.Stderr, "INFO:SchedulingApp:Optimal objective value: %f\n", result.ObjectiveVal)

	// Write output
	dateStrs := make([]string, len(sortedDates))
	for i, d := range sortedDates {
		dateStrs[i] = dateStr(d)
	}
	err = WriteXLSX(*outputPath, result, dateStrs)
	if err != nil {
		log.Fatalf("Error writing output: %v", err)
	}
}

type periodFlag struct {
	dates []time.Time
}

func (p *periodFlag) String() string { return fmt.Sprintf("%v", p.dates) }
func (p *periodFlag) Set(s string) error {
	t, err := time.Parse("2006-01-02", s)
	if err != nil {
		return err
	}
	p.dates = append(p.dates, t)
	return nil
}
