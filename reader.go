package main

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type TaskDef struct {
	Task    string  `json:"Task"`
	Hours   float64 `json:"Hours"`
	Cost    float64 `json:"Cost"`
	Start   int     `json:"Start"`
	Stop    int     `json:"Stop"`
	Comment string  `json:"Comment"`
}

type GridRow struct {
	ProviderID  string
	Date        time.Time
	Assignments []string
}

func ReadTaskCSV(path string) ([]TaskDef, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	records, err := r.ReadAll()
	if err != nil {
		return nil, err
	}

	var tasks []TaskDef
	for i, row := range records {
		if i == 0 {
			continue // skip header
		}
		if len(row) < 5 {
			continue
		}
		hours, _ := strconv.ParseFloat(row[1], 64)
		cost, _ := strconv.ParseFloat(row[2], 64)
		start, _ := strconv.Atoi(row[3])
		stop, _ := strconv.Atoi(row[4])
		comment := ""
		if len(row) > 5 {
			comment = row[5]
		}
		tasks = append(tasks, TaskDef{
			Task:    row[0],
			Hours:   hours,
			Cost:    cost,
			Start:   start,
			Stop:    stop,
			Comment: comment,
		})
	}
	return tasks, nil
}

func ReadParttimeCSV(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	records, err := r.ReadAll()
	if err != nil {
		return nil, err
	}

	var providers []string
	for i, row := range records {
		if i == 0 {
			continue
		}
		if len(row) > 0 && row[0] != "" {
			providers = append(providers, row[0])
		}
	}
	return providers, nil
}

type GridData struct {
	Providers []string
	Dates     []time.Time
	Entries   map[string]map[string][]string // provider -> date_str -> assignments
}

func ReadGridCSV(path string) (*GridData, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	r := csv.NewReader(f)
	records, err := r.ReadAll()
	if err != nil {
		return nil, err
	}

	if len(records) < 2 {
		return nil, fmt.Errorf("grid file too short")
	}

	header := records[0]
	dateStrs := header[1:]

	// Parse dates
	var dates []time.Time
	dateSet := make(map[string]bool)
	for _, ds := range dateStrs {
		t, err := parseDate(ds)
		if err != nil {
			continue
		}
		key := t.Format("2006-01-02")
		if !dateSet[key] {
			dateSet[key] = true
			dates = append(dates, t)
		}
	}

	providerSet := make(map[string]bool)
	var providers []string
	entries := make(map[string]map[string][]string)

	for i := 1; i < len(records); i++ {
		row := records[i]
		if len(row) == 0 {
			continue
		}
		pid := row[0]
		if pid == "" {
			continue
		}
		if !providerSet[pid] {
			providerSet[pid] = true
			providers = append(providers, pid)
		}
		if entries[pid] == nil {
			entries[pid] = make(map[string][]string)
		}
		for j := 1; j < len(row) && j < len(header); j++ {
			if row[j] == "" {
				continue
			}
			ds := header[j]
			t, err := parseDate(ds)
			if err != nil {
				continue
			}
			key := t.Format("2006-01-02")
			entries[pid][key] = append(entries[pid][key], row[j])
		}
	}

	return &GridData{
		Providers: providers,
		Dates:     dates,
		Entries:   entries,
	}, nil
}

func parseDate(s string) (time.Time, error) {
	s = strings.TrimSpace(s)
	formats := []string{
		"1/2/2006",
		"01/02/06",
		"1/02/06",
		"01/2/06",
		"2006-01-02",
	}
	for _, f := range formats {
		t, err := time.Parse(f, s)
		if err == nil {
			return t, nil
		}
	}
	return time.Time{}, fmt.Errorf("cannot parse date: %s", s)
}
