package main

import (
	"math"
	"strings"
)

func CheckAvail(s string) bool {
	if strings.Contains(s, GridRoom) {
		return true
	}
	if strings.Contains(s, GridNoCall) {
		return true
	}
	return false
}

func CheckAssigned(assignments []string, orAssigned map[string]int, ors []string) map[string]int {
	out := make(map[string]int)
	for k, v := range orAssigned {
		out[k] = v
	}
	for _, a := range assignments {
		if isNaN(a) {
			continue
		}
		if contains(ors, a) {
			out[a] = 1
		} else if strings.Contains(a, GridCoordinator) {
			out[TaskLead] = 1
		}
	}
	return out
}

func isNaN(s string) bool {
	return s == "" || s == "nan" || s == "NaN"
}

func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

func containsSubstr(s, substr string) bool {
	return strings.Contains(s, substr)
}

func sumFloat(vals []float64) float64 {
	s := 0.0
	for _, v := range vals {
		s += v
	}
	return s
}

func minFloat(a, b float64) float64 {
	return math.Min(a, b)
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
