package reliability

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/aristath/sentinel/internal/version"
	"github.com/rs/zerolog"
)

// R2BackupService manages cloud backups to Cloudflare R2
type R2BackupService struct {
	r2Client      *R2Client
	backupService *BackupService
	dataDir       string
	log           zerolog.Logger
}

// BackupMetadata contains metadata about a backup
type BackupMetadata struct {
	Timestamp       time.Time          `json:"timestamp"`
	Version         string             `json:"version"`
	SentinelVersion string             `json:"sentinel_version"`
	Databases       []DatabaseMetadata `json:"databases"`
}

// DatabaseMetadata contains metadata about a single database in the backup
type DatabaseMetadata struct {
	Name      string `json:"name"`
	Filename  string `json:"filename"`
	SizeBytes int64  `json:"size_bytes"`
	Checksum  string `json:"checksum"`
}

// BackupInfo represents information about a backup stored in R2
type BackupInfo struct {
	Filename  string    `json:"filename"`
	Timestamp time.Time `json:"timestamp"`
	SizeBytes int64     `json:"size_bytes"`
	AgeHours  int64     `json:"age_hours"`
}

// NewR2BackupService creates a new R2 backup service
func NewR2BackupService(
	r2Client *R2Client,
	backupService *BackupService,
	dataDir string,
	log zerolog.Logger,
) *R2BackupService {
	return &R2BackupService{
		r2Client:      r2Client,
		backupService: backupService,
		dataDir:       dataDir,
		log:           log.With().Str("service", "r2_backup").Logger(),
	}
}

// GetR2Client returns the R2 client (for use by handlers)
func (s *R2BackupService) GetR2Client() *R2Client {
	return s.r2Client
}

// CreateAndUploadBackup creates a backup archive and uploads it to R2
func (s *R2BackupService) CreateAndUploadBackup(ctx context.Context) error {
	s.log.Info().Msg("Starting R2 backup")
	startTime := time.Now()

	// Create staging directory
	stagingDir := filepath.Join(s.dataDir, "r2-staging")
	if err := os.MkdirAll(stagingDir, 0755); err != nil {
		return fmt.Errorf("failed to create staging directory: %w", err)
	}
	defer os.RemoveAll(stagingDir) // Clean up on exit

	// Get database names dynamically from BackupService (includes cache, excludes client_data)
	dbNames := s.backupService.GetDatabaseNames(true, false)
	metadata := BackupMetadata{
		Timestamp:       time.Now().UTC(),
		Version:         "1.0.0",
		SentinelVersion: version.Version,
		Databases:       make([]DatabaseMetadata, 0, len(dbNames)),
	}

	for _, dbName := range dbNames {
		dbPath := filepath.Join(stagingDir, dbName+".db")

		s.log.Debug().Str("database", dbName).Msg("Backing up database")

		if err := s.backupService.BackupDatabase(dbName, dbPath); err != nil {
			s.log.Error().Err(err).Str("database", dbName).Msg("Failed to backup database")
			return fmt.Errorf("failed to backup %s: %w", dbName, err)
		}

		// Get file info and checksum
		info, err := os.Stat(dbPath)
		if err != nil {
			return fmt.Errorf("failed to stat %s backup: %w", dbName, err)
		}

		checksum, err := s.calculateChecksum(dbPath)
		if err != nil {
			return fmt.Errorf("failed to calculate checksum for %s: %w", dbName, err)
		}

		metadata.Databases = append(metadata.Databases, DatabaseMetadata{
			Name:      dbName,
			Filename:  dbName + ".db",
			SizeBytes: info.Size(),
			Checksum:  checksum,
		})
	}

	// Write metadata file
	metadataPath := filepath.Join(stagingDir, "backup-metadata.json")
	if err := s.writeMetadata(metadataPath, metadata); err != nil {
		return fmt.Errorf("failed to write metadata: %w", err)
	}

	// Create tar.gz archive
	timestamp := time.Now().Format("2006-01-02-150405")
	archiveName := fmt.Sprintf("sentinel-backup-%s.tar.gz", timestamp)
	archivePath := filepath.Join(stagingDir, archiveName)

	if err := s.createArchive(archivePath, stagingDir, append(dbNames, "backup-metadata")); err != nil {
		return fmt.Errorf("failed to create archive: %w", err)
	}

	// Get archive size
	archiveInfo, err := os.Stat(archivePath)
	if err != nil {
		return fmt.Errorf("failed to stat archive: %w", err)
	}

	// Upload to R2
	archiveFile, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf("failed to open archive: %w", err)
	}
	defer archiveFile.Close()

	if err := s.r2Client.Upload(ctx, archiveName, archiveFile, archiveInfo.Size()); err != nil {
		return fmt.Errorf("failed to upload to r2: %w", err)
	}

	duration := time.Since(startTime)
	s.log.Info().
		Dur("duration_ms", duration).
		Str("archive", archiveName).
		Int64("size_mb", archiveInfo.Size()/1024/1024).
		Msg("R2 backup completed successfully")

	return nil
}

// ListBackups lists all backups stored in R2
func (s *R2BackupService) ListBackups(ctx context.Context) ([]BackupInfo, error) {
	objects, err := s.r2Client.List(ctx, "sentinel-backup-")
	if err != nil {
		return nil, fmt.Errorf("failed to list r2 backups: %w", err)
	}

	backups := make([]BackupInfo, 0, len(objects))
	now := time.Now()

	for _, obj := range objects {
		if obj.Key == nil {
			continue
		}

		// Parse timestamp from filename: sentinel-backup-2026-01-08-143022.tar.gz
		filename := *obj.Key
		if !strings.HasPrefix(filename, "sentinel-backup-") || !strings.HasSuffix(filename, ".tar.gz") {
			continue
		}

		timestampStr := strings.TrimPrefix(filename, "sentinel-backup-")
		timestampStr = strings.TrimSuffix(timestampStr, ".tar.gz")

		timestamp, err := time.Parse("2006-01-02-150405", timestampStr)
		if err != nil {
			s.log.Warn().Str("filename", filename).Msg("Failed to parse timestamp from filename")
			continue
		}

		var sizeBytes int64
		if obj.Size != nil {
			sizeBytes = *obj.Size
		}

		ageHours := int64(now.Sub(timestamp).Hours())

		backups = append(backups, BackupInfo{
			Filename:  filename,
			Timestamp: timestamp,
			SizeBytes: sizeBytes,
			AgeHours:  ageHours,
		})
	}

	// Sort by timestamp (newest first)
	sort.Slice(backups, func(i, j int) bool {
		return backups[i].Timestamp.After(backups[j].Timestamp)
	})

	return backups, nil
}

// RotateOldBackups deletes backups older than the retention period
// Keeps a minimum of 3 backups regardless of age
func (s *R2BackupService) RotateOldBackups(ctx context.Context, retentionDays int) error {
	s.log.Info().Int("retention_days", retentionDays).Msg("Starting R2 backup rotation")

	backups, err := s.ListBackups(ctx)
	if err != nil {
		return fmt.Errorf("failed to list backups: %w", err)
	}

	// Keep at least 3 backups
	const minBackupsToKeep = 3
	if len(backups) <= minBackupsToKeep {
		s.log.Info().Int("count", len(backups)).Msg("Too few backups to rotate")
		return nil
	}

	// Determine cutoff time (0 = keep forever)
	var cutoffTime time.Time
	if retentionDays > 0 {
		cutoffTime = time.Now().AddDate(0, 0, -retentionDays)
	}

	deletedCount := 0
	for i, backup := range backups {
		// Always keep the first minBackupsToKeep (newest)
		if i < minBackupsToKeep {
			continue
		}

		// If retention is 0, keep everything beyond minimum
		if retentionDays == 0 {
			continue
		}

		// Delete if older than retention period
		if backup.Timestamp.Before(cutoffTime) {
			if err := s.r2Client.Delete(ctx, backup.Filename); err != nil {
				s.log.Error().
					Err(err).
					Str("filename", backup.Filename).
					Msg("Failed to delete old backup")
				continue
			}

			s.log.Info().
				Str("filename", backup.Filename).
				Time("timestamp", backup.Timestamp).
				Msg("Deleted old backup")

			deletedCount++
		}
	}

	s.log.Info().
		Int("deleted", deletedCount).
		Int("remaining", len(backups)-deletedCount).
		Msg("R2 backup rotation completed")

	return nil
}

// calculateChecksum calculates SHA256 checksum of a file
func (s *R2BackupService) calculateChecksum(filePath string) (string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}

	return fmt.Sprintf("sha256:%x", hash.Sum(nil)), nil
}

// writeMetadata writes backup metadata to a JSON file
func (s *R2BackupService) writeMetadata(path string, metadata BackupMetadata) error {
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	return encoder.Encode(metadata)
}

// createArchive creates a tar.gz archive of the specified files
func (s *R2BackupService) createArchive(archivePath, sourceDir string, fileBasenames []string) error {
	// Create archive file
	archiveFile, err := os.Create(archivePath)
	if err != nil {
		return fmt.Errorf("failed to create archive file: %w", err)
	}
	defer archiveFile.Close()

	// Create gzip writer
	gzipWriter := gzip.NewWriter(archiveFile)
	defer gzipWriter.Close()

	// Create tar writer
	tarWriter := tar.NewWriter(gzipWriter)
	defer tarWriter.Close()

	// Add each file to archive
	for _, basename := range fileBasenames {
		var filename string
		if basename == "backup-metadata" {
			filename = "backup-metadata.json"
		} else {
			filename = basename + ".db"
		}

		filePath := filepath.Join(sourceDir, filename)

		if err := s.addFileToArchive(tarWriter, filePath, filename); err != nil {
			return fmt.Errorf("failed to add %s to archive: %w", filename, err)
		}
	}

	return nil
}

// addFileToArchive adds a single file to a tar archive
func (s *R2BackupService) addFileToArchive(tarWriter *tar.Writer, filePath, nameInArchive string) error {
	file, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return err
	}

	header := &tar.Header{
		Name:    nameInArchive,
		Size:    info.Size(),
		Mode:    int64(info.Mode()),
		ModTime: info.ModTime(),
	}

	if err := tarWriter.WriteHeader(header); err != nil {
		return err
	}

	if _, err := io.Copy(tarWriter, file); err != nil {
		return err
	}

	return nil
}
