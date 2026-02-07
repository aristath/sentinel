package ui

import (
	"fmt"
	"image/color"
	"math"
	"strings"

	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"

	"sentinel-tui-go/internal/api"
	"sentinel-tui-go/internal/bigtext"
	"sentinel-tui-go/internal/theme"
)

func (m Model) View() tea.View {
	if !m.ready {
		return tea.NewView("\n  Loading...")
	}
	content := m.viewMain()
	if m.inSettings {
		content = m.viewSettings()
	}
	v := tea.NewView(content)
	v.AltScreen = true
	return v
}

func (m Model) viewMain() string {
	page := lipgloss.NewStyle().
		Width(m.width).
		Height(m.height)
	return page.Render(m.viewport.View())
}

func (m Model) viewSettings() string {
	t := theme.Default

	title := lipgloss.NewStyle().Foreground(t.Primary).Bold(true).Render("SETTINGS")
	label := lipgloss.NewStyle().Foreground(t.Muted).Render("API URL")
	input := lipgloss.NewStyle().Foreground(t.Text).Render(m.apiURLInput)
	hints := lipgloss.NewStyle().Foreground(t.Subtext).Render("ENTER save   ESC cancel   Ctrl+U clear")

	status := ""
	if m.statusMsg != "" {
		color := t.Success
		if strings.Contains(strings.ToLower(m.statusMsg), "invalid") || strings.Contains(strings.ToLower(m.statusMsg), "cannot") {
			color = t.Error
		}
		status = lipgloss.NewStyle().Foreground(color).Render(m.statusMsg)
	}

	body := []string{
		"",
		title,
		"",
		label,
		input,
		"",
		hints,
	}
	if status != "" {
		body = append(body, "", status)
	}

	return lipgloss.NewStyle().
		Width(m.width).
		Height(m.height).
		Padding(1, 2).
		Render(strings.Join(body, "\n"))
}

// contentWidth returns the usable content width after outer padding.
func (m Model) contentWidth() int {
	return m.width - 4
}

func (m *Model) rebuildContent() {
	t := theme.Default
	pad := lipgloss.NewStyle().Padding(0, 2)
	w := m.contentWidth()

	hero := pad.Render(m.viewHero())
	actions := pad.Render(m.viewActions())
	cards := pad.Render(m.viewCards())

	sep := pad.Render(lipgloss.NewStyle().Foreground(t.Primary).Render(
		strings.Repeat("/", w)))

	oneBlock := strings.Join([]string{
		strings.Repeat("\n", m.height),
		hero,
		"", "",
		sep,
		"", "",
		actions,
		"", "",
		sep,
		"", "",
		cards,
	}, "\n")

	oneBlock = strings.TrimRight(oneBlock, "\n")
	m.contentLines = strings.Count(oneBlock, "\n") + 1
	m.viewport.SetContent(oneBlock + "\n" + oneBlock)
}

func (m Model) viewHero() string {
	t := theme.Default
	w := m.contentWidth()

	if m.portfolio == nil && !m.connected {
		return lipgloss.NewStyle().
			Foreground(t.Error).
			Render(fmt.Sprintf("Cannot reach API at %s", m.apiURL))
	}

	var value float64
	if m.portfolio != nil {
		value = m.portfolio.TotalValueEUR
	}

	var cash float64
	if m.portfolio != nil {
		cash = m.portfolio.TotalCashEUR
	}

	var pnlPct float64
	if m.pnlHistory != nil {
		pnlPct = m.pnlHistory.Summary.PnLPercent
	}

	pnlSign := "+"
	pnlColor := t.Success
	if pnlPct < 0 {
		pnlSign = ""
		pnlColor = t.Error
	}

	// Portfolio value — hero number
	valText := bigtext.RenderExtraBoldXXL(formatWithSeparators(value))
	valBlock := theme.GradientText(valText, t.Primary, t.Accent)

	// P&L and cash as compact block text
	pnlText := bigtext.Render(fmt.Sprintf("%s%.1f%%", pnlSign, pnlPct))
	pnlBlock := lipgloss.NewStyle().Foreground(pnlColor).Render(pnlText)
	pnlLabel := lipgloss.NewStyle().Foreground(t.Muted).Render("  PNL")

	cashText := bigtext.Render(formatWithSeparators(cash))
	cashBlock := lipgloss.NewStyle().Foreground(t.Subtext).Render(cashText)
	cashLabel := lipgloss.NewStyle().Foreground(t.Muted).Render("CASH  ")

	pnlCol := lipgloss.JoinVertical(lipgloss.Left, pnlBlock, pnlLabel)
	cashCol := lipgloss.JoinVertical(lipgloss.Right, cashBlock, cashLabel)

	gap := max(0, w-lipgloss.Width(pnlCol)-lipgloss.Width(cashCol))
	infoRow := lipgloss.JoinHorizontal(lipgloss.Top,
		pnlCol,
		lipgloss.NewStyle().Width(gap).Render(""),
		cashCol,
	)

	return lipgloss.JoinVertical(lipgloss.Left,
		"",
		valBlock,
		"",
		infoRow,
		"",
	)
}

func (m Model) viewActions() string {
	t := theme.Default

	if len(m.recommendations) == 0 {
		return lipgloss.NewStyle().
			Foreground(t.Muted).
			Render(bigtext.Render("NO RECOMMENDATIONS"))
	}

	title := lipgloss.NewStyle().Foreground(t.Primary).
		Render(bigtext.Render("RECOMMENDATIONS"))

	var rows []string
	for _, rec := range m.recommendations {
		action := strings.ToUpper(rec.Action)
		cost := rec.Price * float64(rec.Quantity)

		sign := "+"
		c := t.Success
		if action == "SELL" {
			sign = "-"
			c = t.Warning
		}

		symText := bigtext.Render(rec.Symbol)
		symBlock := lipgloss.NewStyle().Foreground(c).Render(symText)

		actionLabel := lipgloss.NewStyle().Foreground(c).Bold(true).
			Render(fmt.Sprintf("  %s  %s%s", action, sign, formatWithSeparators(cost)))

		row := lipgloss.JoinHorizontal(lipgloss.Top, symBlock, actionLabel)
		rows = append(rows, row)
	}

	lines := []string{title, ""}
	for i, row := range rows {
		lines = append(lines, row)
		if i < len(rows)-1 {
			lines = append(lines, "")
		}
	}
	return strings.Join(lines, "\n")
}

func (m Model) viewCards() string {
	t := theme.Default
	w := m.contentWidth()

	var positions []api.Security
	for _, sec := range m.securities {
		if sec.HasPosition {
			positions = append(positions, sec)
		}
	}
	if len(positions) == 0 {
		return ""
	}

	title := lipgloss.NewStyle().Foreground(t.Primary).
		Render(bigtext.Render("HOLDINGS"))

	lines := []string{title, ""}

	for i, sec := range positions {
		symColor := t.Success
		if sec.ProfitPct < 0 {
			symColor = t.Error
		}
		symBlock := lipgloss.NewStyle().Foreground(symColor).
			Render(bigtext.Render(sec.Symbol))

		profitSign := "+"
		profitColor := t.Success
		if sec.ProfitPct < 0 {
			profitSign = ""
			profitColor = t.Error
		}

		statsText := fmt.Sprintf("  %s EUR  %s%.1f%%",
			formatWithSeparators(sec.ValueEUR), profitSign, sec.ProfitPct)
		statsBlock := lipgloss.NewStyle().Foreground(profitColor).Bold(true).
			Render(statsText)

		nameBlock := lipgloss.NewStyle().Foreground(profitColor).
			Render(sec.Name)

		headerRow := lipgloss.JoinHorizontal(lipgloss.Top, symBlock, statsBlock)

		var chartBlock string
		if len(sec.Prices) > 0 {
			prices := make([]float64, len(sec.Prices))
			for j, p := range sec.Prices {
				prices[j] = p.Close
			}
			chartBlock = RenderAreaChart(prices, sec.AvgCost, w, 6, t.Success, t.Error)
		}

		// Score bars with labels
		barWidth := w - 4
		expLabel := lipgloss.NewStyle().Foreground(t.Accent).Render("EXP ")
		expBar := expLabel + renderScoreBar(sec.ExpectedReturn, barWidth, t.Accent, t.Muted)

		var cardLines []string
		cardLines = append(cardLines, "", headerRow, nameBlock, "")
		if chartBlock != "" {
			cardLines = append(cardLines, chartBlock, "")
		}
		cardLines = append(cardLines, expBar, "")

		lines = append(lines, strings.Join(cardLines, "\n"))
		if i < len(positions)-1 {
			cardSep := lipgloss.NewStyle().Foreground(t.Primary).Render(
				strings.Repeat("/", w))
			lines = append(lines, "", cardSep, "")
		}
	}

	return strings.Join(lines, "\n")
}

// renderScoreBar renders a center-anchored horizontal bar for a score in [-1, 1].
func renderScoreBar(score float64, width int, c, emptyColor color.Color) string {
	fractionalBlocks := []rune{'▏', '▎', '▍', '▌', '▋', '▊', '▉', '█'}

	score = math.Max(-1, math.Min(1, score))
	if width < 2 {
		width = 2
	}
	halfWidth := width / 2

	fillCells := math.Abs(score) * float64(halfWidth)
	fullCells := int(fillCells)
	fraction := fillCells - float64(fullCells)

	bar := make([]rune, width)
	for i := range bar {
		bar[i] = '░'
	}

	if score >= 0 {
		for i := 0; i < fullCells && halfWidth+i < width; i++ {
			bar[halfWidth+i] = '█'
		}
		if fraction > 0 && halfWidth+fullCells < width {
			idx := max(0, int(fraction*8)-1)
			bar[halfWidth+fullCells] = fractionalBlocks[idx]
		}
	} else {
		for i := 0; i < fullCells && halfWidth-1-i >= 0; i++ {
			bar[halfWidth-1-i] = '█'
		}
		if fraction > 0 && halfWidth-1-fullCells >= 0 {
			idx := max(0, int(fraction*8)-1)
			bar[halfWidth-1-fullCells] = fractionalBlocks[idx]
		}
	}

	fillStyle := lipgloss.NewStyle().Foreground(c)
	emptyStyle := lipgloss.NewStyle().Foreground(emptyColor)

	var sb strings.Builder
	for _, r := range bar {
		if r == '░' {
			sb.WriteString(emptyStyle.Render(string(r)))
		} else {
			sb.WriteString(fillStyle.Render(string(r)))
		}
	}
	return sb.String()
}

func formatWithSeparators(v float64) string {
	neg := v < 0
	if neg {
		v = -v
	}
	s := fmt.Sprintf("%.0f", v)

	n := len(s)
	if n <= 3 {
		if neg {
			return "-" + s
		}
		return s
	}

	var result strings.Builder
	offset := n % 3
	if offset > 0 {
		result.WriteString(s[:offset])
	}
	for i := offset; i < n; i += 3 {
		if result.Len() > 0 {
			result.WriteByte(',')
		}
		result.WriteString(s[i : i+3])
	}

	if neg {
		return "-" + result.String()
	}
	return result.String()
}
