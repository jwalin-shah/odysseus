package apikeymgr

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestManagerGetOrCreateKey_FreshInstall(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)

	key, err := mgr.GetOrCreateKey()
	if err != nil {
		t.Fatalf("get_or_create: %v", err)
	}
	if len(key) != aesKeyLen {
		t.Fatalf("key length %d, want %d", len(key), aesKeyLen)
	}
	info, err := os.Stat(mgr.KeyFile())
	if err != nil {
		t.Fatalf("stat .key: %v", err)
	}
	if runtime.GOOS != "windows" {
		if got := info.Mode().Perm(); got != keyFilePerm {
			t.Fatalf(".key perm = %o, want %o", got, keyFilePerm)
		}
	}
}

func TestManagerGetOrCreateKey_DeterministicRead(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)

	first, err := mgr.GetOrCreateKey()
	if err != nil {
		t.Fatalf("first: %v", err)
	}
	mgr2 := New(dir)
	second, err := mgr2.GetOrCreateKey()
	if err != nil {
		t.Fatalf("second: %v", err)
	}
	if string(first) != string(second) {
		t.Fatalf("keys differ: %q vs %q", first, second)
	}
}

func TestManagerGetOrCreateKey_HealsLooseMode(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("chmod is a no-op on windows")
	}
	dir := t.TempDir()
	mgr := New(dir)
	seed := make([]byte, aesKeyLen)
	for i := range seed {
		seed[i] = byte(i)
	}

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
	if mode := mustStatMode(t, mgr.KeyFile()); mode != keyFilePerm {
		t.Fatalf(".key perm after heal = %o, want %o", mode, keyFilePerm)
	}
}

func TestManagerGetOrCreateKey_HealsIsIdempotent(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("chmod is a no-op on windows")
	}
	dir := t.TempDir()
	mgr := New(dir)
	if _, err := mgr.GetOrCreateKey(); err != nil {
		t.Fatalf("first: %v", err)
	}
	modeBefore := mustStatMode(t, mgr.KeyFile())
	mgr2 := New(dir)
	if _, err := mgr2.GetOrCreateKey(); err != nil {
		t.Fatalf("second: %v", err)
	}
	modeAfter := mustStatMode(t, mgr2.KeyFile())
	if modeBefore != modeAfter {
		t.Fatalf("mode changed on idempotent read: %o -> %o", modeBefore, modeAfter)
	}
	if modeAfter != keyFilePerm {
		t.Fatalf("mode = %o, want %o", modeAfter, keyFilePerm)
	}
}

func TestEncryptDecryptRoundTrip(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)

	tok, err := mgr.EncryptAPIKey("sk-test-1234")
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if tok == "" {
		t.Fatal("encrypt returned empty token for non-empty input")
	}
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

func TestEncryptAPIKey_EmptyString(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)
	got, err := mgr.EncryptAPIKey("")
	if err != nil {
		t.Fatalf("empty encrypt: %v", err)
	}
	if got != "" {
		t.Fatalf("got %q, want empty", got)
	}
	if _, err := os.Stat(mgr.KeyFile()); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("empty encrypt touched .key; stat err = %v", err)
	}
}

func TestDecryptAPIKey_EmptyString(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)
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
	mgr := New(dir)
	if _, err := mgr.GetOrCreateKey(); err != nil {
		t.Fatalf("seed key: %v", err)
	}

	// Direct decrypt of a bad token returns ErrInvalidToken.
	if _, err := mgr.DecryptAPIKey("not a valid token"); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("bad token err = %v, want ErrInvalidToken", err)
	}

	keys := map[string]string{
		"good":    mustEncrypt(t, mgr, "good-secret"),
		"corrupt": "ZAAAAAAAAAA-not-a-valid-token",
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
	mgr := New(dir)
	if _, err := mgr.GetOrCreateKey(); err != nil {
		t.Fatalf("seed key: %v", err)
	}

	if err := mgr.Save("openai", "openai-secret"); err != nil {
		t.Fatalf("save openai: %v", err)
	}
	if err := mgr.Save("anthropic", "anthropic-secret"); err != nil {
		t.Fatalf("save anthropic: %v", err)
	}

	openaiCT := readRawEntry(t, mgr, "openai")

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
	mgr := New(dir)

	got, err := mgr.LoadRaw()
	if err != nil {
		t.Fatalf("load_raw: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("missing file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_CorruptJSON(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)
	if err := os.WriteFile(mgr.KeysFile(), []byte("{not valid json"), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := mgr.LoadRaw()
	if err != nil {
		t.Fatalf("load_raw on corrupt file: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("corrupt file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_ListShape(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)
	if err := os.WriteFile(mgr.KeysFile(), []byte("[]"), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}

	got, err := mgr.LoadRaw()
	if err != nil {
		t.Fatalf("load_raw on list-shaped file: %v", err)
	}
	if len(got) != 0 {
		t.Fatalf("list-shaped file returned %d entries, want 0", len(got))
	}
}

func TestLoadRaw_NonStringValuesFiltered(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)
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

	got, err := mgr.LoadRaw()
	if err != nil {
		t.Fatalf("load_raw: %v", err)
	}
	if len(got) != 1 || got["good"] != "some-token" {
		t.Fatalf("got %v, want only {good: some-token}", got)
	}
}

func TestSaveAndLoadEndToEnd(t *testing.T) {
	dir := t.TempDir()
	mgr := New(dir)

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
	mgr := New(dir)
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

func TestSafeChmod_WindowsIsNoOp(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("windows-specific test")
	}
	if err := safeChmod("/nonexistent/path", 0o600); err != nil {
		t.Fatalf("safeChmod on windows should be no-op, got %v", err)
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
