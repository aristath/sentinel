package ui

import (
	"fmt"
	"math"
	"strings"

	"github.com/charmbracelet/lipgloss"
	figure "github.com/common-nighthawk/go-figure"

	"sentinel-tui-go/internal/api"
	"sentinel-tui-go/internal/bigtext"
	"sentinel-tui-go/internal/fonts"
	"sentinel-tui-go/internal/theme"
)

func (m Model) View() string {
	if !m.ready {
		return "\n  Loading..."
	}
	return m.viewMain()
}

func (m Model) viewMain() string {
	t := theme.Default

	page := lipgloss.NewStyle().
		Width(m.width).
		Height(m.height).
		Background(t.Base)

	return page.Render(m.viewport.View())
}

func (m *Model) rebuildContent() {
	pad := lipgloss.NewStyle().Padding(0, 2)

	hero := pad.Render(m.viewHero())
	actions := pad.Render(m.viewActions())
	cards := pad.Render(m.viewCards())

	oneBlock := strings.Join([]string{
		strings.Repeat("\n", 50),
		hero,
		"",
		actions,
		"",
		cards,
	}, "\n")

	oneBlock = strings.TrimRight(oneBlock, "\n")
	m.contentLines = strings.Count(oneBlock, "\n") + 1

	// Duplicate the block so the scroll wraps seamlessly.
	m.viewport.SetContent(oneBlock + "\n" + oneBlock)
}

// renderFiglet renders text using the double_blocky font.
func renderFiglet(text string) string {
	fr := fonts.LoadFont("double_blocky")
	if fr == nil {
		return text
	}
	fig := figure.NewFigureWithFont(text, fr, false)
	return strings.Join(fig.Slicify(), "\n")
}

func (m Model) viewHero() string {
	t := theme.Default

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
	if pnlPct < 0 {
		pnlSign = ""
	}

	valFig := bigtext.RenderExtraBold(formatEUR(value))
	pnlFig := renderFiglet(fmt.Sprintf("%s%.1f%%", pnlSign, pnlPct))
	cashFig := renderFiglet(formatWithSeparators(cash))

	valBlock := theme.GradientText(valFig, t.Primary, t.Accent)
	valSep := theme.GradientText(strings.Repeat("█", m.width-6), t.Primary, t.Accent)
	pnlBlock := lipgloss.NewStyle().Foreground(t.Info).Render(pnlFig)
	cashBlock := lipgloss.NewStyle().Foreground(t.Info).Render(cashFig)

	// PnL left, cash right-aligned on the same row
	rowWidth := m.width - 6
	infoRow := lipgloss.JoinHorizontal(lipgloss.Top,
		pnlBlock,
		lipgloss.NewStyle().Width(rowWidth-lipgloss.Width(pnlBlock)-lipgloss.Width(cashBlock)).Render(""),
		cashBlock,
	)

	infoSep := theme.GradientText(strings.Repeat("/", m.width-6), t.Primary, t.Accent)

	return lipgloss.JoinVertical(lipgloss.Left, valBlock, "", valSep, "", infoRow, "", infoSep)
}

func (m Model) viewActions() string {
	t := theme.Default

	if len(m.recommendations) == 0 {
		return lipgloss.NewStyle().
			Foreground(t.Muted).
			Render(renderFiglet("No recommendations"))
	}

	// Pre-render symbols to find max width for alignment.
	type recRow struct {
		symBlock   string
		amtBlock   string
		color      lipgloss.Color
	}
	var rows []recRow
	maxSymWidth := 0

	for _, rec := range m.recommendations {
		action := strings.ToUpper(rec.Action)
		cost := rec.Price * float64(rec.Quantity)

		sign := "+"
		color := t.Success
		if action == "SELL" {
			sign = "-"
			color = t.Warning
		}

		symFig := renderFiglet(rec.Symbol)
		amtFig := renderFiglet(fmt.Sprintf("%s%s", sign, formatWithSeparators(cost)))

		w := lipgloss.Width(symFig)
		if w > maxSymWidth {
			maxSymWidth = w
		}
		rows = append(rows, recRow{symFig, amtFig, color})
	}

	title := lipgloss.NewStyle().Foreground(t.Info).Render(renderFiglet("Recommendations"))
	lines := []string{title, ""}
	for _, row := range rows {
		sym := lipgloss.NewStyle().Width(maxSymWidth).Foreground(row.color).Render(row.symBlock)
		amt := lipgloss.NewStyle().Foreground(row.color).Render(row.amtBlock)

		line := lipgloss.JoinHorizontal(lipgloss.Top, sym, "  ", amt)
		lines = append(lines, line)
		lines = append(lines, "")
	}

	return strings.Join(lines, "\n")
}

func (m Model) viewCards() string {
	t := theme.Default

	var positions []api.Security
	for _, sec := range m.securities {
		if sec.HasPosition {
			positions = append(positions, sec)
		}
	}
	if len(positions) == 0 {
		return ""
	}

	title := lipgloss.NewStyle().Foreground(t.Info).Render(renderFiglet("Holdings"))
	sep := theme.GradientText(strings.Repeat("/", m.width-6), t.Primary, t.Accent)
	lines := []string{strings.Repeat("\n", 50), sep, "", title, ""}

	for _, sec := range positions {
		// Symbol colored by profit
		symColor := t.Success
		if sec.ProfitPct < 0 {
			symColor = t.Error
		}
		symBlock := lipgloss.NewStyle().Foreground(symColor).Render(bigtext.RenderBoldLarge(sec.Symbol))

		// Value + Profit row (figlet)
		valBlock := lipgloss.NewStyle().Foreground(t.Text).Render(renderFiglet(formatWithSeparators(sec.ValueEUR)))

		profitSign := "+"
		profitColor := t.Success
		if sec.ProfitPct < 0 {
			profitSign = ""
			profitColor = t.Error
		}
		profitBlock := lipgloss.NewStyle().Foreground(profitColor).Render(renderFiglet(fmt.Sprintf("%s%.1f%%", profitSign, sec.ProfitPct)))

		statsRow := lipgloss.JoinHorizontal(lipgloss.Top, valBlock, "  ", profitBlock)

		// Area chart from historical prices
		var chartBlock string
		if len(sec.Prices) > 0 {
			prices := make([]float64, len(sec.Prices))
			for i, p := range sec.Prices {
				prices[i] = p.Close
			}
			chartBlock = RenderAreaChart(prices, sec.AvgCost, m.width-6, 10, t.Success, t.Error)
		}

		// Score bars: full-width, no labels, below chart
		barWidth := m.width - 6
		classicBar := renderScoreBar(sec.WaveletScore, barWidth, t.Info, t.Border)
		mlBar := renderScoreBar(sec.MlScore, barWidth, t.Warning, t.Border)
		weightedBar := renderScoreBar(sec.ExpectedReturn, barWidth, t.Accent, t.Border)
		predsRow := strings.Join([]string{classicBar, mlBar, weightedBar}, "\n")

		cardSep := theme.GradientText(strings.Repeat("/", m.width-6), t.Primary, t.Accent)

		lines = append(lines, "", "", "", "", "", symBlock, "", statsRow, "")
		if chartBlock != "" {
			lines = append(lines, chartBlock, "")
		}
		lines = append(lines, predsRow, "", "", "", "", "", cardSep, "")
	}

	return strings.Join(lines, "\n")
}



// renderScoreBar renders a center-anchored horizontal bar for a score in [-1, 1].
// Positive scores fill rightward from center, negative fill leftward.
func renderScoreBar(score float64, width int, color, emptyColor lipgloss.Color) string {
	// Sub-character block elements for fractional fill (1/8 to 8/8).
	fractionalBlocks := []rune{'▏', '▎', '▍', '▌', '▋', '▊', '▉', '█'}

	// Clamp score to [-1, 1].
	score = math.Max(-1, math.Min(1, score))

	if width < 2 {
		width = 2
	}
	halfWidth := width / 2

	// How many cells to fill (fractional).
	fillCells := math.Abs(score) * float64(halfWidth)
	fullCells := int(fillCells)
	fraction := fillCells - float64(fullCells)

	// Build the bar as a rune slice of '░' (empty).
	bar := make([]rune, width)
	for i := range bar {
		bar[i] = '░'
	}

	if score >= 0 {
		// Fill rightward from center.
		for i := 0; i < fullCells && halfWidth+i < width; i++ {
			bar[halfWidth+i] = '█'
		}
		if fraction > 0 && halfWidth+fullCells < width {
			idx := int(fraction*8) - 1
			if idx < 0 {
				idx = 0
			}
			bar[halfWidth+fullCells] = fractionalBlocks[idx]
		}
	} else {
		// Fill leftward from center.
		for i := 0; i < fullCells && halfWidth-1-i >= 0; i++ {
			bar[halfWidth-1-i] = '█'
		}
		if fraction > 0 && halfWidth-1-fullCells >= 0 {
			idx := int(fraction*8) - 1
			if idx < 0 {
				idx = 0
			}
			bar[halfWidth-1-fullCells] = fractionalBlocks[idx]
		}
	}

	// Render: colored fill chars, empty-colored empty chars.
	fillStyle := lipgloss.NewStyle().Foreground(color)
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

func formatEUR(v float64) string {
	return formatWithSeparators(v)
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
