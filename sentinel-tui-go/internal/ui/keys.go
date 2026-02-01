package ui

import "github.com/charmbracelet/bubbles/key"

type keyMap struct {
	Quit key.Binding
	Back key.Binding
}

var keys = keyMap{
	Quit: key.NewBinding(key.WithKeys("q", "ctrl+c"), key.WithHelp("q", "quit")),
	Back: key.NewBinding(key.WithKeys("esc"), key.WithHelp("esc", "back")),
}
