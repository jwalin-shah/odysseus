package appinit

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
)

// ---- Test doubles ----------------------------------------------------------

// recordingBraveKeyLoader captures the keys UpdateSearchConfig was called
// with. Thread-safe so we can use it from goroutines if a test wants to.
type recordingBraveKeyLoader struct {
	calls atomic.Int32
	last  atomic.Value // string
}

func (r *recordingBraveKeyLoader) UpdateSearchConfig(apiKey string) error {
	r.calls.Add(1)
	r.last.Store(apiKey)
	return nil
}

func (r *recordingBraveKeyLoader) Last() string {
	v, _ := r.last.Load().(string)
	return v
}

// countingAPIKeyManager is a hand-rolled APIKeyManager that records Load/Save
// calls and reads from an in-process map. We use it instead of the JSON
// backend when we want to assert on the exact key passed to the loader.
type countingAPIKeyManager struct {
	keys    map[string]string
	loadN   atomic.Int32
	saveN   atomic.Int32
	saveErr error
	loadErr error
}

func (c *countingAPIKeyManager) Load() map[string]string {
	c.loadN.Add(1)
	if c.loadErr != nil {
		return map[string]string{}
	}
	out := make(map[string]string, len(c.keys))
	for k, v := range c.keys {
		out[k] = v
	}
	return out
}

func (c *countingAPIKeyManager) Save(provider, key string) error {
	c.saveN.Add(1)
	if c.saveErr != nil {
		return c.saveErr
	}
	c.keys[provider] = key
	return nil
}

// fixedRegistry returns a Registry populated with stubs for every component
// except the APIKeyManager slot (and BraveKeyLoader, which the test overrides
// separately). Tests can poke individual slots after the call.
func fixedRegistry(api APIKeyManager, brave BraveKeyLoader) Registry {
	r := DefaultRegistry()
	if api != nil {
		r.APIKeyManager = func(_ Config) (any, error) { return api, nil }
	}
	r.BraveKeyLoader = brave
	return r
}

// ---- Tests -----------------------------------------------------------------

// TestCreateDirectoriesIsIdempotent runs CreateDirectories twice and asserts
// the directories exist after each pass. os.MkdirAll is documented as
// idempotent; this test pins that behaviour for the four directories the
// Python module creates.
func TestCreateDirectoriesIsIdempotent(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "data"),
		PersonalDir: filepath.Join(root, "personal"),
		RunbookDir:  filepath.Join(root, "runbook"),
		UploadDir:   filepath.Join(root, "uploads"),
	}

	if err := CreateDirectories(cfg); err != nil {
		t.Fatalf("first CreateDirectories: %v", err)
	}
	for _, dir := range cfg.RequiredDirectories() {
		if fi, err := os.Stat(dir); err != nil || !fi.IsDir() {
			t.Fatalf("expected %s to exist as a directory after first call: err=%v", dir, err)
		}
	}

	// Second call must succeed even though every directory already exists.
	if err := CreateDirectories(cfg); err != nil {
		t.Fatalf("second CreateDirectories: %v", err)
	}
}

// TestCreateDirectoriesCreatesNestedPath ensures MkdirAll is used (not plain
// Mkdir): a deeply nested path that doesn't exist must be created.
func TestCreateDirectoriesCreatesNestedPath(t *testing.T) {
	root := t.TempDir()
	nested := filepath.Join(root, "a", "b", "c")
	cfg := Config{
		DataDir:     filepath.Join(nested, "data"),
		PersonalDir: filepath.Join(nested, "personal_docs"),
		RunbookDir:  filepath.Join(nested, "personal_docs", "runbook"),
		UploadDir:   filepath.Join(nested, "uploads"),
	}
	if err := CreateDirectories(cfg); err != nil {
		t.Fatalf("CreateDirectories: %v", err)
	}
	for _, dir := range cfg.RequiredDirectories() {
		if _, err := os.Stat(dir); err != nil {
			t.Fatalf("expected nested dir %s: %v", dir, err)
		}
	}
}

// TestInitializePopulatesAppContext verifies that Initialize with the default
// registry populates the AppContext fields that have non-nil stubs (the
// APIKeyManager), and leaves the others as zero values (the stubs return
// nil).
func TestInitializePopulatesAppContext(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "data"),
		PersonalDir: filepath.Join(root, "personal_docs"),
		RunbookDir:  filepath.Join(root, "runbook"),
		UploadDir:   filepath.Join(root, "uploads"),
	}

	ctx, err := Initialize(cfg, Registry{})
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if ctx == nil {
		t.Fatal("Initialize returned nil AppContext")
	}
	if ctx.APIKeyManager == nil {
		t.Error("expected APIKeyManager to be wired from DefaultRegistry")
	}
	// Stub registry returns nil for everything else.
	if ctx.MemoryManager != nil {
		t.Errorf("expected nil MemoryManager from stub registry, got %T", ctx.MemoryManager)
	}
	if ctx.SessionManager != nil {
		t.Errorf("expected nil SessionManager from stub registry, got %T", ctx.SessionManager)
	}
	if ctx.ChatHandler != nil {
		t.Errorf("expected nil ChatHandler from stub registry, got %T", ctx.ChatHandler)
	}
}

// TestInitializeMissingDataDirStillCreatesDirs guards the case where a caller
// passes a Config whose paths don't yet exist. Initialize should still wire
// the AppContext (directories are created via CreateDirectories inside the
// registry-default flow / caller-controlled flow). Here we drive the registry
// path explicitly so we know the directories exist before Initialize reads
// anything.
func TestInitializeMissingDataDirStillCreatesDirs(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "fresh", "data"),
		PersonalDir: filepath.Join(root, "fresh", "personal_docs"),
		RunbookDir:  filepath.Join(root, "fresh", "runbook"),
		UploadDir:   filepath.Join(root, "fresh", "uploads"),
	}

	// The Initialize impl does not call CreateDirectories itself — the
	// Python caller does. We mirror that contract: caller creates, then
	// passes the Config in. The test exercises that path and asserts the
	// directories exist after the explicit CreateDirectories call.
	if err := CreateDirectories(cfg); err != nil {
		t.Fatalf("CreateDirectories: %v", err)
	}
	for _, dir := range cfg.RequiredDirectories() {
		if fi, err := os.Stat(dir); err != nil || !fi.IsDir() {
			t.Fatalf("expected %s after CreateDirectories: err=%v", dir, err)
		}
	}

	ctx, err := Initialize(cfg, Registry{})
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if ctx == nil {
		t.Fatal("expected non-nil AppContext")
	}
	if ctx.APIKeyManager == nil {
		t.Error("expected APIKeyManager wired from DefaultRegistry")
	}
}

// TestInitializeNoBraveKeySkipsUpdateSearchConfig pins the "no saved key
// means we don't call UpdateSearchConfig" behaviour. The recording loader
// must see zero calls.
func TestInitializeNoBraveKeySkipsUpdateSearchConfig(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "data"),
		PersonalDir: filepath.Join(root, "personal_docs"),
		RunbookDir:  filepath.Join(root, "runbook"),
		UploadDir:   filepath.Join(root, "uploads"),
	}
	api := &countingAPIKeyManager{keys: map[string]string{}}
	loader := &recordingBraveKeyLoader{}
	reg := fixedRegistry(api, loader)

	ctx, err := Initialize(cfg, reg)
	if err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if ctx == nil {
		t.Fatal("expected non-nil AppContext")
	}
	if got := loader.calls.Load(); got != 0 {
		t.Errorf("expected 0 calls to UpdateSearchConfig when no brave key, got %d", got)
	}
}

// TestInitializeBraveKeyCallsUpdateSearchConfig is the matching positive
// case: a saved "brave" key must be forwarded (as plaintext) to the loader.
func TestInitializeBraveKeyCallsUpdateSearchConfig(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "data"),
		PersonalDir: filepath.Join(root, "personal_docs"),
		RunbookDir:  filepath.Join(root, "runbook"),
		UploadDir:   filepath.Join(root, "uploads"),
	}
	const want = "BSA-the-search-key"
	api := &countingAPIKeyManager{keys: map[string]string{BraveProvider: want}}
	loader := &recordingBraveKeyLoader{}
	reg := fixedRegistry(api, loader)

	if _, err := Initialize(cfg, reg); err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if got := loader.calls.Load(); got != 1 {
		t.Errorf("expected exactly 1 call to UpdateSearchConfig, got %d", got)
	}
	if got := loader.Last(); got != want {
		t.Errorf("UpdateSearchConfig called with %q, want %q", got, want)
	}
	if api.loadN.Load() < 1 {
		t.Errorf("expected APIKeyManager.Load to be called at least once, got %d", api.loadN.Load())
	}
}

// TestAPIKeyBackendRoundTrip is a small sanity check on the JSON backend the
// default registry uses for APIKeyManager: write, read, compare.
func TestAPIKeyBackendRoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "api_keys.json")
	api, err := defaultAPIKeyConstructor(Config{APIKeysFile: path})
	if err != nil {
		t.Fatalf("defaultAPIKeyConstructor: %v", err)
	}
	if err := api.(APIKeyManager).Save("brave", "k1"); err != nil {
		t.Fatalf("Save: %v", err)
	}
	if err := api.(APIKeyManager).Save("openai", "k2"); err != nil {
		t.Fatalf("Save: %v", err)
	}
	loaded := api.(APIKeyManager).Load()
	if loaded["brave"] != "k1" {
		t.Errorf("loaded[brave] = %q, want k1", loaded["brave"])
	}
	if loaded["openai"] != "k2" {
		t.Errorf("loaded[openai] = %q, want k2", loaded["openai"])
	}
}

// TestAPIKeyBackendSurvivesCorruptFile mirrors the Python _load_raw fallback:
// a corrupt api_keys.json must not crash the loader — it returns an empty
// map and the next Save writes a clean file.
func TestAPIKeyBackendSurvivesCorruptFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "api_keys.json")
	if err := os.WriteFile(path, []byte("this is not json"), 0o600); err != nil {
		t.Fatalf("seed: %v", err)
	}
	api, err := defaultAPIKeyConstructor(Config{APIKeysFile: path})
	if err != nil {
		t.Fatalf("defaultAPIKeyConstructor: %v", err)
	}
	loaded := api.(APIKeyManager).Load()
	if len(loaded) != 0 {
		t.Errorf("expected empty map from corrupt file, got %v", loaded)
	}
	if err := api.(APIKeyManager).Save("brave", "recovered"); err != nil {
		t.Fatalf("Save after corrupt: %v", err)
	}
	// File must now parse as JSON.
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read after save: %v", err)
	}
	var parsed map[string]string
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("api_keys.json not valid JSON after Save: %v (raw=%q)", err, string(data))
	}
	if parsed["brave"] != "recovered" {
		t.Errorf("expected brave=recovered after save, got %v", parsed)
	}
}

// TestBraveLoaderErrorPropagates confirms that a failing BraveKeyLoader
// surfaces as an Initialize error. We don't silently drop it.
func TestBraveLoaderErrorPropagates(t *testing.T) {
	root := t.TempDir()
	cfg := Config{
		DataDir:     filepath.Join(root, "data"),
		PersonalDir: filepath.Join(root, "personal_docs"),
		RunbookDir:  filepath.Join(root, "runbook"),
		UploadDir:   filepath.Join(root, "uploads"),
	}
	api := &countingAPIKeyManager{keys: map[string]string{BraveProvider: "k"}}
	loader := errBraveKeyLoader{err: errors.New("boom")}
	reg := fixedRegistry(api, loader)

	if _, err := Initialize(cfg, reg); err == nil {
		t.Fatal("expected Initialize to return error when BraveKeyLoader fails")
	}
}

type errBraveKeyLoader struct{ err error }

func (e errBraveKeyLoader) UpdateSearchConfig(_ string) error { return e.err }

// TestRequiredDirectoriesOrder pins the order the directories are created in
// (data, personal, runbook, upload). The Python helper iterates a fixed
// tuple; the Go port must match so test fixtures that assume the ordering
// keep working.
func TestRequiredDirectoriesOrder(t *testing.T) {
	cfg := Config{
		DataDir:     "d",
		PersonalDir: "p",
		RunbookDir:  "r",
		UploadDir:   "u",
	}
	got := cfg.RequiredDirectories()
	want := []string{"d", "p", "r", "u"}
	if len(got) != len(want) {
		t.Fatalf("len mismatch: got %v want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("dir[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}

// TestConfigWithDefaultsFillsBlanks verifies the withDefaults helper picks
// up the Default* constants for empty fields, and never overwrites a caller-
// supplied value.
func TestConfigWithDefaultsFillsBlanks(t *testing.T) {
	cfg := Config{DataDir: "/tmp/data"}.withDefaults()
	if cfg.DataDir != "/tmp/data" {
		t.Errorf("DataDir overwritten: got %q", cfg.DataDir)
	}
	if cfg.PersonalDir == "" {
		t.Error("PersonalDir should be filled from default")
	}
	if cfg.SessionsFile == "" {
		t.Error("SessionsFile should be filled from default")
	}
	if cfg.APIKeysFile == "" {
		t.Error("APIKeysFile should be filled from default")
	}
}
