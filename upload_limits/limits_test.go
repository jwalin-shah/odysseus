package upload_limits

import (
	"os"
	"strings"
	"testing"
)

func TestFormatByteLimit(t *testing.T) {
	cases := []struct {
		name string
		in   int
		want string
	}{
		{"exact 1 MB", 1024 * 1024, "1 MB"},
		{"exact 10 MB", 10 * 1024 * 1024, "10 MB"},
		{"exact 25 MB", 25 * 1024 * 1024, "25 MB"},
		{"exact 100 MB", 100 * 1024 * 1024, "100 MB"},
		{"exact 1 KB", 1024, "1 KB"},
		{"exact 5 KB", 5 * 1024, "5 KB"},
		{"non-multiple under KB", 500, "500 bytes"},
		{"one byte short of MB", 1024*1024 - 1, "1048575 bytes"},
		{"one byte over KB", 1024 + 1, "1025 bytes"},
		{"zero", 0, "0 bytes"},
		{"negative falls through to bytes branch", -1, "-1 bytes"},
		{"large negative", -1024, "-1024 bytes"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := FormatByteLimit(tc.in)
			if got != tc.want {
				t.Errorf("FormatByteLimit(%d) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestReadByteLimitEnv_UnsetReturnsDefault(t *testing.T) {
	const name = "ODYSSEUS_TEST_UNSET_BVAR"
	// t.Setenv with empty string keeps the var set; use Unsetenv to make
	// LookupEnv report ok=false. We restore any prior value at end via
	// t.Cleanup.
	prev, hadPrev := os.LookupEnv(name)
	os.Unsetenv(name)
	t.Cleanup(func() {
		if hadPrev {
			os.Setenv(name, prev)
		}
	})
	got, err := readByteLimitEnv(name, 42)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 42 {
		t.Errorf("got %d, want 42", got)
	}
}

func TestReadByteLimitEnv_EmptyReturnsDefault(t *testing.T) {
	const name = "ODYSSEUS_TEST_EMPTY_BVAR"
	t.Setenv(name, "")
	got, err := readByteLimitEnv(name, 99)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 99 {
		t.Errorf("got %d, want 99", got)
	}
}

func TestReadByteLimitEnv_WhitespaceReturnsDefault(t *testing.T) {
	const name = "ODYSSEUS_TEST_WHITESPACE_BVAR"
	t.Setenv(name, "   \t  ")
	got, err := readByteLimitEnv(name, 7)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 7 {
		t.Errorf("got %d, want 7", got)
	}
}

func TestReadByteLimitEnv_ValidInt(t *testing.T) {
	const name = "ODYSSEUS_TEST_VALID_BVAR"
	t.Setenv(name, "123456")
	got, err := readByteLimitEnv(name, 0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 123456 {
		t.Errorf("got %d, want 123456", got)
	}
}

func TestReadByteLimitEnv_NonIntReturnsError(t *testing.T) {
	const name = "ODYSSEUS_TEST_NONINT_BVAR"
	t.Setenv(name, "abc")
	_, err := readByteLimitEnv(name, 1)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "must be an integer byte count") {
		t.Errorf("error %q should mention integer byte count", err)
	}
}

func TestReadByteLimitEnv_ZeroReturnsError(t *testing.T) {
	const name = "ODYSSEUS_TEST_ZERO_BVAR"
	t.Setenv(name, "0")
	_, err := readByteLimitEnv(name, 1)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "must be greater than 0") {
		t.Errorf("error %q should mention greater than 0", err)
	}
}

func TestReadByteLimitEnv_NegativeReturnsError(t *testing.T) {
	const name = "ODYSSEUS_TEST_NEG_BVAR"
	t.Setenv(name, "-5")
	_, err := readByteLimitEnv(name, 1)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "must be greater than 0") {
		t.Errorf("error %q should mention greater than 0", err)
	}
}

func TestReadByteLimitEnv_VeryLarge(t *testing.T) {
	const name = "ODYSSEUS_TEST_LARGE_BVAR"
	// 1 TiB worth of bytes — well within int64, but a sanity check that we
	// don't overflow on big values.
	t.Setenv(name, "1099511627776")
	got, err := readByteLimitEnv(name, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 1099511627776 {
		t.Errorf("got %d, want 1099511627776", got)
	}
}

func TestGetChatUploadMaxBytes_Default(t *testing.T) {
	// Ensure the env var is truly unset for the duration of the test.
	prev, hadPrev := os.LookupEnv(EnvChatUploadMaxBytes)
	os.Unsetenv(EnvChatUploadMaxBytes)
	t.Cleanup(func() {
		if hadPrev {
			os.Setenv(EnvChatUploadMaxBytes, prev)
		}
	})
	got := GetChatUploadMaxBytes()
	if got != DefaultChatUploadMaxBytes {
		t.Errorf("got %d, want %d", got, DefaultChatUploadMaxBytes)
	}
}

func TestGetChatUploadMaxBytes_EnvOverride(t *testing.T) {
	t.Setenv(EnvChatUploadMaxBytes, "524288") // 512 KB
	got := GetChatUploadMaxBytes()
	if got != 524288 {
		t.Errorf("got %d, want 524288", got)
	}
}
