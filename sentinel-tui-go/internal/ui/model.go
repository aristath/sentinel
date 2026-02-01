package ui

import (
	"sort"
	"time"

	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"

	"sentinel-tui-go/internal/api"
)

type Model struct {
	client *api.Client
	apiURL string

	// Data
	connected       bool
	tradingMode     string
	portfolio       *api.Portfolio
	pnlHistory      *api.PnLHistory
	recommendations []api.Recommendation
	securities      []api.Security

	// UI state
	width     int
	height    int
	maxWidth  int
	maxHeight int
	ready     bool

	// Auto-scroll
	scrolling    bool
	scrollAccum  float64
	contentLines int // line count of one content block
	contentDirty bool

	// Components
	viewport viewport.Model
}

// Messages

type healthMsg struct {
	health api.Health
	err    error
}

type portfolioMsg struct {
	portfolio api.Portfolio
	err       error
}

type pnlMsg struct {
	history api.PnLHistory
	err     error
}

type recsMsg struct {
	recs []api.Recommendation
	err  error
}

type securitiesMsg struct {
	securities []api.Security
	err        error
}

// Scroll: 30fps tick with fractional accumulator for smooth pacing.
const scrollLinesPerSec = 5.0
const scrollInterval = 33 * time.Millisecond

type tickMsg time.Time

const refreshInterval = 10 * time.Second

type refreshMsg struct{}

func NewModel(client *api.Client, apiURL string, maxWidth, maxHeight int) Model {
	return Model{
		client:    client,
		apiURL:    apiURL,
		maxWidth:  maxWidth,
		maxHeight: maxHeight,
	}
}

func (m Model) Init() tea.Cmd {
	cmds := fetchAll(m.client)
	cmds = append(cmds, scheduleRefresh())
	return tea.Batch(cmds...)
}

// Commands

func fetchAll(c *api.Client) []tea.Cmd {
	return []tea.Cmd{
		fetchHealth(c),
		fetchPortfolio(c),
		fetchPnL(c),
		fetchRecs(c),
		fetchSecurities(c),
	}
}

func fetchHealth(c *api.Client) tea.Cmd {
	return func() tea.Msg {
		h, err := c.Health()
		return healthMsg{h, err}
	}
}

func fetchPortfolio(c *api.Client) tea.Cmd {
	return func() tea.Msg {
		p, err := c.Portfolio()
		return portfolioMsg{p, err}
	}
}

func fetchPnL(c *api.Client) tea.Cmd {
	return func() tea.Msg {
		h, err := c.PnLHistory("1M")
		return pnlMsg{h, err}
	}
}

func fetchRecs(c *api.Client) tea.Cmd {
	return func() tea.Msg {
		r, err := c.Recommendations()
		return recsMsg{r, err}
	}
}

func fetchSecurities(c *api.Client) tea.Cmd {
	return func() tea.Msg {
		s, err := c.Unified()
		if err == nil {
			sort.Slice(s, func(i, j int) bool {
				return s[i].ValueEUR > s[j].ValueEUR
			})
		}
		return securitiesMsg{s, err}
	}
}

func tickCmd() tea.Cmd {
	return tea.Tick(scrollInterval, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func scheduleRefresh() tea.Cmd {
	return tea.Tick(refreshInterval, func(t time.Time) tea.Msg {
		return refreshMsg{}
	})
}
