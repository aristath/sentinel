package universe

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/aristath/arduino-trader/internal/clients/tradernet"
	"github.com/rs/zerolog"
)

// IdentifierType represents the type of security identifier
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> IdentifierType
type IdentifierType int

const (
	// IdentifierTypeISIN represents an ISIN identifier
	IdentifierTypeISIN IdentifierType = iota
	// IdentifierTypeTradernet represents a Tradernet symbol (e.g., AAPL.US)
	IdentifierTypeTradernet
	// IdentifierTypeYahoo represents a Yahoo Finance symbol
	IdentifierTypeYahoo
)

// String returns the string representation of IdentifierType
func (i IdentifierType) String() string {
	switch i {
	case IdentifierTypeISIN:
		return "ISIN"
	case IdentifierTypeTradernet:
		return "Tradernet"
	case IdentifierTypeYahoo:
		return "Yahoo"
	default:
		return "Unknown"
	}
}

// SymbolInfo contains resolved symbol information
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> SymbolInfo
type SymbolInfo struct {
	TradernetSymbol *string // Tradernet symbol (e.g., AAPL.US)
	ISIN            *string // ISIN (e.g., US0378331005)
	YahooSymbol     string  // Best identifier for Yahoo (ISIN if available, else converted)
}

// HasISIN checks if ISIN is available
func (s *SymbolInfo) HasISIN() bool {
	return s.ISIN != nil && *s.ISIN != ""
}

// Tradernet suffix pattern: ends with .XX or .XXX
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> TRADERNET_SUFFIX_PATTERN
var tradernetSuffixPattern = regexp.MustCompile(`\.[A-Z]{2,3}$`)

// IsISIN checks if identifier is an ISIN
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> is_isin()
// Note: Uses the same logic as isISIN() in handlers.go, but exported for use outside the package
func IsISIN(identifier string) bool {
	// Use the existing isISIN function from handlers.go (package-level function)
	return isISIN(identifier)
}

// IsTradernetFormat checks if identifier is in Tradernet format (has .XX or .XXX suffix)
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> is_tradernet_format()
func IsTradernetFormat(identifier string) bool {
	if identifier == "" {
		return false
	}
	return tradernetSuffixPattern.MatchString(strings.ToUpper(identifier))
}

// DetectIdentifierType detects the type of identifier
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> detect_identifier_type()
func DetectIdentifierType(identifier string) IdentifierType {
	if IsISIN(identifier) {
		return IdentifierTypeISIN
	}
	if IsTradernetFormat(identifier) {
		return IdentifierTypeTradernet
	}
	return IdentifierTypeYahoo
}

// TradernetToYahoo converts Tradernet symbol to Yahoo format
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> tradernet_to_yahoo()
//
// This is the fallback when ISIN is not available.
// For .US securities, strips the suffix.
// For .GR securities, converts to .AT (Athens).
// Other suffixes pass through unchanged.
func TradernetToYahoo(tradernetSymbol string) string {
	symbol := strings.ToUpper(tradernetSymbol)

	// US securities: strip .US suffix
	if strings.HasSuffix(symbol, ".US") {
		return symbol[:len(symbol)-3]
	}

	// Greek securities: .GR -> .AT (Athens Exchange)
	if strings.HasSuffix(symbol, ".GR") {
		return symbol[:len(symbol)-3] + ".AT"
	}

	// Everything else passes through unchanged
	return symbol
}

// SymbolResolver service for resolving security identifiers to usable formats
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> SymbolResolver
type SymbolResolver struct {
	tradernetClient *tradernet.Client
	securityRepo    *SecurityRepository
	log             zerolog.Logger
}

// NewSymbolResolver creates a new symbol resolver
func NewSymbolResolver(
	tradernetClient *tradernet.Client,
	securityRepo *SecurityRepository,
	log zerolog.Logger,
) *SymbolResolver {
	return &SymbolResolver{
		tradernetClient: tradernetClient,
		securityRepo:    securityRepo,
		log:             log.With().Str("component", "symbol_resolver").Logger(),
	}
}

// DetectType detects the type of identifier
func (r *SymbolResolver) DetectType(identifier string) IdentifierType {
	return DetectIdentifierType(identifier)
}

// Resolve resolves any identifier to SymbolInfo
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> resolve()
//
// For Tradernet symbols:
// 1. Check if ISIN is cached in database
// 2. If not, fetch from Tradernet API
// 3. Return SymbolInfo with ISIN as yahoo_symbol (best for Yahoo lookups)
//
// For ISIN:
// 1. Return directly with ISIN as yahoo_symbol
//
// For Yahoo format:
// 1. Return as-is (no Tradernet symbol or ISIN known)
func (r *SymbolResolver) Resolve(identifier string) (*SymbolInfo, error) {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))
	idType := r.DetectType(identifier)

	r.log.Debug().
		Str("identifier", identifier).
		Str("type", idType.String()).
		Msg("Resolving identifier")

	switch idType {
	case IdentifierTypeISIN:
		// ISIN provided directly - use as yahoo_symbol
		return &SymbolInfo{
			TradernetSymbol: nil,
			ISIN:            &identifier,
			YahooSymbol:     identifier,
		}, nil

	case IdentifierTypeTradernet:
		// Try to get ISIN for Tradernet symbol
		isin, err := r.getISINForTradernet(identifier)
		if err != nil {
			r.log.Warn().Err(err).Str("symbol", identifier).Msg("Failed to get ISIN for Tradernet symbol")
			// Fall back to simple conversion
			yahoo := TradernetToYahoo(identifier)
			return &SymbolInfo{
				TradernetSymbol: &identifier,
				ISIN:            nil,
				YahooSymbol:     yahoo,
			}, nil
		}

		if isin != nil && *isin != "" {
			return &SymbolInfo{
				TradernetSymbol: &identifier,
				ISIN:            isin,
				YahooSymbol:     *isin, // Use ISIN for Yahoo
			}, nil
		}

		// Fall back to simple conversion
		yahoo := TradernetToYahoo(identifier)
		return &SymbolInfo{
			TradernetSymbol: &identifier,
			ISIN:            nil,
			YahooSymbol:     yahoo,
		}, nil

	case IdentifierTypeYahoo:
		// Yahoo format - return as-is
		return &SymbolInfo{
			TradernetSymbol: nil,
			ISIN:            nil,
			YahooSymbol:     identifier,
		}, nil

	default:
		return nil, fmt.Errorf("unknown identifier type: %v", idType)
	}
}

// getISINForTradernet gets ISIN for a Tradernet symbol
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> _get_isin_for_tradernet()
//
// 1. Check database cache first
// 2. If not cached, fetch from Tradernet API
func (r *SymbolResolver) getISINForTradernet(tradernetSymbol string) (*string, error) {
	// Check database cache first
	if r.securityRepo != nil {
		security, err := r.securityRepo.GetBySymbol(tradernetSymbol)
		if err != nil {
			r.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Error checking database cache")
		} else if security != nil && security.ISIN != "" {
			r.log.Debug().
				Str("symbol", tradernetSymbol).
				Str("isin", security.ISIN).
				Msg("Found cached ISIN in database")
			return &security.ISIN, nil
		}
	}

	// Fetch from Tradernet API
	return r.fetchISINFromTradernet(tradernetSymbol)
}

// fetchISINFromTradernet fetches ISIN from Tradernet's FindSymbol API
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> _fetch_isin_from_tradernet()
//
// Uses the Tradernet microservice FindSymbol endpoint which returns security info including ISIN.
func (r *SymbolResolver) fetchISINFromTradernet(tradernetSymbol string) (*string, error) {
	if r.tradernetClient == nil {
		r.log.Warn().Msg("Tradernet client not available, cannot fetch ISIN")
		return nil, nil
	}

	if !r.tradernetClient.IsConnected() {
		r.log.Warn().Msg("Tradernet client not connected, cannot fetch ISIN")
		return nil, nil
	}

	r.log.Debug().Str("symbol", tradernetSymbol).Msg("Fetching ISIN from Tradernet API")

	// Call Tradernet FindSymbol
	securities, err := r.tradernetClient.FindSymbol(tradernetSymbol, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to find symbol in Tradernet: %w", err)
	}

	if len(securities) == 0 {
		r.log.Warn().Str("symbol", tradernetSymbol).Msg("No securities found in Tradernet")
		return nil, nil
	}

	// Use first result (typically the primary exchange listing)
	security := securities[0]

	// Extract ISIN
	if security.ISIN == nil || *security.ISIN == "" {
		r.log.Debug().Str("symbol", tradernetSymbol).Msg("No ISIN in security info")
		return nil, nil
	}

	isinStr := *security.ISIN

	// Validate ISIN
	if !IsISIN(isinStr) {
		r.log.Warn().
			Str("symbol", tradernetSymbol).
			Str("isin", isinStr).
			Msg("Invalid ISIN format in security info")
		return nil, nil
	}

	r.log.Info().
		Str("symbol", tradernetSymbol).
		Str("isin", isinStr).
		Msg("Fetched ISIN from Tradernet")
	return &isinStr, nil
}

// ResolveAndCache resolves a Tradernet symbol and caches the ISIN if found
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> resolve_and_cache()
func (r *SymbolResolver) ResolveAndCache(tradernetSymbol string) (*SymbolInfo, error) {
	info, err := r.Resolve(tradernetSymbol)
	if err != nil {
		return nil, err
	}

	// Cache the ISIN if we have a repo and found an ISIN
	if r.securityRepo != nil && info.ISIN != nil && *info.ISIN != "" {
		security, err := r.securityRepo.GetBySymbol(tradernetSymbol)
		if err != nil {
			r.log.Warn().Err(err).Str("symbol", tradernetSymbol).Msg("Error checking for existing security")
		} else if security != nil && security.ISIN == "" {
			// Update with ISIN
			err = r.securityRepo.Update(tradernetSymbol, map[string]interface{}{
				"isin": *info.ISIN,
			})
			if err != nil {
				r.log.Warn().Err(err).
					Str("symbol", tradernetSymbol).
					Str("isin", *info.ISIN).
					Msg("Failed to cache ISIN")
			} else {
				r.log.Info().
					Str("symbol", tradernetSymbol).
					Str("isin", *info.ISIN).
					Msg("Cached ISIN in database")
			}
		}
	}

	return info, nil
}

// ResolveToISIN resolves any identifier (symbol or ISIN) to canonical ISIN
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> resolve_to_isin()
//
// This is a simplified method for when you just need the ISIN
// and don't need full SymbolInfo.
func (r *SymbolResolver) ResolveToISIN(identifier string) (*string, error) {
	identifier = strings.TrimSpace(strings.ToUpper(identifier))

	// If already an ISIN, return it directly
	if IsISIN(identifier) {
		return &identifier, nil
	}

	// Try to resolve via full resolution
	info, err := r.Resolve(identifier)
	if err != nil {
		return nil, err
	}

	return info.ISIN, nil
}

// GetSymbolForDisplay gets display symbol (Tradernet format) for an ISIN
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> get_symbol_for_display()
//
// Looks up the database to find the Tradernet symbol associated
// with the given ISIN. Falls back to the input if not found.
func (r *SymbolResolver) GetSymbolForDisplay(isinOrSymbol string) string {
	if r.securityRepo == nil {
		return isinOrSymbol
	}

	identifier := strings.TrimSpace(strings.ToUpper(isinOrSymbol))

	if IsISIN(identifier) {
		// Look up by ISIN to get symbol
		security, err := r.securityRepo.GetByISIN(identifier)
		if err != nil {
			r.log.Warn().Err(err).Str("isin", identifier).Msg("Error looking up security by ISIN")
			return identifier
		}
		if security != nil {
			return security.Symbol
		}
		return identifier
	}

	// Already a symbol, return as-is
	return identifier
}

// GetISINForSymbol gets ISIN for a given symbol from database
// Faithful translation from Python: app/modules/universe/domain/symbol_resolver.py -> get_isin_for_symbol()
func (r *SymbolResolver) GetISINForSymbol(symbol string) (*string, error) {
	if r.securityRepo == nil {
		return nil, nil
	}

	security, err := r.securityRepo.GetBySymbol(strings.ToUpper(symbol))
	if err != nil {
		return nil, fmt.Errorf("failed to get security by symbol: %w", err)
	}

	if security != nil && security.ISIN != "" {
		return &security.ISIN, nil
	}

	return nil, nil
}
