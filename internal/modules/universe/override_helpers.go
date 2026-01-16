package universe

import (
	"reflect"
	"strconv"
	"strings"
)

// SecurityDefaults defines the default values for fields removed from securities table
// These are applied at read time when no override exists
var SecurityDefaults = map[string]interface{}{
	"allow_buy":           true,
	"allow_sell":          true,
	"min_lot":             1,
	"priority_multiplier": 1.0,
}

// ApplyDefaults applies default values for fields that were removed from the securities table
// This should be called after scanning a security from the database
func ApplyDefaults(security *Security) {
	if security == nil {
		return
	}

	// Apply defaults
	security.AllowBuy = true
	security.AllowSell = true
	security.MinLot = 1
	security.PriorityMultiplier = 1.0
}

// ApplyOverrides applies all non-empty overrides to a security using reflection
// This is a generic function that works with any field in the Security struct
// Field names are matched via json tags (e.g., "allow_buy" matches `json:"allow_buy"`)
func ApplyOverrides(security *Security, overrides map[string]string) {
	if security == nil || len(overrides) == 0 {
		return
	}

	v := reflect.ValueOf(security).Elem()
	t := v.Type()

	// Build a map of json tag -> field index for efficient lookup
	jsonToField := make(map[string]int)
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		jsonTag := field.Tag.Get("json")
		// Extract field name from json tag (handles "name,omitempty")
		jsonName := strings.Split(jsonTag, ",")[0]
		if jsonName != "" && jsonName != "-" {
			jsonToField[jsonName] = i
		}
	}

	// Apply overrides
	for fieldName, value := range overrides {
		// Skip empty values - they represent "use default"
		if value == "" {
			continue
		}

		fieldIdx, exists := jsonToField[fieldName]
		if !exists {
			continue // Unknown field, skip
		}

		fieldValue := v.Field(fieldIdx)
		if !fieldValue.CanSet() {
			continue
		}

		switch fieldValue.Kind() {
		case reflect.String:
			fieldValue.SetString(value)
		case reflect.Bool:
			fieldValue.SetBool(value == "true")
		case reflect.Int, reflect.Int64:
			if intVal, err := strconv.ParseInt(value, 10, 64); err == nil {
				fieldValue.SetInt(intVal)
			} else {
				// Parse error - invalid override value, keeping default
				// This indicates data integrity issue - validation should happen at override creation
			}
		case reflect.Float64:
			if floatVal, err := strconv.ParseFloat(value, 64); err == nil {
				fieldValue.SetFloat(floatVal)
			} else {
				// Parse error - invalid override value, keeping default
				// This indicates data integrity issue - validation should happen at override creation
			}
		}
	}
}

// ApplyOverridesToSecurityWithScore applies all non-empty overrides to a SecurityWithScore using reflection
// Similar to ApplyOverrides but for the SecurityWithScore struct
func ApplyOverridesToSecurityWithScore(sws *SecurityWithScore, overrides map[string]string) {
	if sws == nil || len(overrides) == 0 {
		return
	}

	v := reflect.ValueOf(sws).Elem()
	t := v.Type()

	// Build a map of json tag -> field index for efficient lookup
	jsonToField := make(map[string]int)
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		jsonTag := field.Tag.Get("json")
		// Extract field name from json tag (handles "name,omitempty")
		jsonName := strings.Split(jsonTag, ",")[0]
		if jsonName != "" && jsonName != "-" {
			jsonToField[jsonName] = i
		}
	}

	// Apply overrides
	for fieldName, value := range overrides {
		// Skip empty values - they represent "use default"
		if value == "" {
			continue
		}

		fieldIdx, exists := jsonToField[fieldName]
		if !exists {
			continue // Unknown field, skip
		}

		fieldValue := v.Field(fieldIdx)
		if !fieldValue.CanSet() {
			continue
		}

		switch fieldValue.Kind() {
		case reflect.String:
			fieldValue.SetString(value)
		case reflect.Bool:
			fieldValue.SetBool(value == "true")
		case reflect.Int, reflect.Int64:
			if intVal, err := strconv.ParseInt(value, 10, 64); err == nil {
				fieldValue.SetInt(intVal)
			} else {
				// Parse error - invalid override value, keeping default
				// This indicates data integrity issue - validation should happen at override creation
			}
		case reflect.Float64:
			if floatVal, err := strconv.ParseFloat(value, 64); err == nil {
				fieldValue.SetFloat(floatVal)
			} else {
				// Parse error - invalid override value, keeping default
				// This indicates data integrity issue - validation should happen at override creation
			}
		}
	}
}
