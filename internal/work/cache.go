package work

import (
	"database/sql"
	"encoding/json"
	"time"
)

// Cache provides simple key-value storage with expiration.
type Cache struct {
	db *sql.DB
}

// NewCache creates a new cache instance.
func NewCache(db *sql.DB) *Cache {
	return &Cache{db: db}
}

// GetExpiresAt returns the expiration timestamp for a key.
// Returns 0 if key doesn't exist.
// Does not check if expired - callers should compare with time.Now().Unix().
func (c *Cache) GetExpiresAt(key string) int64 {
	var expiresAt int64
	err := c.db.QueryRow("SELECT expires_at FROM cache WHERE key = ?", key).Scan(&expiresAt)
	if err != nil {
		return 0
	}
	return expiresAt
}

// Set stores a key with expiration timestamp.
func (c *Cache) Set(key string, expiresAt int64) error {
	_, err := c.db.Exec(`
		INSERT INTO cache (key, value, expires_at)
		VALUES (?, '', ?)
		ON CONFLICT(key) DO UPDATE SET
			expires_at = excluded.expires_at
	`, key, expiresAt)
	return err
}

// Delete removes a cache entry.
func (c *Cache) Delete(key string) error {
	_, err := c.db.Exec("DELETE FROM cache WHERE key = ?", key)
	return err
}

// DeleteByPrefix removes all cache entries matching a prefix.
func (c *Cache) DeleteByPrefix(prefix string) error {
	_, err := c.db.Exec("DELETE FROM cache WHERE key LIKE ?", prefix+"%")
	return err
}

// SetJSON stores a value as JSON in the cache with expiration timestamp.
func (c *Cache) SetJSON(key string, value interface{}, expiresAt int64) error {
	jsonData, err := json.Marshal(value)
	if err != nil {
		return err
	}

	_, err = c.db.Exec(`
		INSERT INTO cache (key, value, expires_at)
		VALUES (?, ?, ?)
		ON CONFLICT(key) DO UPDATE SET
			value = excluded.value,
			expires_at = excluded.expires_at
	`, key, string(jsonData), expiresAt)
	return err
}

// GetJSON retrieves a JSON value from the cache and unmarshals it into dest.
// Returns error if key doesn't exist, is expired, or JSON unmarshal fails.
func (c *Cache) GetJSON(key string, dest interface{}) error {
	var value string
	var expiresAt int64
	err := c.db.QueryRow("SELECT value, expires_at FROM cache WHERE key = ?", key).Scan(&value, &expiresAt)
	if err != nil {
		return err
	}

	// Check if expired
	if time.Now().Unix() >= expiresAt {
		return sql.ErrNoRows
	}

	return json.Unmarshal([]byte(value), dest)
}

// ExtendExpiration extends the expiration time of a cache entry by the specified duration.
// It extends from the current expiration time, not from now.
func (c *Cache) ExtendExpiration(key string, duration time.Duration) error {
	// Get current expiration time
	currentExpiresAt := c.GetExpiresAt(key)
	if currentExpiresAt == 0 {
		// Entry doesn't exist or is expired - can't extend
		return nil // Silently ignore (entry already invalid)
	}

	// Extend from current expiration time
	newExpiresAt := currentExpiresAt + int64(duration.Seconds())
	_, err := c.db.Exec(`
		UPDATE cache SET expires_at = ? WHERE key = ?
	`, newExpiresAt, key)
	return err
}
