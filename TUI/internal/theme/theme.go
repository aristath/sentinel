package theme

import (
	"fmt"
	"image/color"
	"math"
	"strings"

	catppuccin "github.com/catppuccin/go"

	"charm.land/lipgloss/v2"
)

var mocha = catppuccin.Mocha

// Theme holds the semantic color palette for the entire TUI.
type Theme struct {
	Muted   color.Color
	Text    color.Color
	Subtext color.Color
	Primary color.Color
	Accent  color.Color
	Success color.Color
	Warning color.Color
	Error   color.Color
	Info    color.Color
}

// Default theme: Catppuccin Mocha.
var Default = Theme{
	Muted:   mocha.Overlay0(),
	Text:    mocha.Text(),
	Subtext: mocha.Subtext0(),
	Primary: mocha.Blue(),
	Accent:  mocha.Mauve(),
	Success: mocha.Green(),
	Warning: mocha.Peach(),
	Error:   mocha.Red(),
	Info:    mocha.Sky(),
}

// GradientText applies a horizontal color gradient across each line of text.
func GradientText(text string, from, to color.Color) string {
	fr, fg, fb := colorToRGB(from)
	tr, tg, tb := colorToRGB(to)

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

			c := lipgloss.Color(fmt.Sprintf("#%02x%02x%02x", cr, cg, cb))
			sb.WriteString(lipgloss.NewStyle().Foreground(c).Render(string(r)))
		}
		result = append(result, sb.String())
	}
	return strings.Join(result, "\n")
}

func colorToRGB(c color.Color) (uint8, uint8, uint8) {
	r, g, b, _ := c.RGBA()
	return uint8(r >> 8), uint8(g >> 8), uint8(b >> 8)
}
