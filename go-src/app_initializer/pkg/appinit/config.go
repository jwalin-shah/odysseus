package appinit

// Config groups the paths and base directory the orchestrator needs to wire
// the manager graph. Zero-value Config is intentionally usable: it falls back
// to the Default* constants so callers (and tests) can stay terse.
//
// Each field can be overridden independently. Empty strings mean "use the
// default". This mirrors the Python constants module where each path is
// derived from DATA_DIR but a caller may still pass an explicit base_dir.
type Config struct {
	// BaseDir is the application's top-level directory. It is forwarded to
	// the UploadHandler constructor. May be empty.
	BaseDir string

	// DataDir is the root for persisted state. Used by managers that own
	// their own subdirectory (MemoryManager, SkillsManager, APIKeyManager,
	// PresetManager, ...).
	DataDir string

	// PersonalDir, RunbookDir, UploadDir, SessionsFile, APIKeysFile are the
	// per-component paths. Empty values fall back to the Default* constants.
	PersonalDir  string
	RunbookDir   string
	UploadDir    string
	SessionsFile string
	APIKeysFile  string
}

// withDefaults returns a copy of c with empty fields filled in from the
// Default* constants. It never mutates the caller's Config.
func (c Config) withDefaults() Config {
	if c.DataDir == "" {
		c.DataDir = DefaultDataDir
	}
	if c.PersonalDir == "" {
		c.PersonalDir = DefaultPersonalDir
	}
	if c.RunbookDir == "" {
		c.RunbookDir = DefaultRunbookDir
	}
	if c.UploadDir == "" {
		c.UploadDir = DefaultUploadDir
	}
	if c.SessionsFile == "" {
		c.SessionsFile = DefaultSessionsFile
	}
	if c.APIKeysFile == "" {
		c.APIKeysFile = DefaultAPIKeysFile
	}
	return c
}

// WithDefaults returns a copy of c with empty fields filled in from the
// Default* constants. It is the exported form of withDefaults so callers
// outside this package (notably cmd/appinit) can see the resolved paths.
func (c Config) WithDefaults() Config {
	return c.withDefaults()
}

// RequiredDirectories returns the directories that CreateDirectories ensures
// exist. The order matches the Python implementation: data, personal,
// runbook, upload.
func (c Config) RequiredDirectories() []string {
	c = c.withDefaults()
	return []string{c.DataDir, c.PersonalDir, c.RunbookDir, c.UploadDir}
}
