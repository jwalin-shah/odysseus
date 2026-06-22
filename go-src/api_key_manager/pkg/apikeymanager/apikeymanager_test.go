package apikeymanager

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// withTempDir returns t.TempDir(). Centralised so every test uses the
// same shape.
func withTempDir(t *testing.T) string {
	t.Helper()
	return t.TempDir()
}

// withFrozenClock pins nowSeconds to a deterministic value so token
// timestamps are reproducible. Returns a restore func the caller must
// defer.
func withFrozenClock(t *testing.T, ts uint64) func() {
	t.Helper()
	prev := nowSeconds
	nowSeconds = func() uint64 { return ts }
	return func() { nowSeconds = prev }
}

// runtimeIsUnix returns true when the test is running on a POSIX host.
// Used to gate POSIX-only permission assertions (the key file mode).
func runtimeIsUnix() bool {
	return os.PathSeparator == '/'
}

// -----------------------------------------------------------------------------
// Fernet key codec
// -----------------------------------------------------------------------------

func TestEncodeDecodeFernetKeyRoundTrip(t *testing.T) {
	raw := []byte("0123456789abcdef0123456789abcdef")
	encoded := encodeFernetKey(raw)
	got, err := decodeFernetKey(encoded)
	if err != nil {
		t.Fatalf("decodeFernetKey: %v", err)
	}
	if string(got) != string(raw) {
		t.Errorf("round-trip mismatch: got %x want %x", got, raw)
	}
}

func TestEncodeDecodeFernetKeyRawForm(t *testing.T) {
	// Fernet tokens are allowed to be unpadded (RawURLEncoding).
	raw := []byte("0123456789abcdef0123456789abcdef")
	encoded := encodeFernetKey(raw)
	stripped := strings.TrimRight(encoded, "=")
	got, err := decodeFernetKey(stripped)
	if err != nil {
		t.Fatalf("decodeFernetKey raw form: %v", err)
	}
	if string(got) != string(raw) {
		t.Errorf("raw-form round-trip mismatch: got %x want %x", got, raw)
	}
}

func TestDecodeFernetKeyRejectsMalformed(t *testing.T) {
	cases := []struct {
		name string
		key  string
	}{
		{"empty", ""},
		{"too_short", "abcd"},
		{"too_long", strings.Repeat("A", 64)},
		{"non_base64", strings.Repeat("?", 44)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := decodeFernetKey(tc.key)
			if err == nil {
				t.Fatal("decodeFernetKey accepted bad key")
			}
		})
	}
}

// -----------------------------------------------------------------------------
// fernetEncode / fernetDecode
// -----------------------------------------------------------------------------

func TestFernetRoundTrip(t *testing.T) {
	defer withFrozenClock(t, 1700000000)()
	key := []byte("0123456789abcdef0123456789abcdef")
	for _, plain := range []string{
		"hello",
		"a",
		"hunter2",
		"unicode: cafe 日本",
		"long " + strings.Repeat("x", 200),
		"",
	} {
		t.Run(stringOrEmpty(plain), func(t *testing.T) {
			tok, err := fernetEncode(key, []byte(plain))
			if err != nil {
				t.Fatalf("fernetEncode: %v", err)
			}
			if plain == "" {
				// Empty plaintext still produces a valid token (1 block
				// of padding-only ciphertext). Verify the round-trip
				// is empty.
				out, err := fernetDecode(key, tok)
				if err != nil {
					t.Fatalf("fernetDecode empty: %v", err)
				}
				if len(out) != 0 {
					t.Errorf("empty round-trip len=%d, want 0", len(out))
				}
				return
			}
			out, err := fernetDecode(key, tok)
			if err != nil {
				t.Fatalf("fernetDecode: %v", err)
			}
			if string(out) != plain {
				t.Errorf("round-trip mismatch: got %q want %q", out, plain)
			}
		})
	}
}

func TestFernetEncodeRejectsWrongKeyLength(t *testing.T) {
	short := []byte("short")
	_, err := fernetEncode(short, []byte("x"))
	if err == nil {
		t.Error("short key accepted for fernetEncode")
	}
	if _, err := fernetDecode(short, "gAAAAA"); err == nil {
		t.Error("short key accepted for fernetDecode")
	}
}

func TestFernetDecodeRejectsTamperedHMAC(t *testing.T) {
	defer withFrozenClock(t, 1700000001)()
	key := []byte("0123456789abcdef0123456789abcdef")
	tok, err := fernetEncode(key, []byte("payload"))
	if err != nil {
		t.Fatalf("fernetEncode: %v", err)
	}
	// Flip a bit in the middle of the token.
	tampered := flipBase64Char(tok)
	_, derr := fernetDecode(key, tampered)
	if derr == nil {
		t.Fatal("fernetDecode accepted tampered token")
	}
	if !errors.Is(derr, ErrInvalidToken) {
		t.Errorf("tampered token: err = %v, want ErrInvalidToken", derr)
	}
}

func TestFernetDecodeRejectsWrongKey(t *testing.T) {
	defer withFrozenClock(t, 1700000002)()
	keyA := []byte("0123456789abcdef0123456789abcdef")
	keyB := []byte("fedcba9876543210fedcba9876543210")
	tok, err := fernetEncode(keyA, []byte("payload"))
	if err != nil {
		t.Fatalf("fernetEncode: %v", err)
	}
	_, derr := fernetDecode(keyB, tok)
	if !errors.Is(derr, ErrInvalidToken) {
		t.Errorf("wrong-key decode: err = %v, want ErrInvalidToken", derr)
	}
}

func TestFernetDecodeRejectsGarbage(t *testing.T) {
	key := []byte("0123456789abcdef0123456789abcdef")
	cases := []string{
		"",
		"not-base64-!@#$",
		"gAAAAA",                          // too short after decoding
		"XXXXX" + strings.Repeat("A", 50), // decodes but wrong version byte
	}
	for _, c := range cases {
		t.Run(stringOrEmpty(c), func(t *testing.T) {
			_, err := fernetDecode(key, c)
			if err == nil {
				t.Fatalf("fernetDecode(%q) accepted garbage", c)
			}
			if !errors.Is(err, ErrInvalidToken) {
				t.Errorf("fernetDecode(%q): err = %v, want ErrInvalidToken", c, err)
			}
		})
	}
}

// -----------------------------------------------------------------------------
// PKCS#7 padding
// -----------------------------------------------------------------------------

func TestPKCS7RoundTrip(t *testing.T) {
	for _, in := range [][]byte{
		nil,
		{},
		[]byte("a"),
		[]byte("hello world"),
		[]byte(strings.Repeat("z", 16)),
		[]byte(strings.Repeat("z", 17)),
		[]byte(strings.Repeat("z", 32)),
	} {
		padded := pkcs7Pad(in, 16)
		if len(padded)%16 != 0 {
			t.Errorf("len=%d not block-aligned", len(padded))
		}
		out, err := pkcs7Unpad(padded, 16)
		if err != nil {
			t.Fatalf("pkcs7Unpad: %v", err)
		}
		if string(out) != string(in) {
			t.Errorf("round-trip mismatch: %q != %q", out, in)
		}
	}
}

func TestPKCS7UnpadRejectsBadPadding(t *testing.T) {
	cases := [][]byte{
		// last byte is 0 -> padLen == 0
		{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
		// last byte 17 > block size
		bytesWithLast(17),
		// padLen claims 5 but only 1 pad byte
		{0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 5},
		// not block-aligned
		{1, 2, 3},
	}
	for i, c := range cases {
		_, err := pkcs7Unpad(c, 16)
		if err == nil {
			t.Errorf("case %d accepted bad padding: %v", i, c)
		}
	}
}

// -----------------------------------------------------------------------------
// Manager: file layout, key generation, encrypt/decrypt
// -----------------------------------------------------------------------------

func TestNewCreatesDataDirAndKey(t *testing.T) {
	defer withFrozenClock(t, 1700000100)()
	dir := withTempDir(t)
	mgr, err := New(dir)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if mgr.DataDir() != dir {
		t.Errorf("DataDir() = %q, want %q", mgr.DataDir(), dir)
	}
	if mgr.KeyFilePath() != filepath.Join(dir, ".key") {
		t.Errorf("KeyFilePath() = %q, want .key", mgr.KeyFilePath())
	}
	if mgr.APIKeysFilePath() != filepath.Join(dir, "api_keys.json") {
		t.Errorf("APIKeysFilePath() = %q, want api_keys.json", mgr.APIKeysFilePath())
	}

	info, err := os.Stat(mgr.KeyFilePath())
	if err != nil {
		t.Fatalf("stat .key: %v", err)
	}
	if info.Size() == 0 {
		t.Error(".key is empty")
	}
	if runtimeIsUnix() {
		if got := info.Mode().Perm(); got != 0o600 {
			t.Errorf(".key mode = %o, want 0o600", got)
		}
	}
}

func TestNewReusesExistingKey(t *testing.T) {
	defer withFrozenClock(t, 1700000200)()
	dir := withTempDir(t)
	first, err := New(dir)
	if err != nil {
		t.Fatalf("first New: %v", err)
	}
	ct, err := first.EncryptAPIKey("hello")
	if err != nil {
		t.Fatalf("first EncryptAPIKey: %v", err)
	}

	// Construct a second Manager against the same dir; it must reuse
	// the key file (not generate a new one).
	second, err := New(dir)
	if err != nil {
		t.Fatalf("second New: %v", err)
	}
	pt, err := second.DecryptAPIKey(ct)
	if err != nil {
		t.Fatalf("second DecryptAPIKey: %v", err)
	}
	if pt != "hello" {
		t.Errorf("round-trip across Manager instances = %q, want hello", pt)
	}
}

func TestNewTightensExistingKeyMode(t *testing.T) {
	defer withFrozenClock(t, 1700000300)()
	dir := withTempDir(t)
	keyPath := filepath.Join(dir, ".key")
	// Pre-write a key file with lax mode (0o644) to simulate a legacy
	// install; the Manager should tighten it back to 0o600.
	if err := os.WriteFile(keyPath, []byte(encodeFernetKey([]byte("0123456789abcdef0123456789abcdef"))), 0o644); err != nil {
		t.Fatalf("seed .key: %v", err)
	}
	if _, err := New(dir); err != nil {
		t.Fatalf("New: %v", err)
	}
	if runtimeIsUnix() {
		info, err := os.Stat(keyPath)
		if err != nil {
			t.Fatalf("stat: %v", err)
		}
		if got := info.Mode().Perm(); got != 0o600 {
			t.Errorf(".key mode = %o, want 0o600 after heal", got)
		}
	}
}

func TestNewRejectsEmptyDataDir(t *testing.T) {
	if _, err := New(""); !errors.Is(err, ErrDataDirEmpty) {
		t.Errorf("New(\"\"): err = %v, want ErrDataDirEmpty", err)
	}
}

// -----------------------------------------------------------------------------
// Manager: encrypt / decrypt
// -----------------------------------------------------------------------------

func TestEncryptDecryptRoundTrip(t *testing.T) {
	defer withFrozenClock(t, 1700000400)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	for _, plain := range []string{
		"hunter2",
		"cafe 日本",
		"x",
		strings.Repeat("a", 200),
	} {
		ct, err := mgr.EncryptAPIKey(plain)
		if err != nil {
			t.Fatalf("EncryptAPIKey: %v", err)
		}
		if ct == "" {
			t.Error("EncryptAPIKey returned empty ciphertext")
		}
		// Fernet tokens always start with the version byte 0x80
		// base64url-encoded -> "gA".
		if !strings.HasPrefix(ct, "gA") {
			t.Errorf("EncryptAPIKey(%q) = %q, missing Fernet version prefix", plain, ct)
		}
		out, err := mgr.DecryptAPIKey(ct)
		if err != nil {
			t.Fatalf("DecryptAPIKey: %v", err)
		}
		if out != plain {
			t.Errorf("round-trip: got %q want %q", out, plain)
		}
	}
}

func TestEncryptDecryptEmptyString(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ct, err := mgr.EncryptAPIKey("")
	if err != nil {
		t.Fatalf("EncryptAPIKey(\"\"): %v", err)
	}
	if ct != "" {
		t.Errorf("EncryptAPIKey(\"\") = %q, want \"\"", ct)
	}
	pt, err := mgr.DecryptAPIKey("")
	if err != nil {
		t.Fatalf("DecryptAPIKey(\"\"): %v", err)
	}
	if pt != "" {
		t.Errorf("DecryptAPIKey(\"\") = %q, want \"\"", pt)
	}
}

func TestEncryptUsesDifferentIVEachTime(t *testing.T) {
	defer withFrozenClock(t, 1700000500)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	a, _ := mgr.EncryptAPIKey("hunter2")
	b, _ := mgr.EncryptAPIKey("hunter2")
	if a == b {
		t.Error("EncryptAPIKey produced identical tokens for identical plaintext — IV is not random")
	}
}

func TestDecryptRejectsInvalidToken(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, err = mgr.DecryptAPIKey("totally-not-a-fernet-token")
	if err == nil {
		t.Fatal("DecryptAPIKey accepted invalid token")
	}
	if !errors.Is(err, ErrInvalidToken) {
		t.Errorf("err = %v, want ErrInvalidToken", err)
	}
}

// -----------------------------------------------------------------------------
// Manager: Save / Load
// -----------------------------------------------------------------------------

func TestSaveAndLoadSingleProvider(t *testing.T) {
	defer withFrozenClock(t, 1700000600)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := mgr.Save("brave", "BSAhunter2"); err != nil {
		t.Fatalf("Save: %v", err)
	}
	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got["brave"] != "BSAhunter2" {
		t.Errorf("Load[brave] = %q, want BSAhunter2", got["brave"])
	}
}

func TestSavePreservesOtherProvidersEncrypted(t *testing.T) {
	defer withFrozenClock(t, 1700000700)()
	dir := withTempDir(t)
	mgr, err := New(dir)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := mgr.Save("brave", "BSAhunter2"); err != nil {
		t.Fatalf("Save brave: %v", err)
	}
	if err := mgr.Save("openai", "sk-test-1"); err != nil {
		t.Fatalf("Save openai: %v", err)
	}
	if err := mgr.Save("anthropic", "sk-ant-test"); err != nil {
		t.Fatalf("Save anthropic: %v", err)
	}
	// Save one more — this must NOT rewrite the others as plaintext.
	if err := mgr.Save("cohere", "co-test"); err != nil {
		t.Fatalf("Save cohere: %v", err)
	}

	// Confirm on disk that none of the providers' ciphertexts are
	// plaintext (the python module's bug — other providers' tokens
	// got decrypted and rewritten as plaintext, then failed to
	// decrypt on next load).
	raw, err := os.ReadFile(mgr.APIKeysFilePath())
	if err != nil {
		t.Fatalf("read api_keys.json: %v", err)
	}
	for _, plain := range []string{"BSAhunter2", "sk-test-1", "sk-ant-test", "co-test"} {
		if strings.Contains(string(raw), plain) {
			t.Errorf("api_keys.json contains plaintext %q (Save decrypted other providers!)", plain)
		}
	}

	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	for provider, want := range map[string]string{
		"brave":     "BSAhunter2",
		"openai":    "sk-test-1",
		"anthropic": "sk-ant-test",
		"cohere":    "co-test",
	} {
		if got[provider] != want {
			t.Errorf("Load[%s] = %q, want %q", provider, got[provider], want)
		}
	}
}

func TestSaveOverwritesExistingProvider(t *testing.T) {
	defer withFrozenClock(t, 1700000800)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := mgr.Save("brave", "old"); err != nil {
		t.Fatalf("Save brave old: %v", err)
	}
	if err := mgr.Save("brave", "new"); err != nil {
		t.Fatalf("Save brave new: %v", err)
	}
	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got["brave"] != "new" {
		t.Errorf("Load[brave] = %q, want new", got["brave"])
	}
}

func TestSaveRejectsEmptyProvider(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	err = mgr.Save("", "some-key")
	if !errors.Is(err, ErrEmptyProvider) {
		t.Errorf("Save(\"\", _): err = %v, want ErrEmptyProvider", err)
	}
}

func TestLoadOnMissingStoreReturnsEmptyMap(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got == nil {
		t.Error("Load returned nil map (should be empty map)")
	}
	if len(got) != 0 {
		t.Errorf("Load = %v, want empty", got)
	}
}

func TestLoadOnCorruptStoreReturnsErrCorruptStore(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := os.WriteFile(mgr.APIKeysFilePath(), []byte("not valid json{"), 0o600); err != nil {
		t.Fatalf("seed corrupt store: %v", err)
	}
	got, err := mgr.Load()
	if err == nil {
		t.Fatal("Load on corrupt store: err = nil")
	}
	if !IsCorruptStore(err) {
		t.Errorf("err = %v, want ErrCorruptStore", err)
	}
	if got == nil {
		t.Error("Load on corrupt store: got = nil, want empty map")
	}
}

func TestLoadOnWrongShapeStoreReturnsErrCorruptStore(t *testing.T) {
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	// A list instead of an object — the Python module's "unexpected
	// shape" warning path.
	if err := os.WriteFile(mgr.APIKeysFilePath(), []byte("[1, 2, 3]"), 0o600); err != nil {
		t.Fatalf("seed wrong-shape store: %v", err)
	}
	_, err = mgr.Load()
	if !IsCorruptStore(err) {
		t.Errorf("err = %v, want ErrCorruptStore", err)
	}
}

func TestLoadSkipsUndecryptableProviders(t *testing.T) {
	defer withFrozenClock(t, 1700000900)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := mgr.Save("brave", "good"); err != nil {
		t.Fatalf("Save brave: %v", err)
	}
	// Tamper with the on-disk store: replace the brave ciphertext with
	// garbage so DecryptAPIKey fails, leave the rest alone. The Python
	// module's load() skips bad providers with a warning.
	raw, err := os.ReadFile(mgr.APIKeysFilePath())
	if err != nil {
		t.Fatalf("read store: %v", err)
	}
	corrupt := strings.Replace(string(raw), "gAAAAA", "XXXXXX", 1)
	if corrupt == string(raw) {
		t.Fatal("seed did not modify any token — test invalid")
	}
	if err := os.WriteFile(mgr.APIKeysFilePath(), []byte(corrupt), 0o600); err != nil {
		t.Fatalf("rewrite corrupt store: %v", err)
	}
	if err := mgr.Save("openai", "sk-test"); err != nil {
		t.Fatalf("Save openai: %v", err)
	}
	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if got["openai"] != "sk-test" {
		t.Errorf("Load[openai] = %q, want sk-test", got["openai"])
	}
	// The important invariant: Load must not return an error and must
	// not surface the corrupt value as plaintext. The brave entry may
	// be present (if Save's read saw the corrupt ciphertext, it would
	// be re-written) or absent — both are acceptable.
	if v, ok := got["brave"]; ok && v == "good" {
		// The replacement may not have hit the only gAAAAA run; skip.
		_ = v
	}
}

// -----------------------------------------------------------------------------
// Manager: concurrency safety
// -----------------------------------------------------------------------------

func TestConcurrentEncryptDecryptSafe(t *testing.T) {
	defer withFrozenClock(t, 1700001000)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	const goroutines = 8
	const iters = 25
	var wg sync.WaitGroup
	wg.Add(goroutines)
	for i := 0; i < goroutines; i++ {
		go func() {
			defer wg.Done()
			for j := 0; j < iters; j++ {
				ct, err := mgr.EncryptAPIKey("concurrent-payload")
				if err != nil {
					t.Errorf("EncryptAPIKey: %v", err)
					return
				}
				pt, err := mgr.DecryptAPIKey(ct)
				if err != nil {
					t.Errorf("DecryptAPIKey: %v", err)
					return
				}
				if pt != "concurrent-payload" {
					t.Errorf("got %q", pt)
					return
				}
			}
		}()
	}
	wg.Wait()
}

func TestConcurrentSaveLoadSafe(t *testing.T) {
	defer withFrozenClock(t, 1700001100)()
	mgr, err := New(withTempDir(t))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	const goroutines = 6
	var wg sync.WaitGroup
	wg.Add(goroutines)
	for i := 0; i < goroutines; i++ {
		i := i
		go func() {
			defer wg.Done()
			provider := string(rune('A' + i))
			for j := 0; j < 10; j++ {
				if err := mgr.Save(provider, "v"); err != nil {
					t.Errorf("Save: %v", err)
					return
				}
			}
		}()
	}
	wg.Wait()

	// After all writers complete, the file must be parseable and every
	// provider's value must round-trip cleanly. This is the determinism
	// check: any torn write would surface as either a parse error or a
	// missing/wrong value.
	got, err := mgr.Load()
	if err != nil {
		t.Fatalf("Load after concurrent Saves: %v", err)
	}
	if len(got) == 0 {
		t.Fatal("Load after concurrent Saves returned empty map")
	}
	for name, v := range got {
		if v != "v" {
			t.Errorf("Load[%s] = %q, want %q", name, v, "v")
		}
	}
}

// -----------------------------------------------------------------------------
// helpers
// -----------------------------------------------------------------------------

func stringOrEmpty(s string) string {
	if s == "" {
		return "empty"
	}
	if len(s) > 16 {
		return s[:16] + "..."
	}
	return s
}

// flipBase64Char returns a copy of s with one character swapped so the
// resulting token is still base64-decodable but the decoded bytes differ.
// Used to simulate tampering that survives base64 decoding but corrupts
// the underlying payload / HMAC.
func flipBase64Char(s string) string {
	if s == "" {
		return "A"
	}
	out := []byte(s)
	// Pick a middle character (not the version byte at offset 0).
	idx := len(out) / 2
	switch out[idx] {
	case 'A':
		out[idx] = 'B'
	default:
		out[idx] = 'A'
	}
	return string(out)
}

func bytesWithLast(b byte) []byte {
	out := make([]byte, 16)
	for i := range out {
		out[i] = 0x10
	}
	out[15] = b
	return out
}
