package server

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/rs/zerolog"

	"github.com/aristath/arduino-trader/internal/config"
	"github.com/aristath/arduino-trader/internal/database"
)

// Config holds server configuration
type Config struct {
	Port    int
	Log     zerolog.Logger
	DB      *database.DB
	Config  *config.Config
	DevMode bool
}

// Server represents the HTTP server
type Server struct {
	router *chi.Mux
	server *http.Server
	log    zerolog.Logger
	db     *database.DB
	cfg    *config.Config
}

// New creates a new HTTP server
func New(cfg Config) *Server {
	s := &Server{
		router: chi.NewRouter(),
		log:    cfg.Log.With().Str("component", "server").Logger(),
		db:     cfg.DB,
		cfg:    cfg.Config,
	}

	s.setupMiddleware(cfg.DevMode)
	s.setupRoutes()

	s.server = &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.Port),
		Handler:      s.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return s
}

// setupMiddleware configures middleware
func (s *Server) setupMiddleware(devMode bool) {
	// Recovery from panics
	s.router.Use(middleware.Recoverer)

	// Request ID
	s.router.Use(middleware.RequestID)

	// Real IP
	s.router.Use(middleware.RealIP)

	// Logging
	s.router.Use(s.loggingMiddleware)

	// Timeout
	s.router.Use(middleware.Timeout(60 * time.Second))

	// CORS
	s.router.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type"},
		ExposedHeaders:   []string{"Link"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Compress responses
	if !devMode {
		s.router.Use(middleware.Compress(5))
	}
}

// setupRoutes configures all routes
func (s *Server) setupRoutes() {
	// Health check
	s.router.Get("/health", s.handleHealth)

	// API routes
	s.router.Route("/api", func(r chi.Router) {
		// System
		r.Route("/system", func(r chi.Router) {
			r.Get("/status", s.handleSystemStatus)
		})

		// TODO: Add more routes as modules are migrated
		// r.Route("/portfolio", func(r chi.Router) { ... })
		// r.Route("/trading", func(r chi.Router) { ... })
		// r.Route("/planning", func(r chi.Router) { ... })
	})

	// Serve static files (for dashboard)
	// s.router.Handle("/static/*", http.StripPrefix("/static/", http.FileServer(http.Dir("./static"))))
}

// Start starts the HTTP server
func (s *Server) Start() error {
	s.log.Info().Int("port", s.cfg.Port).Msg("Starting HTTP server")
	return s.server.ListenAndServe()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown(ctx context.Context) error {
	s.log.Info().Msg("Shutting down HTTP server")
	return s.server.Shutdown(ctx)
}

// loggingMiddleware logs HTTP requests
func (s *Server) loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
		next.ServeHTTP(ww, r)

		s.log.Info().
			Str("method", r.Method).
			Str("path", r.URL.Path).
			Int("status", ww.Status()).
			Int("bytes", ww.BytesWritten()).
			Dur("duration_ms", time.Since(start)).
			Str("request_id", middleware.GetReqID(r.Context())).
			Msg("HTTP request")
	})
}
