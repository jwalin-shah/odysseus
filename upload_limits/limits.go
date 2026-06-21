// Package upload_limits provides route-local upload size caps and a bounded
// reader. The values are env-overridable so an operator can tune per-route
// caps without redeploying code. Reads are intentionally lazy: callers go
// through the Get* functions (or build a Limits snapshot via Resolve) so that
// tests can set env vars without init-time ordering surprises.
package upload_limits

import (
	"fmt"
	"os"
	"strconv"
	"strings"
)

// One-megabyte and one-kilobyte in bytes. Kept as named constants to make the
// formatting branches self-documenting.
const (
	bytesPerKB = 1024
	bytesPerMB = 1024 * 1024
)

// Default per-route caps. These are the fallback values when the matching
// ODYSSEUS_*_MAX_BYTES env var is unset or blank.
const (
	DefaultChatUploadMaxBytes             = 10 * 1024 * 1024
	DefaultGalleryUploadMaxBytes          = 100 * 1024 * 1024
	DefaultGalleryTransformUploadMaxBytes = 25 * 1024 * 1024
	DefaultMemoryImportMaxBytes           = 10 * 1024 * 1024
	DefaultPersonalUploadMaxBytes         = 25 * 1024 * 1024
	DefaultEmailComposeUploadMaxBytes     = 25 * 1024 * 1024
	DefaultSTTMaxAudioBytes               = 25 * 1024 * 1024
	DefaultICSMaxBytes                    = 10 * 1024 * 1024
)

// Environment variable names. They are exported so tests and operators can
// reference them by symbol rather than copying string literals.
const (
	EnvChatUploadMaxBytes             = "ODYSSEUS_CHAT_UPLOAD_MAX_BYTES"
	EnvGalleryUploadMaxBytes          = "ODYSSEUS_GALLERY_UPLOAD_MAX_BYTES"
	EnvGalleryTransformUploadMaxBytes = "ODYSSEUS_GALLERY_TRANSFORM_UPLOAD_MAX_BYTES"
	EnvMemoryImportMaxBytes           = "ODYSSEUS_MEMORY_IMPORT_MAX_BYTES"
	EnvPersonalUploadMaxBytes         = "ODYSSEUS_PERSONAL_UPLOAD_MAX_BYTES"
	EnvEmailComposeUploadMaxBytes     = "ODYSSEUS_EMAIL_COMPOSE_UPLOAD_MAX_BYTES"
	EnvSTTMaxAudioBytes               = "ODYSSEUS_STT_MAX_AUDIO_BYTES"
	EnvICSMaxBytes                    = "ODYSSEUS_ICS_MAX_BYTES"
)

// Limits is a snapshot of the effective per-route caps, computed once via
// Resolve. Useful when a caller wants to pass a single struct around (e.g.
// into HTTP handlers) rather than calling each Get* function on every
// request.
type Limits struct {
	Chat             int
	Gallery          int
	GalleryTransform int
	MemoryImport     int
	Personal         int
	EmailCompose     int
	STT              int
	ICS              int
}

// FormatByteLimit formats a byte count for human display. Divisible by 1MB
// renders as "X MB"; divisible by 1KB (but not 1MB) renders as "X KB";
// everything else renders as "X bytes". Zero and negative values both render
// in the bytes branch to match the Python implementation, which formats any
// non-multiple-of-1024 value (including 0) as raw bytes.
func FormatByteLimit(limit int) string {
	if limit > 0 && limit%bytesPerMB == 0 {
		return fmt.Sprintf("%d MB", limit/bytesPerMB)
	}
	if limit > 0 && limit%bytesPerKB == 0 {
		return fmt.Sprintf("%d KB", limit/bytesPerKB)
	}
	return fmt.Sprintf("%d bytes", limit)
}

// readByteLimitEnv reads a byte-limit env var. An unset or whitespace-only
// value returns the default. A non-integer value or a value below 1 returns an
// error. The error messages mirror the Python implementation so logs and
// downstream error handling can be shared between the two runtimes.
func readByteLimitEnv(name string, defaultValue int) (int, error) {
	raw, ok := os.LookupEnv(name)
	if !ok {
		return defaultValue, nil
	}
	if strings.TrimSpace(raw) == "" {
		return defaultValue, nil
	}
	limit, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer byte count: %w", name, err)
	}
	if limit < 1 {
		return 0, fmt.Errorf("%s must be greater than 0", name)
	}
	return limit, nil
}

// GetChatUploadMaxBytes returns the effective chat upload cap, consulting the
// matching env var on every call.
func GetChatUploadMaxBytes() int {
	v, err := readByteLimitEnv(EnvChatUploadMaxBytes, DefaultChatUploadMaxBytes)
	if err != nil {
		// Per Python semantics the env is validated at import time. We
		// surface the failure via panic-equivalent: any non-zero exit path
		// would change behavior, and a misconfigured server should not boot.
		// Callers that want graceful handling should use Resolve and check
		// the returned error.
		panic(err)
	}
	return v
}

// GetGalleryUploadMaxBytes returns the effective gallery upload cap.
func GetGalleryUploadMaxBytes() int {
	v, err := readByteLimitEnv(EnvGalleryUploadMaxBytes, DefaultGalleryUploadMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetGalleryTransformUploadMaxBytes returns the effective gallery transform
// upload cap.
func GetGalleryTransformUploadMaxBytes() int {
	v, err := readByteLimitEnv(EnvGalleryTransformUploadMaxBytes, DefaultGalleryTransformUploadMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetMemoryImportMaxBytes returns the effective memory-import cap.
func GetMemoryImportMaxBytes() int {
	v, err := readByteLimitEnv(EnvMemoryImportMaxBytes, DefaultMemoryImportMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetPersonalUploadMaxBytes returns the effective personal upload cap.
func GetPersonalUploadMaxBytes() int {
	v, err := readByteLimitEnv(EnvPersonalUploadMaxBytes, DefaultPersonalUploadMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetEmailComposeUploadMaxBytes returns the effective email-compose upload
// cap.
func GetEmailComposeUploadMaxBytes() int {
	v, err := readByteLimitEnv(EnvEmailComposeUploadMaxBytes, DefaultEmailComposeUploadMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetSTTMaxAudioBytes returns the effective STT audio cap.
func GetSTTMaxAudioBytes() int {
	v, err := readByteLimitEnv(EnvSTTMaxAudioBytes, DefaultSTTMaxAudioBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// GetICSMaxBytes returns the effective ICS file cap.
func GetICSMaxBytes() int {
	v, err := readByteLimitEnv(EnvICSMaxBytes, DefaultICSMaxBytes)
	if err != nil {
		panic(err)
	}
	return v
}

// Resolve reads every env-overridable cap and returns a populated Limits
// snapshot. The first invalid env var returns its error so callers (notably
// the CLI in cmd/upload_limits) can surface a clear message and exit non-zero
// instead of panicking.
func Resolve() (Limits, error) {
	l := Limits{}
	var err error
	if l.Chat, err = readByteLimitEnv(EnvChatUploadMaxBytes, DefaultChatUploadMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.Gallery, err = readByteLimitEnv(EnvGalleryUploadMaxBytes, DefaultGalleryUploadMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.GalleryTransform, err = readByteLimitEnv(EnvGalleryTransformUploadMaxBytes, DefaultGalleryTransformUploadMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.MemoryImport, err = readByteLimitEnv(EnvMemoryImportMaxBytes, DefaultMemoryImportMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.Personal, err = readByteLimitEnv(EnvPersonalUploadMaxBytes, DefaultPersonalUploadMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.EmailCompose, err = readByteLimitEnv(EnvEmailComposeUploadMaxBytes, DefaultEmailComposeUploadMaxBytes); err != nil {
		return Limits{}, err
	}
	if l.STT, err = readByteLimitEnv(EnvSTTMaxAudioBytes, DefaultSTTMaxAudioBytes); err != nil {
		return Limits{}, err
	}
	if l.ICS, err = readByteLimitEnv(EnvICSMaxBytes, DefaultICSMaxBytes); err != nil {
		return Limits{}, err
	}
	return l, nil
}
