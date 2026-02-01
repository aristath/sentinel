package ui

import (
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
)

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		if m.maxWidth > 0 && m.width > m.maxWidth {
			m.width = m.maxWidth
		}
		if m.maxHeight > 0 && m.height > m.maxHeight {
			m.height = m.maxHeight
		}
		m.viewport = viewport.New(m.width, m.height)
		m.ready = true
		m.contentDirty = true


	case tea.KeyMsg:
		switch {
		case key.Matches(msg, keys.Quit):
			return m, tea.Quit
		case key.Matches(msg, keys.Back):
			// reserved
		}

	case refreshMsg:
		cmds = append(cmds, fetchAll(m.client)...)
		cmds = append(cmds, scheduleRefresh())

	case healthMsg:
		if msg.err != nil {
			m.connected = false
		} else {
			m.connected = true
			m.tradingMode = msg.health.TradingMode
		}

	case portfolioMsg:
		if msg.err == nil {
			m.portfolio = &msg.portfolio
			m.contentDirty = true
			if !m.scrolling {
				m.scrolling = true
				cmds = append(cmds, tickCmd())
			}
		}

	case pnlMsg:
		if msg.err == nil {
			m.pnlHistory = &msg.history
			m.contentDirty = true
		}

	case recsMsg:
		if msg.err == nil {
			m.recommendations = msg.recs
			m.contentDirty = true
		}

	case securitiesMsg:
		if msg.err == nil {
			m.securities = msg.securities
			m.contentDirty = true
		}

	case tickMsg:
		if m.scrolling {
			m.scrollAccum += scrollLinesPerSec * scrollInterval.Seconds()
			lines := int(m.scrollAccum)
			if lines > 0 {
				m.scrollAccum -= float64(lines)
				m.viewport.YOffset += lines
				if m.contentLines > 0 && m.viewport.YOffset >= m.contentLines {
					m.viewport.YOffset -= m.contentLines
				}
			}
			cmds = append(cmds, tickCmd())
		}
	}

	if m.ready {
		if m.contentDirty {
			m.rebuildContent()
			m.contentDirty = false
		}
		// Only forward non-tick messages to viewport (resize, scroll keys, etc.)
		if _, isTick := msg.(tickMsg); !isTick {
			var cmd tea.Cmd
			m.viewport, cmd = m.viewport.Update(msg)
			cmds = append(cmds, cmd)
		}
	}

	return m, tea.Batch(cmds...)
}
