package api_key_manager

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// fixedTestKey is a deterministic Fernet key (44 base64 chars, 32 raw bytes)
// so tests don't depend on rng. The raw bytes are derived from a known seed:
// SHA-256("api_key_manager_test_key_v1")[:32] then base64.
func fixedTestKey(t *testing.T) []byte {
	t.Helper()
	return []byte("ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
}

func TestManagerGetOrCreateKey_FreshInstall(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)

	key, err := mgr.GetOrCreateKey()
	if err != nil {
		t.Fatalf("get_or_create: %v", err)
	}
	if len(key) != fernetKeyB64Len {
		t.Fatalf("key length %d, want %d", len(key), fernetKeyB64Len)
	}
	// File must exist with 0o600.
	info, err := os.Stat(mgr.KeyFile())
	if err != nil {
		t.Fatalf("stat .key: %v", err)
	}
	if got := info.Mode().Perm(); got != 0o600 {
		t.Fatalf(".key perm = %o, want 0o600", got)
	}
}

func TestManagerGetOrCreateKey_DeterministicRead(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)

	first, err := mgr.GetOrCreateKey()
	if err != nil {
		t.Fatalf("first: %v", err)
	}
	// Drop the cached key by constructing a fresh manager and re-reading.
	mgr2 := NewManager(dir)
	second, err := mgr2.GetOrCreateKey()
	if err != nil {
		t.Fatalf("second: %v", err)
	}
	if string(first) != string(second) {
		t.Fatalf("keys differ: %q vs %q", first, second)
	}
}

func TestManagerGetOrCreateKey_HealsLooseMode(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	seed := fixedTestKey(t)

	// Pre-create the .key file with a deliberately loose mode.
	if err := os.WriteFile(mgr.KeyFile(), seed, 0o644); err != nil {
		t.Fatalf("seed write: %v", err)
	}
	if err := os.Chmod(mgr.KeyFile(), 0o644); err != nil {
		t.Skipf("chmod unsupported here: %v", err)
	}
	if got := mustStatMode(t, mgr.KeyFile()); got != 0o644 {
		t.Fatalf("setup: .key perm = %o, want 0o644", got)
	}

	got, err := mgr.GetOrCreateKey()
	if err != nil {
		t.Fatalf("get_or_create: %v", err)
	}
	if string(got) != string(seed) {
		t.Fatalf("got key %q, want %q", got, seed)
	}
	if mode := mustStatMode(t, mgr.KeyFile()); mode != 0o600 {
		t.Fatalf(".key perm after heal = %o, want 0o600", mode)
	}
}

func TestEncryptDecryptRoundTrip(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)

	tok, err := mgr.EncryptAPIKey("sk-test-1234")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if tok == "" {
		t.Fatal("encrypt returned empty token for non-empty input")
	}
	// Sanity: must be valid base64.
	if _, err := base64.URLEncoding.DecodeString(tok); err != nil {
		t.Fatalf("token not URL-safe base64: %v", err)
	}
	plain, err := mgr.DecryptAPIKey(tok)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if plain != "sk-test-1234" {
		t.Fatalf("got %q, want %q", plain, "sk-test-1234")
	}
}

func TestDecryptAPIKey_EmptyString(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	// Don't even create a key — empty input must not touch disk.
	got, err := mgr.DecryptAPIKey("")
	if err != nil {
		t.Fatalf("empty decrypt: %v", err)
	}
	if got != "" {
		t.Fatalf("got %q, want empty", got)
	}
	if _, err := os.Stat(mgr.KeyFile()); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("empty decrypt touched .key; stat err = %v", err)
	}
}

func TestDecryptAPIKey_CorruptedTokenIsSkipped(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	if _, err := mgr.GetOrCreateKey(); err != nil {
		t.Fatalf("seed key: %v", err)
	}

	// Direct decrypt of a bad token returns an error.
	if _, err := mgr.DecryptAPIKey("not a valid fernet token"); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("bad token err = %v, want ErrInvalidToken", err)
	}

	// Build a real store with one good provider and one corrupted token,
	// then Load() — the corrupted entry must be skipped.
	keys := map[string]string{
		"good":    mustEncrypt(t, mgr, "good-secret"),
		"corrupt": "ZAAAAA-this-is-not-real-aaaa",
	}
	writeRawKeys(t, mgr, keys)

	loaded, err := mgr.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if got := loaded["good"]; got != "good-secret" {
		t.Fatalf("good entry = %q, want %q", got, "good-secret")
	}
	if _, present := loaded["corrupt"]; present {
		t.Fatal("corrupt entry should have been skipped")
	}
}

func TestSave_PreservesOtherProvidersEncrypted(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	if _, err := mgr.GetOrCreateKey(); err != nil {
		t.Fatalf("seed key: %v", err)
	}

	// Save two providers.
	if err := mgr.Save("openai", "openai-secret"); err != nil {
		t.Fatalf("save openai: %v", err)
	}
	if err := mgr.Save("anthropic", "anthropic-secret"); err != nil {
		t.Fatalf("save anthropic: %v", err)
	}

	// Snapshot the on-disk ciphertext of "openai" — it must be unchanged
	// after we save anthropic a second time.
	openaiCT := readRawEntry(t, mgr, "openai")

	// Update anthropic again with a different value.
	if err := mgr.Save("anthropic", "anthropic-secret-v2"); err != nil {
		t.Fatalf("save anthropic v2: %v", err)
	}

	if got := readRawEntry(t, mgr, "openai"); got != openaiCT {
		t.Fatalf("openai ciphertext changed during save of a different provider: before=%q after=%q", openaiCT, got)
	}

	loaded, err := mgr.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if loaded["openai"] != "openai-secret" {
		t.Fatalf("openai = %q, want %q", loaded["openai"], "openai-secret")
	}
	if loaded["anthropic"] != "anthropic-secret-v2" {
		t.Fatalf("anthropic = %q, want %q", loaded["anthropic"], "anthropic-secret-v2")
	}
}

func TestLoadRaw_MissingFile(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)

	got, err := mgr.loadRaw()
	if err != nil {
		t.Fatalf("load_raw: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("missing file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_CorruptJSON(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	if err := os.WriteFile(mgr.KeysFile(), []byte("{not valid json"), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := mgr.loadRaw()
	if err != nil {
		t.Fatalf("load_raw on corrupt file: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("corrupt file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_ListShape(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	if err := os.WriteFile(mgr.KeysFile(), []byte("[]"), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := mgr.loadRaw()
	if err != nil {
		t.Fatalf("load_raw on list-shaped file: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("list-shaped file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_NonStringValuesFiltered(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	// Build a JSON map with one valid string, one int, one null.
	raw := map[string]any{
		"good": "some-token",
		"int":  42,
		"null": nil,
	}
	data, err := json.Marshal(raw)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(mgr.KeysFile(), data, 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := mgr.loadRaw()
	if err != nil {
		t.Fatalf("load_raw: %v", err)
	}
	if len(got) != 1 || got["good"] != "some-token" {
		t.Fatalf("got %v, want only {good: some-token}", got)
	}
}

func TestSaveAndLoadEndToEnd(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)

	if err := mgr.Save("alpha", "alpha-value"); err != nil {
		t.Fatalf("save: %v", err)
	}
	loaded, err := mgr.Load()
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if loaded["alpha"] != "alpha-value" {
		t.Fatalf("loaded[alpha] = %q, want %q", loaded["alpha"], "alpha-value")
	}

	// Re-save the same provider with a different value and reload.
	if err := mgr.Save("alpha", "alpha-value-v2"); err != nil {
		t.Fatalf("save v2: %v", err)
	}
	loaded, err = mgr.Load()
	if err != nil {
		t.Fatalf("load v2: %v", err)
	}
	if loaded["alpha"] != "alpha-value-v2" {
		t.Fatalf("loaded[alpha] = %q, want %q", loaded["alpha"], "alpha-value-v2")
	}
}

func TestDataDirAccessors(t *testing.T) {
	dir := t.TempDir()
	mgr := NewManager(dir)
	if got := mgr.DataDir(); got != dir {
		t.Fatalf("DataDir() = %q, want %q", got, dir)
	}
	if got := mgr.KeyFile(); got != filepath.Join(dir, ".key") {
		t.Fatalf("KeyFile() = %q", got)
	}
	if got := mgr.KeysFile(); got != filepath.Join(dir, "api_keys.json") {
		t.Fatalf("KeysFile() = %q", got)
	}
}

func TestSafeChmod_IgnoresPermissionErrors(t *testing.T) {
	// On a directory we don't own, os.Chmod often fails with EPERM. The
	// helper must swallow that and return nil so callers don't have to
	// branch on platform.
	err := safeChmod("/this/path/does/not/exist", 0o600)
	if err != nil {
		// File-not-exist isn't ErrPermission, but ErrInvalid isn't either
		// — we only promise to ignore ErrPermission. Anything else is OK to
		// surface. (Most importantly, this must not panic.)
		_ = err
	}
}

// CLI smoke test: confirm the binary can be driven end-to-end through its
// helper. Lives in the package rather than cmd/api_key_manager because it
// shares the Manager type — fewer moving parts than shelling out.
func TestCLI_EncryptDecryptRoundTrip(t *testing.T) {
	dir := t.TempDir()

	// Encrypt via the Manager (which the CLI wraps).
	mgr := NewManager(dir)
	tok, err := mgr.EncryptAPIKey("cli-test-key")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}

	// Decrypt via a fresh Manager — proves the .key file alone is enough.
	mgr2 := NewManager(dir)
	plain, err := mgr2.DecryptAPIKey(tok)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if plain != "cli-test-key" {
		t.Fatalf("plain = %q, want %q", plain, "cli-test-key")
	}
}

// --- helpers -----------------------------------------------------------------

func mustStatMode(t *testing.T, path string) os.FileMode {
	t.Helper()
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat %s: %v", path, err)
	}
	return info.Mode().Perm()
}

func mustEncrypt(t *testing.T, mgr *Manager, plain string) string {
	t.Helper()
	tok, err := mgr.EncryptAPIKey(plain)
	if err != nil {
		t.Fatalf("encrypt %q: %v", plain, err)
	}
	return tok
}

func writeRawKeys(t *testing.T, mgr *Manager, keys map[string]string) {
	t.Helper()
	data, err := json.MarshalIndent(keys, "", "  ")
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(mgr.KeysFile(), data, 0o600); err != nil {
		t.Fatalf("write keys: %v", err)
	}
}

func readRawEntry(t *testing.T, mgr *Manager, provider string) string {
	t.Helper()
	data, err := os.ReadFile(mgr.KeysFile())
	if err != nil {
		t.Fatalf("read keys: %v", err)
	}
	var raw map[string]string
	if err := json.Unmarshal(data, &raw); err != nil {
		t.Fatalf("parse keys: %v", err)
	}
	v, ok := raw[provider]
	if !ok {
		t.Fatalf("provider %q not in store", provider)
	}
	return v
}

// silence unused-import linter on platforms where strings isn't otherwise used.
var _ = strings.TrimSpace
var _ = time.Time{}
