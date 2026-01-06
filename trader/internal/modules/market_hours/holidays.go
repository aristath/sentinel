package market_hours

import "time"

// CalculateEaster calculates the date of Easter for a given year and calendar type
// Uses the algorithm for Gregorian or Julian calendar
func CalculateEaster(year int, calendarType CalendarType) time.Time {
	if calendarType == Julian {
		return calculateJulianEaster(year)
	}
	return calculateGregorianEaster(year)
}

// calculateGregorianEaster calculates Easter using the Gregorian calendar (Western/Catholic)
// Algorithm based on the computus method
func calculateGregorianEaster(year int) time.Time {
	// Golden Number (position in 19-year Metonic cycle)
	a := year % 19

	// Century
	b := year / 100
	c := year % 100

	// Corrections
	d := b / 4
	e := b % 4
	f := (b + 8) / 25
	g := (b - f + 1) / 3
	h := (19*a + b - d - g + 15) % 30
	i := c / 4
	k := c % 4
	l := (32 + 2*e + 2*i - h - k) % 7
	m := (a + 11*h + 22*l) / 451

	// Month and day
	month := (h + l - 7*m + 114) / 31
	day := ((h + l - 7*m + 114) % 31) + 1

	return time.Date(year, time.Month(month), day, 0, 0, 0, 0, time.UTC)
}

// calculateJulianEaster calculates Easter using the Julian calendar (Orthodox)
// Algorithm based on the Julian computus
// Returns the date in Gregorian calendar
func calculateJulianEaster(year int) time.Time {
	// Golden Number (position in 19-year Metonic cycle)
	a := year % 19

	// Calculate epact and other values
	b := year % 4
	c := year % 7

	// Julian calendar calculations
	// d is the "epact" - age of moon on Jan 1
	d := (19*a + 15) % 30
	// e is used to find the Sunday
	e := (2*b + 4*c + 6*d + 6) % 7

	// Easter date in Julian calendar
	// March 22 + d + e days
	julianEasterDay := 22 + d + e

	// Determine month (March or April)
	var julianMonth time.Month = 3
	if julianEasterDay > 31 {
		julianEasterDay -= 31
		julianMonth = 4
	}

	// Create the date in Julian calendar (conceptually)
	// Go's time package uses Gregorian, so we create the Julian date
	// then convert to Gregorian by adding the calendar difference
	// For years 1900-2099, the difference is 13 days
	julianDate := time.Date(year, julianMonth, julianEasterDay, 0, 0, 0, 0, time.UTC)

	// Convert from Julian to Gregorian
	// The difference varies by century, but for 1900-2099 it's 13 days
	// However, we need to be careful: the algorithm gives us the date in Julian calendar
	// but we want to return it in Gregorian calendar
	// The standard conversion: add 13 days for years 1900-2099
	gregorianEaster := julianDate.AddDate(0, 0, 13)

	return gregorianEaster
}

// CalculateGoodFriday calculates Good Friday (Friday before Easter)
func CalculateGoodFriday(year int, calendarType CalendarType) time.Time {
	easter := CalculateEaster(year, calendarType)
	return easter.AddDate(0, 0, -2) // Two days before Easter Sunday
}

// findNthWeekday finds the nth occurrence of a weekday in a given month/year
// n: 1 = first, 2 = second, etc.
func findNthWeekday(year, month int, weekday time.Weekday, n int) time.Time {
	// Start with the first day of the month
	date := time.Date(year, time.Month(month), 1, 0, 0, 0, 0, time.UTC)

	// Find the first occurrence of the weekday
	daysToAdd := int(weekday - date.Weekday())
	if daysToAdd < 0 {
		daysToAdd += 7
	}
	date = date.AddDate(0, 0, daysToAdd)

	// Add (n-1) weeks to get the nth occurrence
	date = date.AddDate(0, 0, (n-1)*7)

	return date
}

// findLastWeekday finds the last occurrence of a weekday in a given month/year
func findLastWeekday(year, month int, weekday time.Weekday) time.Time {
	// Start with the last day of the month
	date := time.Date(year, time.Month(month+1), 0, 0, 0, 0, 0, time.UTC)

	// Find the last occurrence of the weekday
	daysToSubtract := int(date.Weekday() - weekday)
	if daysToSubtract < 0 {
		daysToSubtract += 7
	}
	date = date.AddDate(0, 0, -daysToSubtract)

	return date
}

// observeOnWeekday moves a date to the nearest weekday if it falls on a weekend
// Saturday -> Friday, Sunday -> Monday
func observeOnWeekday(date time.Time) time.Time {
	switch date.Weekday() {
	case time.Saturday:
		return date.AddDate(0, 0, -1) // Move to Friday
	case time.Sunday:
		return date.AddDate(0, 0, 1) // Move to Monday
	default:
		return date // Already a weekday
	}
}

// CalculateUSHolidays calculates all US market holidays for a given year
func CalculateUSHolidays(year int) []time.Time {
	holidays := make([]time.Time, 0, 10)

	// New Year's Day - Jan 1 (observed on nearest weekday)
	newYear := time.Date(year, 1, 1, 0, 0, 0, 0, time.UTC)
	holidays = append(holidays, observeOnWeekday(newYear))

	// Martin Luther King Jr. Day - 3rd Monday in January
	mlkDay := findNthWeekday(year, 1, time.Monday, 3)
	holidays = append(holidays, mlkDay)

	// Presidents Day - 3rd Monday in February
	presidentsDay := findNthWeekday(year, 2, time.Monday, 3)
	holidays = append(holidays, presidentsDay)

	// Good Friday - Friday before Easter (Gregorian)
	goodFriday := CalculateGoodFriday(year, Gregorian)
	holidays = append(holidays, goodFriday)

	// Memorial Day - Last Monday in May
	memorialDay := findLastWeekday(year, 5, time.Monday)
	holidays = append(holidays, memorialDay)

	// Juneteenth - June 19 (observed on nearest weekday)
	juneteenth := time.Date(year, 6, 19, 0, 0, 0, 0, time.UTC)
	holidays = append(holidays, observeOnWeekday(juneteenth))

	// Independence Day - July 4 (observed on nearest weekday)
	independenceDay := time.Date(year, 7, 4, 0, 0, 0, 0, time.UTC)
	holidays = append(holidays, observeOnWeekday(independenceDay))

	// Labor Day - 1st Monday in September
	laborDay := findNthWeekday(year, 9, time.Monday, 1)
	holidays = append(holidays, laborDay)

	// Thanksgiving - 4th Thursday in November
	thanksgiving := findNthWeekday(year, 11, time.Thursday, 4)
	holidays = append(holidays, thanksgiving)

	// Christmas - Dec 25 (observed on nearest weekday)
	christmas := time.Date(year, 12, 25, 0, 0, 0, 0, time.UTC)
	holidays = append(holidays, observeOnWeekday(christmas))

	return holidays
}
