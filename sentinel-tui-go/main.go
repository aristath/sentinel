package main

import (
	"flag"
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"sentinel-tui-go/internal/api"
	"sentinel-tui-go/internal/ui"
)

func main() {
	apiURL := flag.String("api-url", "http://localhost:8000", "Sentinel API URL")
	maxWidth := flag.Int("max-width", 0, "Max columns (0 = no limit)")
	maxHeight := flag.Int("max-height", 0, "Max rows (0 = no limit)")
	flag.Parse()

	client := api.NewClient(*apiURL)
	m := ui.NewModel(client, *apiURL, *maxWidth, *maxHeight)

	p := tea.NewProgram(m, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
