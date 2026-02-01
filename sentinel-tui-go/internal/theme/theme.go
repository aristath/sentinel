package theme

import (
	"fmt"
	"math"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Theme holds the semantic color palette for the entire TUI.
type Theme struct {
	Base    lipgloss.Color
	Surface lipgloss.Color
	Overlay lipgloss.Color
	Border  lipgloss.Color
	Muted   lipgloss.Color
	Text    lipgloss.Color
	Subtext lipgloss.Color
	Primary lipgloss.Color
	Accent  lipgloss.Color
	Success lipgloss.Color
	Warning lipgloss.Color
	Error   lipgloss.Color
	Info    lipgloss.Color
}

// Default theme uses Charmbracelet's CharmTone palette from Crush.
var Default = Theme{
	Base:    lipgloss.Color("#201F26"), // Pepper
	Surface: lipgloss.Color("#2D2C35"), // BBQ
	Overlay: lipgloss.Color("#3A3943"), // Charcoal
	Border:  lipgloss.Color("#4D4C57"), // Iron
	Muted:   lipgloss.Color("#858392"), // Squid
	Text:    lipgloss.Color("#DFDBDD"), // Ash
	Subtext: lipgloss.Color("#BFBCC8"), // Smoke
	Primary: lipgloss.Color("#6B50FF"), // Charple
	Accent:  lipgloss.Color("#FF60FF"), // Dolly
	Success: lipgloss.Color("#00FFB2"), // Julep
	Warning: lipgloss.Color("#FFD300"),
	Error:   lipgloss.Color("#E94090"),
	Info:    lipgloss.Color("#00CED1"),
}

// GradientText applies a horizontal color gradient across each line of text.
func GradientText(text string, from, to lipgloss.Color) string {
	fr, fg, fb := hexToRGB(string(from))
	tr, tg, tb := hexToRGB(string(to))

	lines := strings.Split(text, "\n")
	var result []string

	for _, line := range lines {
		runes := []rune(line)
		n := len(runes)
		if n == 0 {
			result = append(result, "")
			continue
		}

		var sb strings.Builder
		for i, r := range runes {
			t := 0.0
			if n > 1 {
				t = float64(i) / float64(n-1)
			}
			cr := uint8(math.Round(float64(fr) + t*float64(int(tr)-int(fr))))
			cg := uint8(math.Round(float64(fg) + t*float64(int(tg)-int(fg))))
			cb := uint8(math.Round(float64(fb) + t*float64(int(tb)-int(fb))))

			color := lipgloss.Color(fmt.Sprintf("#%02x%02x%02x", cr, cg, cb))
			sb.WriteString(lipgloss.NewStyle().Foreground(color).Render(string(r)))
		}
		result = append(result, sb.String())
	}
	return strings.Join(result, "\n")
}

func hexToRGB(hex string) (uint8, uint8, uint8) {
	hex = strings.TrimPrefix(hex, "#")
	if len(hex) != 6 {
		return 0, 0, 0
	}
	var r, g, b uint8
	fmt.Sscanf(hex, "%02x%02x%02x", &r, &g, &b)
	return r, g, b
}
