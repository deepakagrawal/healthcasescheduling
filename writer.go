package main

import (
	"archive/zip"
	"encoding/xml"
	"fmt"
	"os"
	"strings"
)

func WriteXLSX(path string, result *SolverResult, days []string) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	w := zip.NewWriter(f)
	defer w.Close()

	// [Content_Types].xml
	writeZipFile(w, "[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`)

	// _rels/.rels
	writeZipFile(w, "_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`)

	// xl/_rels/workbook.xml.rels
	writeZipFile(w, "xl/_rels/workbook.xml.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`)

	// xl/workbook.xml
	writeZipFile(w, "xl/workbook.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="assignment" sheetId="1" r:id="rId1"/></sheets>
</workbook>`)

	// xl/worksheets/sheet1.xml - assignment data
	var sb strings.Builder
	sb.WriteString(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`)
	sb.WriteString(`<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">`)
	sb.WriteString(`<sheetData>`)

	// Header row
	sb.WriteString(`<row r="1">`)
	sb.WriteString(`<c r="A1" t="inlineStr"><is><t>Provider</t></is></c>`)
	for ci, d := range days {
		col := colName(ci + 1)
		sb.WriteString(fmt.Sprintf(`<c r="%s1" t="inlineStr"><is><t>%s</t></is></c>`, col, xmlEscape(d)))
	}
	sb.WriteString(`</row>`)

	// Data rows
	rowNum := 2
	for provider, assignments := range result.Solution {
		hasData := false
		for _, d := range days {
			if assignments[d] != "" {
				hasData = true
				break
			}
		}
		if !hasData {
			continue
		}
		sb.WriteString(fmt.Sprintf(`<row r="%d">`, rowNum))
		sb.WriteString(fmt.Sprintf(`<c r="A%d" t="inlineStr"><is><t>%s</t></is></c>`, rowNum, xmlEscape(provider)))
		for ci, d := range days {
			col := colName(ci + 1)
			if v := assignments[d]; v != "" {
				sb.WriteString(fmt.Sprintf(`<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>`, col, rowNum, xmlEscape(v)))
			}
		}
		sb.WriteString(`</row>`)
		rowNum++
	}

	sb.WriteString(`</sheetData></worksheet>`)
	writeZipFile(w, "xl/worksheets/sheet1.xml", sb.String())

	return nil
}

func writeZipFile(w *zip.Writer, name, content string) {
	fw, _ := w.Create(name)
	fw.Write([]byte(content))
}

func colName(n int) string {
	if n <= 26 {
		return string(rune('A' + n - 1))
	}
	return string(rune('A'+n/26-1)) + string(rune('A'+n%26-1))
}

func xmlEscape(s string) string {
	var b strings.Builder
	xml.EscapeText(&b, []byte(s))
	return b.String()
}
