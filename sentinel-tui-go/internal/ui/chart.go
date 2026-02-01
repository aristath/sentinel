package ui

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Block elements for sub-character vertical resolution (1/8 to 8/8).
var blockChars = [9]rune{' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'}

// RenderAreaChart renders a filled area chart using Unicode block elements.
// data contains the values to plot, baseline determines the color threshold
// (green above, red below). width and height control the chart dimensions
// in characters. Returns a multi-line string.
func RenderAreaChart(data []float64, baseline float64, width, height int, aboveColor, belowColor lipgloss.Color) string {
	if len(data) == 0 || width <= 0 || height <= 0 {
		return ""
	}

	// Downsample data to width columns via averaging.
	cols := downsample(data, width)

	// Find min/max for normalization.
	minVal, maxVal := cols[0], cols[0]
	for _, v := range cols {
		if v < minVal {
			minVal = v
		}
		if v > maxVal {
			maxVal = v
		}
	}

	// Total sub-cell levels across all rows.
	totalLevels := height * 8
	valRange := maxVal - minVal
	if valRange == 0 {
		valRange = 1
	}

	// Scale each column to 1..totalLevels (at least 1 so every column is visible).
	scaled := make([]int, len(cols))
	for i, v := range cols {
		norm := (v - minVal) / valRange
		s := int(norm*float64(totalLevels-1)) + 1
		if s > totalLevels {
			s = totalLevels
		}
		scaled[i] = s
	}

	// Build the chart row by row, top to bottom.
	rows := make([]string, height)
	for row := 0; row < height; row++ {
		// This row represents levels from rowBottom to rowTop.
		rowBottom := (height - 1 - row) * 8

		var sb strings.Builder
		for col := 0; col < len(scaled); col++ {
			fill := scaled[col] - rowBottom
			if fill <= 0 {
				sb.WriteRune(' ')
				continue
			}
			if fill > 8 {
				fill = 8
			}

			ch := blockChars[fill]
			color := aboveColor
			if cols[col] < baseline {
				color = belowColor
			}
			sb.WriteString(lipgloss.NewStyle().Foreground(color).Render(string(ch)))
		}
		rows[row] = sb.String()
	}

	// Trim fully empty top rows.
	start := 0
	for start < len(rows) {
		if strings.TrimSpace(rows[start]) != "" {
			break
		}
		start++
	}

	return strings.Join(rows[start:], "\n")
}

// downsample reduces data to n points by averaging buckets.
func downsample(data []float64, n int) []float64 {
	if len(data) <= n {
		out := make([]float64, len(data))
		copy(out, data)
		return out
	}

	out := make([]float64, n)
	bucketSize := float64(len(data)) / float64(n)
	for i := 0; i < n; i++ {
		start := int(float64(i) * bucketSize)
		end := int(float64(i+1) * bucketSize)
		if end > len(data) {
			end = len(data)
		}
		sum := 0.0
		for j := start; j < end; j++ {
			sum += data[j]
		}
		out[i] = sum / float64(end-start)
	}
	return out
}
