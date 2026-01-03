package scheduler

import (
	"time"

	"github.com/rs/zerolog"
)

// TradingWindow represents a single trading period within a day
type TradingWindow struct {
	OpenHour    int
	OpenMinute  int
	CloseHour   int
	CloseMinute int
}

// ExchangeCalendar defines trading hours and holidays for an exchange
type ExchangeCalendar struct {
	Code           string
	Name           string
	TimezoneStr    string
	Timezone       *time.Location
	TradingWindows []TradingWindow
	Holidays2026   []time.Time // Year-specific holidays
	StrictHours    bool        // Asian markets - trades only when open
}

// MarketHoursService provides market status information
type MarketHoursService struct {
	calendars map[string]*ExchangeCalendar
	log       zerolog.Logger
}

// NewMarketHoursService creates a new market hours service
func NewMarketHoursService(log zerolog.Logger) *MarketHoursService {
	service := &MarketHoursService{
		calendars: make(map[string]*ExchangeCalendar),
		log:       log.With().Str("component", "market_hours").Logger(),
	}

	service.initializeCalendars()
	return service
}

// initializeCalendars sets up trading hours and holidays for all exchanges
func (s *MarketHoursService) initializeCalendars() {
	// ============================================================
	// AMERICAS
	// ============================================================

	// US Markets (NYSE, NASDAQ) - Conservative core hours: 10:00-15:00 ET
	nyLoc, _ := time.LoadLocation("America/New_York")
	usHolidays := []time.Time{
		time.Date(2026, 1, 1, 0, 0, 0, 0, nyLoc),   // New Year's Day
		time.Date(2026, 1, 19, 0, 0, 0, 0, nyLoc),  // MLK Day
		time.Date(2026, 2, 16, 0, 0, 0, 0, nyLoc),  // Presidents Day
		time.Date(2026, 4, 10, 0, 0, 0, 0, nyLoc),  // Good Friday
		time.Date(2026, 5, 25, 0, 0, 0, 0, nyLoc),  // Memorial Day
		time.Date(2026, 7, 3, 0, 0, 0, 0, nyLoc),   // Independence Day (observed)
		time.Date(2026, 9, 7, 0, 0, 0, 0, nyLoc),   // Labor Day
		time.Date(2026, 11, 26, 0, 0, 0, 0, nyLoc), // Thanksgiving
		time.Date(2026, 12, 25, 0, 0, 0, 0, nyLoc), // Christmas
	}

	s.calendars["NYSE"] = &ExchangeCalendar{
		Code:        "XNYS",
		Name:        "NYSE",
		TimezoneStr: "America/New_York",
		Timezone:    nyLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative 5-hour core window
		},
		Holidays2026: usHolidays,
		StrictHours:  false,
	}

	s.calendars["NASDAQ"] = &ExchangeCalendar{
		Code:        "XNAS",
		Name:        "NASDAQ",
		TimezoneStr: "America/New_York",
		Timezone:    nyLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative 5-hour core window
		},
		Holidays2026: usHolidays,
		StrictHours:  false,
	}

	s.calendars["NasdaqGS"] = s.calendars["NASDAQ"]
	s.calendars["NasdaqCM"] = s.calendars["NASDAQ"]

	// Toronto Stock Exchange (TSX)
	torontoLoc, _ := time.LoadLocation("America/Toronto")
	s.calendars["TSX"] = &ExchangeCalendar{
		Code:        "XTSE",
		Name:        "TSX",
		TimezoneStr: "America/Toronto",
		Timezone:    torontoLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative core hours
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, torontoLoc),   // New Year's Day
			time.Date(2026, 2, 16, 0, 0, 0, 0, torontoLoc),  // Family Day
			time.Date(2026, 4, 10, 0, 0, 0, 0, torontoLoc),  // Good Friday
			time.Date(2026, 5, 18, 0, 0, 0, 0, torontoLoc),  // Victoria Day
			time.Date(2026, 7, 1, 0, 0, 0, 0, torontoLoc),   // Canada Day
			time.Date(2026, 8, 3, 0, 0, 0, 0, torontoLoc),   // Civic Holiday
			time.Date(2026, 9, 7, 0, 0, 0, 0, torontoLoc),   // Labour Day
			time.Date(2026, 10, 12, 0, 0, 0, 0, torontoLoc), // Thanksgiving
			time.Date(2026, 12, 25, 0, 0, 0, 0, torontoLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, torontoLoc), // Boxing Day
		},
		StrictHours: false,
	}

	// ============================================================
	// EUROPE
	// ============================================================

	// Common European holidays for reference
	euCommonHolidays := []time.Time{
		time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),   // New Year's Day
		time.Date(2026, 4, 10, 0, 0, 0, 0, time.UTC),  // Good Friday
		time.Date(2026, 4, 13, 0, 0, 0, 0, time.UTC),  // Easter Monday
		time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC),   // Labor Day
		time.Date(2026, 12, 25, 0, 0, 0, 0, time.UTC), // Christmas
		time.Date(2026, 12, 26, 0, 0, 0, 0, time.UTC), // Boxing Day
	}

	// London Stock Exchange - Conservative core hours: 10:00-15:00 GMT
	londonLoc, _ := time.LoadLocation("Europe/London")
	londonHolidays := make([]time.Time, len(euCommonHolidays))
	for i, h := range euCommonHolidays {
		londonHolidays[i] = time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, londonLoc)
	}
	londonHolidays = append(londonHolidays,
		time.Date(2026, 5, 4, 0, 0, 0, 0, londonLoc),  // Early May Bank Holiday
		time.Date(2026, 5, 25, 0, 0, 0, 0, londonLoc), // Spring Bank Holiday
		time.Date(2026, 8, 31, 0, 0, 0, 0, londonLoc), // Summer Bank Holiday
	)

	s.calendars["LSE"] = &ExchangeCalendar{
		Code:        "XLON",
		Name:        "LSE",
		TimezoneStr: "Europe/London",
		Timezone:    londonLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative 5-hour core window
		},
		Holidays2026: londonHolidays,
		StrictHours:  false,
	}

	// XETRA (Frankfurt) - Conservative core hours: 10:00-16:00 CET
	frankfurtLoc, _ := time.LoadLocation("Europe/Berlin")
	frankfurtHolidays := make([]time.Time, len(euCommonHolidays))
	for i, h := range euCommonHolidays {
		frankfurtHolidays[i] = time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, frankfurtLoc)
	}
	frankfurtHolidays = append(frankfurtHolidays,
		time.Date(2026, 12, 24, 0, 0, 0, 0, frankfurtLoc), // Christmas Eve
		time.Date(2026, 12, 31, 0, 0, 0, 0, frankfurtLoc), // New Year's Eve
	)

	s.calendars["XETRA"] = &ExchangeCalendar{
		Code:        "XETR",
		Name:        "XETRA",
		TimezoneStr: "Europe/Berlin",
		Timezone:    frankfurtLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: frankfurtHolidays,
		StrictHours:  false,
	}
	s.calendars["XETR"] = s.calendars["XETRA"]

	// Euronext Paris - Conservative core hours: 10:00-16:00 CET
	parisLoc, _ := time.LoadLocation("Europe/Paris")
	parisHolidays := make([]time.Time, len(euCommonHolidays))
	for i, h := range euCommonHolidays {
		parisHolidays[i] = time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, parisLoc)
	}

	s.calendars["Paris"] = &ExchangeCalendar{
		Code:        "XPAR",
		Name:        "Paris",
		TimezoneStr: "Europe/Paris",
		Timezone:    parisLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: parisHolidays,
		StrictHours:  false,
	}

	// Euronext Amsterdam - Conservative core hours: 10:00-16:00 CET
	amsterdamLoc, _ := time.LoadLocation("Europe/Amsterdam")
	amsterdamHolidays := make([]time.Time, len(euCommonHolidays))
	for i, h := range euCommonHolidays {
		amsterdamHolidays[i] = time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, amsterdamLoc)
	}
	amsterdamHolidays = append(amsterdamHolidays,
		time.Date(2026, 4, 27, 0, 0, 0, 0, amsterdamLoc), // King's Day
	)

	s.calendars["Amsterdam"] = &ExchangeCalendar{
		Code:        "XAMS",
		Name:        "Amsterdam",
		TimezoneStr: "Europe/Amsterdam",
		Timezone:    amsterdamLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: amsterdamHolidays,
		StrictHours:  false,
	}

	// Borsa Italiana (Milan) - Conservative core hours: 10:00-16:00 CET
	milanLoc, _ := time.LoadLocation("Europe/Rome")
	milanHolidays := make([]time.Time, len(euCommonHolidays))
	for i, h := range euCommonHolidays {
		milanHolidays[i] = time.Date(h.Year(), h.Month(), h.Day(), 0, 0, 0, 0, milanLoc)
	}
	milanHolidays = append(milanHolidays,
		time.Date(2026, 8, 15, 0, 0, 0, 0, milanLoc),  // Assumption Day
		time.Date(2026, 12, 24, 0, 0, 0, 0, milanLoc), // Christmas Eve
		time.Date(2026, 12, 31, 0, 0, 0, 0, milanLoc), // New Year's Eve
	)

	s.calendars["Milan"] = &ExchangeCalendar{
		Code:        "XMIL",
		Name:        "Milan",
		TimezoneStr: "Europe/Rome",
		Timezone:    milanLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: milanHolidays,
		StrictHours:  false,
	}

	// SIX Swiss Exchange (Zurich) - Conservative core hours: 10:00-16:00 CET
	zurichLoc, _ := time.LoadLocation("Europe/Zurich")
	s.calendars["SIX"] = &ExchangeCalendar{
		Code:        "XSWX",
		Name:        "SIX",
		TimezoneStr: "Europe/Zurich",
		Timezone:    zurichLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, zurichLoc),   // New Year's Day
			time.Date(2026, 1, 2, 0, 0, 0, 0, zurichLoc),   // Berchtold's Day
			time.Date(2026, 4, 10, 0, 0, 0, 0, zurichLoc),  // Good Friday
			time.Date(2026, 4, 13, 0, 0, 0, 0, zurichLoc),  // Easter Monday
			time.Date(2026, 5, 1, 0, 0, 0, 0, zurichLoc),   // Labor Day
			time.Date(2026, 5, 21, 0, 0, 0, 0, zurichLoc),  // Ascension Day
			time.Date(2026, 6, 1, 0, 0, 0, 0, zurichLoc),   // Whit Monday
			time.Date(2026, 8, 1, 0, 0, 0, 0, zurichLoc),   // National Day
			time.Date(2026, 12, 25, 0, 0, 0, 0, zurichLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, zurichLoc), // Boxing Day
		},
		StrictHours: false,
	}

	// Athens Stock Exchange - Conservative core hours: 11:00-16:00 EET
	athensLoc, _ := time.LoadLocation("Europe/Athens")
	s.calendars["Athens"] = &ExchangeCalendar{
		Code:        "ASEX",
		Name:        "Athens",
		TimezoneStr: "Europe/Athens",
		Timezone:    athensLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 11, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 5-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, athensLoc),   // New Year's Day
			time.Date(2026, 1, 6, 0, 0, 0, 0, athensLoc),   // Epiphany
			time.Date(2026, 3, 2, 0, 0, 0, 0, athensLoc),   // Clean Monday
			time.Date(2026, 3, 25, 0, 0, 0, 0, athensLoc),  // Independence Day
			time.Date(2026, 4, 17, 0, 0, 0, 0, athensLoc),  // Good Friday (Orthodox)
			time.Date(2026, 4, 20, 0, 0, 0, 0, athensLoc),  // Easter Monday (Orthodox)
			time.Date(2026, 5, 1, 0, 0, 0, 0, athensLoc),   // Labor Day
			time.Date(2026, 6, 8, 0, 0, 0, 0, athensLoc),   // Whit Monday (Orthodox)
			time.Date(2026, 8, 15, 0, 0, 0, 0, athensLoc),  // Assumption
			time.Date(2026, 10, 28, 0, 0, 0, 0, athensLoc), // Ochi Day
			time.Date(2026, 12, 25, 0, 0, 0, 0, athensLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, athensLoc), // Boxing Day
		},
		StrictHours: false,
	}

	// Copenhagen Stock Exchange - Conservative core hours: 10:00-15:00 CET
	copenhagenLoc, _ := time.LoadLocation("Europe/Copenhagen")
	s.calendars["Copenhagen"] = &ExchangeCalendar{
		Code:        "XCSE",
		Name:        "Copenhagen",
		TimezoneStr: "Europe/Copenhagen",
		Timezone:    copenhagenLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative 5-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, copenhagenLoc),   // New Year's Day
			time.Date(2026, 4, 9, 0, 0, 0, 0, copenhagenLoc),   // Maundy Thursday
			time.Date(2026, 4, 10, 0, 0, 0, 0, copenhagenLoc),  // Good Friday
			time.Date(2026, 4, 13, 0, 0, 0, 0, copenhagenLoc),  // Easter Monday
			time.Date(2026, 5, 8, 0, 0, 0, 0, copenhagenLoc),   // Store Bededag
			time.Date(2026, 5, 21, 0, 0, 0, 0, copenhagenLoc),  // Ascension Day
			time.Date(2026, 6, 1, 0, 0, 0, 0, copenhagenLoc),   // Whit Monday
			time.Date(2026, 12, 24, 0, 0, 0, 0, copenhagenLoc), // Christmas Eve
			time.Date(2026, 12, 25, 0, 0, 0, 0, copenhagenLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, copenhagenLoc), // Boxing Day
			time.Date(2026, 12, 31, 0, 0, 0, 0, copenhagenLoc), // New Year's Eve
		},
		StrictHours: false,
	}

	// ============================================================
	// ASIA-PACIFIC (CRITICAL - Strict market hours, lunch breaks)
	// ============================================================

	// Hong Kong Stock Exchange (CRITICAL - lunch break, strict hours)
	// Conservative: 10:00-11:30, 13:30-15:30 HKT (core hours avoiding open/close edge cases)
	hkLoc, _ := time.LoadLocation("Asia/Hong_Kong")
	s.calendars["HKSE"] = &ExchangeCalendar{
		Code:        "XHKG",
		Name:        "HKSE",
		TimezoneStr: "Asia/Hong_Kong",
		Timezone:    hkLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 11, CloseMinute: 30},  // Morning session (1.5h core)
			{OpenHour: 13, OpenMinute: 30, CloseHour: 15, CloseMinute: 30}, // Afternoon session (2h core)
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, hkLoc),   // New Year's Day
			time.Date(2026, 1, 29, 0, 0, 0, 0, hkLoc),  // Lunar New Year
			time.Date(2026, 1, 30, 0, 0, 0, 0, hkLoc),  // Lunar New Year
			time.Date(2026, 1, 31, 0, 0, 0, 0, hkLoc),  // Lunar New Year
			time.Date(2026, 4, 6, 0, 0, 0, 0, hkLoc),   // Ching Ming Festival
			time.Date(2026, 4, 10, 0, 0, 0, 0, hkLoc),  // Good Friday
			time.Date(2026, 4, 11, 0, 0, 0, 0, hkLoc),  // Day after Good Friday
			time.Date(2026, 4, 13, 0, 0, 0, 0, hkLoc),  // Easter Monday
			time.Date(2026, 5, 1, 0, 0, 0, 0, hkLoc),   // Labor Day
			time.Date(2026, 5, 19, 0, 0, 0, 0, hkLoc),  // Buddha's Birthday
			time.Date(2026, 6, 25, 0, 0, 0, 0, hkLoc),  // Dragon Boat Festival
			time.Date(2026, 7, 1, 0, 0, 0, 0, hkLoc),   // HKSAR Establishment Day
			time.Date(2026, 10, 1, 0, 0, 0, 0, hkLoc),  // National Day
			time.Date(2026, 10, 2, 0, 0, 0, 0, hkLoc),  // Day after Mid-Autumn Festival
			time.Date(2026, 10, 26, 0, 0, 0, 0, hkLoc), // Chung Yeung Festival
			time.Date(2026, 12, 25, 0, 0, 0, 0, hkLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, hkLoc), // Boxing Day
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}
	s.calendars["XHKG"] = s.calendars["HKSE"]

	// Shanghai/Shenzhen Stock Exchanges (CRITICAL - lunch break, strict hours)
	// Conservative: 10:00-11:00, 13:30-14:30 CST (core hours avoiding edge cases)
	shanghaiLoc, _ := time.LoadLocation("Asia/Shanghai")
	chinaHolidays := []time.Time{
		time.Date(2026, 1, 1, 0, 0, 0, 0, shanghaiLoc),  // New Year's Day
		time.Date(2026, 1, 2, 0, 0, 0, 0, shanghaiLoc),  // New Year's Day
		time.Date(2026, 1, 3, 0, 0, 0, 0, shanghaiLoc),  // New Year's Day
		time.Date(2026, 2, 17, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 18, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 19, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 20, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 21, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 22, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 2, 23, 0, 0, 0, 0, shanghaiLoc), // Spring Festival
		time.Date(2026, 4, 4, 0, 0, 0, 0, shanghaiLoc),  // Qingming Festival
		time.Date(2026, 4, 5, 0, 0, 0, 0, shanghaiLoc),  // Qingming Festival
		time.Date(2026, 4, 6, 0, 0, 0, 0, shanghaiLoc),  // Qingming Festival
		time.Date(2026, 5, 1, 0, 0, 0, 0, shanghaiLoc),  // Labor Day
		time.Date(2026, 5, 2, 0, 0, 0, 0, shanghaiLoc),  // Labor Day
		time.Date(2026, 5, 3, 0, 0, 0, 0, shanghaiLoc),  // Labor Day
		time.Date(2026, 6, 22, 0, 0, 0, 0, shanghaiLoc), // Dragon Boat Festival
		time.Date(2026, 6, 23, 0, 0, 0, 0, shanghaiLoc), // Dragon Boat Festival
		time.Date(2026, 6, 24, 0, 0, 0, 0, shanghaiLoc), // Dragon Boat Festival
		time.Date(2026, 10, 1, 0, 0, 0, 0, shanghaiLoc), // National Day
		time.Date(2026, 10, 2, 0, 0, 0, 0, shanghaiLoc), // National Day
		time.Date(2026, 10, 3, 0, 0, 0, 0, shanghaiLoc), // Mid-Autumn Festival
		time.Date(2026, 10, 4, 0, 0, 0, 0, shanghaiLoc), // National Day
		time.Date(2026, 10, 5, 0, 0, 0, 0, shanghaiLoc), // National Day
		time.Date(2026, 10, 6, 0, 0, 0, 0, shanghaiLoc), // National Day
		time.Date(2026, 10, 7, 0, 0, 0, 0, shanghaiLoc), // National Day
	}

	s.calendars["Shenzhen"] = &ExchangeCalendar{
		Code:        "XSHG",
		Name:        "Shenzhen",
		TimezoneStr: "Asia/Shanghai",
		Timezone:    shanghaiLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 11, CloseMinute: 0},   // Morning session (1h core)
			{OpenHour: 13, OpenMinute: 30, CloseHour: 14, CloseMinute: 30}, // Afternoon session (1h core)
		},
		Holidays2026: chinaHolidays,
		StrictHours:  true, // CRITICAL - trades only when market open
	}
	s.calendars["XSHG"] = s.calendars["Shenzhen"]

	// Tokyo Stock Exchange (CRITICAL - lunch break, strict hours)
	// Conservative: 10:00-11:00, 13:00-14:30 JST (core hours avoiding edge cases)
	tokyoLoc, _ := time.LoadLocation("Asia/Tokyo")
	s.calendars["TSE"] = &ExchangeCalendar{
		Code:        "XTSE",
		Name:        "TSE",
		TimezoneStr: "Asia/Tokyo",
		Timezone:    tokyoLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 11, CloseMinute: 0},  // Morning session (1h core)
			{OpenHour: 13, OpenMinute: 0, CloseHour: 14, CloseMinute: 30}, // Afternoon session (1.5h core)
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, tokyoLoc),   // New Year's Day
			time.Date(2026, 1, 2, 0, 0, 0, 0, tokyoLoc),   // New Year's Holiday
			time.Date(2026, 1, 3, 0, 0, 0, 0, tokyoLoc),   // New Year's Holiday
			time.Date(2026, 1, 12, 0, 0, 0, 0, tokyoLoc),  // Coming of Age Day
			time.Date(2026, 2, 11, 0, 0, 0, 0, tokyoLoc),  // National Foundation Day
			time.Date(2026, 2, 23, 0, 0, 0, 0, tokyoLoc),  // Emperor's Birthday
			time.Date(2026, 3, 20, 0, 0, 0, 0, tokyoLoc),  // Vernal Equinox Day
			time.Date(2026, 4, 29, 0, 0, 0, 0, tokyoLoc),  // Showa Day
			time.Date(2026, 5, 3, 0, 0, 0, 0, tokyoLoc),   // Constitution Memorial Day
			time.Date(2026, 5, 4, 0, 0, 0, 0, tokyoLoc),   // Greenery Day
			time.Date(2026, 5, 5, 0, 0, 0, 0, tokyoLoc),   // Children's Day
			time.Date(2026, 7, 20, 0, 0, 0, 0, tokyoLoc),  // Marine Day
			time.Date(2026, 8, 11, 0, 0, 0, 0, tokyoLoc),  // Mountain Day
			time.Date(2026, 9, 21, 0, 0, 0, 0, tokyoLoc),  // Respect for the Aged Day
			time.Date(2026, 9, 22, 0, 0, 0, 0, tokyoLoc),  // Autumnal Equinox Day
			time.Date(2026, 10, 12, 0, 0, 0, 0, tokyoLoc), // Sports Day
			time.Date(2026, 11, 3, 0, 0, 0, 0, tokyoLoc),  // Culture Day
			time.Date(2026, 11, 23, 0, 0, 0, 0, tokyoLoc), // Labor Thanksgiving Day
			time.Date(2026, 12, 31, 0, 0, 0, 0, tokyoLoc), // New Year's Eve
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}
	s.calendars["XTSE"] = s.calendars["TSE"]

	// Singapore Exchange (CRITICAL - strict hours, no lunch break)
	// Conservative: 10:00-16:00 SGT (core 6-hour window)
	singaporeLoc, _ := time.LoadLocation("Asia/Singapore")
	s.calendars["SGX"] = &ExchangeCalendar{
		Code:        "XSES",
		Name:        "SGX",
		TimezoneStr: "Asia/Singapore",
		Timezone:    singaporeLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 16, CloseMinute: 0}, // Conservative 6-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, singaporeLoc),   // New Year's Day
			time.Date(2026, 1, 29, 0, 0, 0, 0, singaporeLoc),  // Chinese New Year
			time.Date(2026, 1, 30, 0, 0, 0, 0, singaporeLoc),  // Chinese New Year
			time.Date(2026, 4, 10, 0, 0, 0, 0, singaporeLoc),  // Good Friday
			time.Date(2026, 5, 1, 0, 0, 0, 0, singaporeLoc),   // Labor Day
			time.Date(2026, 5, 21, 0, 0, 0, 0, singaporeLoc),  // Vesak Day
			time.Date(2026, 6, 25, 0, 0, 0, 0, singaporeLoc),  // Hari Raya Puasa
			time.Date(2026, 8, 9, 0, 0, 0, 0, singaporeLoc),   // National Day
			time.Date(2026, 9, 1, 0, 0, 0, 0, singaporeLoc),   // Hari Raya Haji
			time.Date(2026, 10, 21, 0, 0, 0, 0, singaporeLoc), // Deepavali
			time.Date(2026, 12, 25, 0, 0, 0, 0, singaporeLoc), // Christmas
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}

	// Korea Exchange (KRX) - Conservative: 10:00-14:30 KST (core 4.5-hour window)
	seoulLoc, _ := time.LoadLocation("Asia/Seoul")
	s.calendars["KRX"] = &ExchangeCalendar{
		Code:        "XKRX",
		Name:        "KRX",
		TimezoneStr: "Asia/Seoul",
		Timezone:    seoulLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 14, CloseMinute: 30}, // Conservative 4.5-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, seoulLoc),   // New Year's Day
			time.Date(2026, 1, 29, 0, 0, 0, 0, seoulLoc),  // Lunar New Year
			time.Date(2026, 1, 30, 0, 0, 0, 0, seoulLoc),  // Lunar New Year
			time.Date(2026, 1, 31, 0, 0, 0, 0, seoulLoc),  // Lunar New Year
			time.Date(2026, 3, 1, 0, 0, 0, 0, seoulLoc),   // Independence Movement Day
			time.Date(2026, 5, 5, 0, 0, 0, 0, seoulLoc),   // Children's Day
			time.Date(2026, 5, 19, 0, 0, 0, 0, seoulLoc),  // Buddha's Birthday
			time.Date(2026, 6, 6, 0, 0, 0, 0, seoulLoc),   // Memorial Day
			time.Date(2026, 8, 15, 0, 0, 0, 0, seoulLoc),  // Liberation Day
			time.Date(2026, 10, 1, 0, 0, 0, 0, seoulLoc),  // Chuseok
			time.Date(2026, 10, 2, 0, 0, 0, 0, seoulLoc),  // Chuseok
			time.Date(2026, 10, 3, 0, 0, 0, 0, seoulLoc),  // National Foundation Day
			time.Date(2026, 10, 9, 0, 0, 0, 0, seoulLoc),  // Hangeul Day
			time.Date(2026, 12, 25, 0, 0, 0, 0, seoulLoc), // Christmas
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}

	// Taiwan Stock Exchange (CRITICAL - strict hours, lunch break)
	// Conservative: 10:00-12:00, 13:30-13:00 CST (core hours)
	taipeiLoc, _ := time.LoadLocation("Asia/Taipei")
	s.calendars["TWSE"] = &ExchangeCalendar{
		Code:        "XTAI",
		Name:        "TWSE",
		TimezoneStr: "Asia/Taipei",
		Timezone:    taipeiLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 0, CloseHour: 12, CloseMinute: 0}, // Morning session (2h core)
			// Note: Afternoon session is very short (13:00-13:30), omitting for safety
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, taipeiLoc),   // New Year's Day
			time.Date(2026, 1, 29, 0, 0, 0, 0, taipeiLoc),  // Lunar New Year
			time.Date(2026, 1, 30, 0, 0, 0, 0, taipeiLoc),  // Lunar New Year
			time.Date(2026, 1, 31, 0, 0, 0, 0, taipeiLoc),  // Lunar New Year
			time.Date(2026, 2, 28, 0, 0, 0, 0, taipeiLoc),  // Peace Memorial Day
			time.Date(2026, 4, 4, 0, 0, 0, 0, taipeiLoc),   // Tomb Sweeping Day
			time.Date(2026, 6, 25, 0, 0, 0, 0, taipeiLoc),  // Dragon Boat Festival
			time.Date(2026, 10, 1, 0, 0, 0, 0, taipeiLoc),  // Mid-Autumn Festival
			time.Date(2026, 10, 10, 0, 0, 0, 0, taipeiLoc), // National Day
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}

	// Australian Stock Exchange (CRITICAL - strict hours, no lunch break)
	// Conservative: 11:00-15:00 AEDT (core 4-hour window)
	sydneyLoc, _ := time.LoadLocation("Australia/Sydney")
	s.calendars["ASX"] = &ExchangeCalendar{
		Code:        "XASX",
		Name:        "ASX",
		TimezoneStr: "Australia/Sydney",
		Timezone:    sydneyLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 11, OpenMinute: 0, CloseHour: 15, CloseMinute: 0}, // Conservative 4-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 1, 0, 0, 0, 0, sydneyLoc),   // New Year's Day
			time.Date(2026, 1, 26, 0, 0, 0, 0, sydneyLoc),  // Australia Day
			time.Date(2026, 4, 10, 0, 0, 0, 0, sydneyLoc),  // Good Friday
			time.Date(2026, 4, 11, 0, 0, 0, 0, sydneyLoc),  // Easter Saturday
			time.Date(2026, 4, 13, 0, 0, 0, 0, sydneyLoc),  // Easter Monday
			time.Date(2026, 4, 25, 0, 0, 0, 0, sydneyLoc),  // ANZAC Day
			time.Date(2026, 6, 8, 0, 0, 0, 0, sydneyLoc),   // Queen's Birthday
			time.Date(2026, 12, 25, 0, 0, 0, 0, sydneyLoc), // Christmas
			time.Date(2026, 12, 26, 0, 0, 0, 0, sydneyLoc), // Boxing Day
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}
	s.calendars["XASX"] = s.calendars["ASX"]

	// India NSE (National Stock Exchange) - Conservative: 10:30-14:30 IST (core 4-hour window)
	mumbaiLoc, _ := time.LoadLocation("Asia/Kolkata")
	s.calendars["NSE"] = &ExchangeCalendar{
		Code:        "XNSE",
		Name:        "NSE",
		TimezoneStr: "Asia/Kolkata",
		Timezone:    mumbaiLoc,
		TradingWindows: []TradingWindow{
			{OpenHour: 10, OpenMinute: 30, CloseHour: 14, CloseMinute: 30}, // Conservative 4-hour core window
		},
		Holidays2026: []time.Time{
			time.Date(2026, 1, 26, 0, 0, 0, 0, mumbaiLoc),  // Republic Day
			time.Date(2026, 3, 14, 0, 0, 0, 0, mumbaiLoc),  // Holi
			time.Date(2026, 3, 30, 0, 0, 0, 0, mumbaiLoc),  // Ram Navami
			time.Date(2026, 4, 2, 0, 0, 0, 0, mumbaiLoc),   // Mahavir Jayanti
			time.Date(2026, 4, 10, 0, 0, 0, 0, mumbaiLoc),  // Good Friday
			time.Date(2026, 4, 14, 0, 0, 0, 0, mumbaiLoc),  // Ambedkar Jayanti
			time.Date(2026, 5, 1, 0, 0, 0, 0, mumbaiLoc),   // Maharashtra Day
			time.Date(2026, 7, 7, 0, 0, 0, 0, mumbaiLoc),   // Bakri Id
			time.Date(2026, 8, 15, 0, 0, 0, 0, mumbaiLoc),  // Independence Day
			time.Date(2026, 10, 2, 0, 0, 0, 0, mumbaiLoc),  // Gandhi Jayanti
			time.Date(2026, 10, 23, 0, 0, 0, 0, mumbaiLoc), // Dussehra
			time.Date(2026, 11, 11, 0, 0, 0, 0, mumbaiLoc), // Diwali
			time.Date(2026, 11, 12, 0, 0, 0, 0, mumbaiLoc), // Diwali (Balipratipada)
			time.Date(2026, 11, 25, 0, 0, 0, 0, mumbaiLoc), // Gurunanak Jayanti
			time.Date(2026, 12, 25, 0, 0, 0, 0, mumbaiLoc), // Christmas
		},
		StrictHours: true, // CRITICAL - trades only when market open
	}

	s.log.Info().Int("calendars", len(s.calendars)).Msg("Market hours calendars initialized")
}

// GetCalendar returns the calendar for an exchange name (case-insensitive lookup)
func (s *MarketHoursService) GetCalendar(exchangeName string) *ExchangeCalendar {
	if cal, ok := s.calendars[exchangeName]; ok {
		return cal
	}

	// Default to NYSE if not found
	s.log.Warn().Str("exchange", exchangeName).Msg("Unknown exchange, defaulting to NYSE")
	return s.calendars["NYSE"]
}

// IsMarketOpen checks if a market is currently open for trading
func (s *MarketHoursService) IsMarketOpen(exchangeName string) bool {
	cal := s.GetCalendar(exchangeName)
	now := time.Now().In(cal.Timezone)

	// Check if it's a weekend
	if now.Weekday() == time.Saturday || now.Weekday() == time.Sunday {
		return false
	}

	// Check if it's a holiday
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, cal.Timezone)
	for _, holiday := range cal.Holidays2026 {
		if holiday.Equal(today) {
			return false
		}
	}

	// Check if we're within any trading window
	currentMinutes := now.Hour()*60 + now.Minute()
	for _, window := range cal.TradingWindows {
		openMinutes := window.OpenHour*60 + window.OpenMinute
		closeMinutes := window.CloseHour*60 + window.CloseMinute

		if currentMinutes >= openMinutes && currentMinutes < closeMinutes {
			return true
		}
	}

	return false
}

// RequiresStrictMarketHours checks if an exchange requires strict market hours (Asian markets)
func (s *MarketHoursService) RequiresStrictMarketHours(exchangeName string) bool {
	cal := s.GetCalendar(exchangeName)
	return cal.StrictHours
}

// ShouldCheckMarketHours determines if market hours check is required for a trade
// Rules:
// - SELL orders: Always check market hours (all markets)
// - BUY orders: Only check if exchange requires strict market hours (Asian markets)
func (s *MarketHoursService) ShouldCheckMarketHours(exchangeName string, side string) bool {
	if side == "SELL" {
		return true
	}
	if side == "BUY" {
		return s.RequiresStrictMarketHours(exchangeName)
	}
	// Unknown side, default to checking (safe default)
	return true
}

// MarketStatus represents the status of a market
type MarketStatus struct {
	Exchange string `json:"exchange"`
	IsOpen   bool   `json:"is_open"`
	Timezone string `json:"timezone"`
}

// GetAllMarketStatuses returns status for all configured markets
func (s *MarketHoursService) GetAllMarketStatuses() []MarketStatus {
	statuses := make([]MarketStatus, 0, len(s.calendars))
	seen := make(map[string]bool)

	for name, cal := range s.calendars {
		// Skip aliases (only report each unique calendar once)
		if seen[cal.Code] {
			continue
		}
		seen[cal.Code] = true

		statuses = append(statuses, MarketStatus{
			Exchange: name,
			IsOpen:   s.IsMarketOpen(name),
			Timezone: cal.TimezoneStr,
		})
	}

	return statuses
}
