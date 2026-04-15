package main

/*
#cgo LDFLAGS: -lCbcSolver -lCbc -lCgl -lOsiClp -lClp -lCoinUtils -lm -lpthread -lstdc++
#cgo CFLAGS: -I/usr/include/coin

#include <stdlib.h>
#include <Cbc_C_Interface.h>
*/
import "C"
import (
	"fmt"
	"math"
	"os"
	"time"
	"unsafe"
)

type SolverResult struct {
	Status        int
	ObjectiveVal  float64
	WallTimeMs    int64
	Solution      map[string]map[string]string
	ProviderPain  map[string]map[string]float64
}

type SolverInput struct {
	Cost           map[string]float64
	Avail          map[string]int
	Assigned       map[string]int
	Specialty1Cost map[string]float64
	Providers      []string
	Days           []time.Time
	Ors            []string
	HighCostRooms  []string
	Objective      string
	Parttime       []string
	NewPeriod      [2]time.Time
	NoCallAssigned map[string]int
	MaxRoom        map[string]int
}

func key2(a, b string) string { return a + "|" + b }
func key3(a, b, c string) string { return a + "|" + b + "|" + c }
func dateStr(t time.Time) string { return t.Format("2006-01-02") }

// constraint bound types
const (
	BND_FX = iota // lb == ub (equality)
	BND_UP        // <= ub
	BND_LO        // >= lb
)

type constraint struct {
	indices []int
	coeffs  []float64
	bndType int
	lb, ub  float64
}

func buildConstraints(input *SolverInput, providers []string, days []time.Time, ors []string,
	xIdx map[string]int, zAvgIdx map[string]int, avgOfAvgIdx int,
	newStart, newEnd time.Time) []constraint {
	return nil
}

func Solve(input *SolverInput) *SolverResult {
	startTime := time.Now()

	providers := input.Providers
	days := input.Days
	ors := input.Ors
	newStart := input.NewPeriod[0]
	newEnd := input.NewPeriod[1]

	// Create column index mapping (0-based for CBC)
	xIdx := make(map[string]int)
	colCount := 0

	for _, i := range providers {
		for _, j := range days {
			js := dateStr(j)
			for _, k := range ors {
				xIdx[key3(i, js, k)] = colCount
				colCount++
			}
		}
	}

	zAvgIdx := make(map[string]int)
	for _, i := range providers {
		zAvgIdx[i] = colCount
		colCount++
	}

	avgOfAvgIdx := colCount
	colCount++

	// Column bounds, objective coefficients, and types
	collb := make([]float64, colCount)
	colub := make([]float64, colCount)
	obj := make([]float64, colCount)
	isInteger := make([]bool, colCount)

	// Set x variable bounds
	for _, i := range providers {
		for _, j := range days {
			js := dateStr(j)
			for _, k := range ors {
				idx := xIdx[key3(i, js, k)]
				isInteger[idx] = true
				if j.Before(newStart) || input.Assigned[key3(i, js, k)] == 1 ||
					getOrsIndex(k, ors) >= 21 || input.Avail[key2(i, js)] == 0 {
					collb[idx] = 0
					colub[idx] = 0
				} else {
					collb[idx] = 0
					colub[idx] = 1
				}
			}
		}
	}

	// z_avg variables (continuous, 0-100)
	for _, i := range providers {
		idx := zAvgIdx[i]
		collb[idx] = 0
		colub[idx] = 100
	}

	// AvgOfAvgPain (continuous, >= 0)
	collb[avgOfAvgIdx] = 0
	colub[avgOfAvgIdx] = 1e20
	obj[avgOfAvgIdx] = 1.0 // minimize this

	// Build constraints
	constraints := buildConstraints(input, providers, days, ors, xIdx, zAvgIdx, avgOfAvgIdx, newStart, newEnd)

	fmt.Fprintf(os.Stderr, "DEBUG: Columns: %d, Constraints: %d\n", colCount, len(constraints))

	// Build CSC (Compressed Sparse Column) matrix for CBC
	numrows := len(constraints)

	// Row bounds
	rowlb := make([]float64, numrows)
	rowub := make([]float64, numrows)
	for ri, c := range constraints {
		switch c.bndType {
		case BND_FX:
			rowlb[ri] = c.lb
			rowub[ri] = c.ub
		case BND_UP:
			rowlb[ri] = -1e30
			rowub[ri] = c.ub
		case BND_LO:
			rowlb[ri] = c.lb
			rowub[ri] = 1e30
		}
	}

	// Build COO (coordinate) format, then convert to CSC
	type entry struct {
		row int
		col int
		val float64
	}
	var entries []entry
	for ri, c := range constraints {
		for ei, ci := range c.indices {
			if ci >= 0 && ci < colCount {
				entries = append(entries, entry{ri, ci, c.coeffs[ei]})
			}
		}
	}

	// Convert COO to CSC
	start := make([]C.CoinBigIndex, colCount+1)
	// Count entries per column
	colCounts := make([]int, colCount)
	for _, e := range entries {
		colCounts[e.col]++
	}
	// Compute start offsets
	start[0] = 0
	for c := 0; c < colCount; c++ {
		start[c+1] = start[c] + C.CoinBigIndex(colCounts[c])
	}
	// Fill index and value arrays
	nnz := len(entries)
	index := make([]C.int, nnz)
	value := make([]C.double, nnz)
	pos := make([]int, colCount)
	for _, e := range entries {
		c := e.col
		p := int(start[c]) + pos[c]
		index[p] = C.int(e.row)
		value[p] = C.double(e.val)
		pos[c]++
	}

	// Create CBC model
	model := C.Cbc_newModel()
	defer C.Cbc_deleteModel(model)

	// Convert Go slices to C arrays
	cCollb := make([]C.double, colCount)
	cColub := make([]C.double, colCount)
	cObj := make([]C.double, colCount)
	for i := 0; i < colCount; i++ {
		cCollb[i] = C.double(collb[i])
		cColub[i] = C.double(colub[i])
		cObj[i] = C.double(obj[i])
	}
	cRowlb := make([]C.double, numrows)
	cRowub := make([]C.double, numrows)
	for i := 0; i < numrows; i++ {
		cRowlb[i] = C.double(rowlb[i])
		cRowub[i] = C.double(rowub[i])
	}

	var startPtr *C.CoinBigIndex
	var indexPtr *C.int
	var valuePtr *C.double
	if nnz > 0 {
		startPtr = &start[0]
		indexPtr = &index[0]
		valuePtr = &value[0]
	} else {
		startPtr = &start[0]
		indexPtr = nil
		valuePtr = nil
	}

	C.Cbc_loadProblem(model,
		C.int(colCount), C.int(numrows),
		startPtr, indexPtr, valuePtr,
		&cCollb[0], &cColub[0], &cObj[0],
		&cRowlb[0], &cRowub[0])

	// Set objective direction: minimize
	C.Cbc_setObjSense(model, 1.0)

	// Set integer variables
	for i := 0; i < colCount; i++ {
		if isInteger[i] {
			C.Cbc_setInteger(model, C.int(i))
		}
	}

	// Set log level (0 = silent)
	C.Cbc_setLogLevel(model, 0)

	// Solve
	C.Cbc_solve(model)

	status := 0
	if C.Cbc_isProvenOptimal(model) == 0 {
		status = 1
	}
	objVal := float64(C.Cbc_getObjValue(model))
	elapsed := time.Since(startTime).Milliseconds()

	// Extract solution
	colSol := C.Cbc_getColSolution(model)
	solVals := make([]float64, colCount)
	cArr := (*[1 << 30]C.double)(unsafe.Pointer(colSol))[:colCount:colCount]
	for i := 0; i < colCount; i++ {
		solVals[i] = float64(cArr[i])
	}

	solution := make(map[string]map[string]string)
	for _, i := range providers {
		solution[i] = make(map[string]string)
		for _, j := range days {
			js := dateStr(j)
			for _, k := range ors {
				if k == TaskBackup1 || k == TaskBackup2 {
					continue
				}
				xi := xIdx[key3(i, js, k)]
				xVal := solVals[xi]
				aVal := float64(input.Assigned[key3(i, js, k)])
				if math.Round(xVal+aVal) == 1 {
					solution[i][js] = k
				}
			}
		}
	}

	// Compute pain metrics
	providerPain := make(map[string]map[string]float64)
	for _, i := range providers {
		orDays := 0.0
		for _, j := range days {
			js := dateStr(j)
			v := float64(input.Avail[key2(i, js)])
			for _, k := range ors {
				v += float64(input.Assigned[key3(i, js, k)])
			}
			orDays += minFloat(v, 1)
		}
		if orDays > 0 {
			totalPain := input.Specialty1Cost[i]
			totalRoomPain := 0.0
			for _, j := range days {
				js := dateStr(j)
				for _, k := range ors {
					xi := xIdx[key3(i, js, k)]
					totalRoomPain += input.Cost[k] * (solVals[xi] + float64(input.Assigned[key3(i, js, k)]))
				}
			}
			totalPain += totalRoomPain
			providerPain[i] = map[string]float64{
				"Total Cost":            totalPain,
				"Total SiteA Room Cost": totalRoomPain,
				"SiteA Room days":       orDays,
				"Avg. Cost":             totalPain / orDays,
				"Avg. Room Cost":        totalRoomPain / orDays,
			}
		}
	}

	return &SolverResult{
		Status:       status,
		ObjectiveVal: objVal,
		WallTimeMs:   elapsed,
		Solution:     solution,
		ProviderPain: providerPain,
	}
}

func getOrsIndex(task string, ors []string) int {
	for i, o := range ors {
		if o == task {
			return i
		}
	}
	return -1
}
