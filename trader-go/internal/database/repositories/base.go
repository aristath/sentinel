package repositories

import (
	"database/sql"
	"github.com/rs/zerolog"
)

// BaseRepository provides common database operations
type BaseRepository struct {
	db  *sql.DB
	log zerolog.Logger
}

// NewBase creates a new base repository
func NewBase(db *sql.DB, log zerolog.Logger) *BaseRepository {
	return &BaseRepository{
		db:  db,
		log: log,
	}
}

// DB returns the database connection
func (r *BaseRepository) DB() *sql.DB {
	return r.db
}

// Example repository pattern:
//
// type SecurityRepository struct {
//     *BaseRepository
// }
//
// func NewSecurityRepository(db *sql.DB, log zerolog.Logger) *SecurityRepository {
//     return &SecurityRepository{
//         BaseRepository: NewBase(db, log.With().Str("repo", "security").Logger()),
//     }
// }
//
// func (r *SecurityRepository) GetBySymbol(symbol string) (*domain.Security, error) {
//     // Implementation
// }
