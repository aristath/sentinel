// Package events provides event management functionality.
package events

import (
	"encoding/json"
	"time"
)

// EventType represents different event types
type EventType string

const (
	// Existing event types
	CashFlowSyncStart    EventType = "CASH_FLOW_SYNC_START"
	CashFlowSyncComplete EventType = "CASH_FLOW_SYNC_COMPLETE"
	ErrorOccurred        EventType = "ERROR_OCCURRED"
	DepositProcessed     EventType = "DEPOSIT_PROCESSED"
	DividendCreated      EventType = "DIVIDEND_CREATED"
	SecurityAdded        EventType = "SECURITY_ADDED"

	// New event types for queue system
	PortfolioChanged     EventType = "PORTFOLIO_CHANGED"
	PriceUpdated         EventType = "PRICE_UPDATED"
	RecommendationsReady EventType = "RECOMMENDATIONS_READY"
	DividendDetected     EventType = "DIVIDEND_DETECTED"
	PlanGenerated        EventType = "PLAN_GENERATED"
	SecuritySynced       EventType = "SECURITY_SYNCED"
	ScoreUpdated         EventType = "SCORE_UPDATED"

	// Additional event types for reactive UI
	TradeExecuted            EventType = "TRADE_EXECUTED"
	CashUpdated              EventType = "CASH_UPDATED"
	AllocationTargetsChanged EventType = "ALLOCATION_TARGETS_CHANGED"
	SettingsChanged          EventType = "SETTINGS_CHANGED"
	PlannerConfigChanged     EventType = "PLANNER_CONFIG_CHANGED"
	LogFileChanged           EventType = "LOG_FILE_CHANGED"
	SystemStatusChanged      EventType = "SYSTEM_STATUS_CHANGED"
	TradernetStatusChanged   EventType = "TRADERNET_STATUS_CHANGED"
	MarketsStatusChanged     EventType = "MARKETS_STATUS_CHANGED"
	PlanningStatusUpdated    EventType = "PLANNING_STATUS_UPDATED"
)
