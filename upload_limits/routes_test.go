package upload_limits

import (
	"os"
	"testing"
)

type routeCase struct {
	name     string
	envName  string
	defaultV int
	get      func() int
}

func perRouteCases() []routeCase {
	return []routeCase{
		{
			name:     "gallery",
			envName:  EnvGalleryUploadMaxBytes,
			defaultV: DefaultGalleryUploadMaxBytes,
			get:      GetGalleryUploadMaxBytes,
		},
		{
			name:     "gallery_transform",
			envName:  EnvGalleryTransformUploadMaxBytes,
			defaultV: DefaultGalleryTransformUploadMaxBytes,
			get:      GetGalleryTransformUploadMaxBytes,
		},
		{
			name:     "memory_import",
			envName:  EnvMemoryImportMaxBytes,
			defaultV: DefaultMemoryImportMaxBytes,
			get:      GetMemoryImportMaxBytes,
		},
		{
			name:     "personal",
			envName:  EnvPersonalUploadMaxBytes,
			defaultV: DefaultPersonalUploadMaxBytes,
			get:      GetPersonalUploadMaxBytes,
		},
		{
			name:     "email_compose",
			envName:  EnvEmailComposeUploadMaxBytes,
			defaultV: DefaultEmailComposeUploadMaxBytes,
			get:      GetEmailComposeUploadMaxBytes,
		},
		{
			name:     "stt",
			envName:  EnvSTTMaxAudioBytes,
			defaultV: DefaultSTTMaxAudioBytes,
			get:      GetSTTMaxAudioBytes,
		},
		{
			name:     "ics",
			envName:  EnvICSMaxBytes,
			defaultV: DefaultICSMaxBytes,
			get:      GetICSMaxBytes,
		},
	}
}

func TestPerRouteGetters_Default(t *testing.T) {
	for _, c := range perRouteCases() {
		t.Run(c.name, func(t *testing.T) {
			prev, hadPrev := os.LookupEnv(c.envName)
			os.Unsetenv(c.envName)
			t.Cleanup(func() {
				if hadPrev {
					os.Setenv(c.envName, prev)
				}
			})
			got := c.get()
			if got != c.defaultV {
				t.Errorf("%s default = %d, want %d", c.name, got, c.defaultV)
			}
		})
	}
}

func TestPerRouteGetters_EnvOverride(t *testing.T) {
	for _, c := range perRouteCases() {
		t.Run(c.name, func(t *testing.T) {
			const override = 1234567
			t.Setenv(c.envName, "1234567")
			got := c.get()
			if got != override {
				t.Errorf("%s override = %d, want %d", c.name, got, override)
			}
		})
	}
}

func TestResolve_PopulatesAllFields(t *testing.T) {
	// Make sure no env is set so we get defaults.
	for _, c := range perRouteCases() {
		prev, hadPrev := os.LookupEnv(c.envName)
		os.Unsetenv(c.envName)
		if hadPrev {
			// Re-set after the test; t.Cleanup runs in LIFO order.
			t.Cleanup(func() { os.Setenv(c.envName, prev) })
		}
	}
	prevChat, hadChat := os.LookupEnv(EnvChatUploadMaxBytes)
	os.Unsetenv(EnvChatUploadMaxBytes)
	if hadChat {
		t.Cleanup(func() { os.Setenv(EnvChatUploadMaxBytes, prevChat) })
	}

	l, err := Resolve()
	if err != nil {
		t.Fatalf("Resolve: %v", err)
	}
	if l.Chat != DefaultChatUploadMaxBytes {
		t.Errorf("Chat = %d", l.Chat)
	}
	if l.Gallery != DefaultGalleryUploadMaxBytes {
		t.Errorf("Gallery = %d", l.Gallery)
	}
	if l.GalleryTransform != DefaultGalleryTransformUploadMaxBytes {
		t.Errorf("GalleryTransform = %d", l.GalleryTransform)
	}
	if l.MemoryImport != DefaultMemoryImportMaxBytes {
		t.Errorf("MemoryImport = %d", l.MemoryImport)
	}
	if l.Personal != DefaultPersonalUploadMaxBytes {
		t.Errorf("Personal = %d", l.Personal)
	}
	if l.EmailCompose != DefaultEmailComposeUploadMaxBytes {
		t.Errorf("EmailCompose = %d", l.EmailCompose)
	}
	if l.STT != DefaultSTTMaxAudioBytes {
		t.Errorf("STT = %d", l.STT)
	}
	if l.ICS != DefaultICSMaxBytes {
		t.Errorf("ICS = %d", l.ICS)
	}
}

func TestResolve_PropagatesEnvError(t *testing.T) {
	t.Setenv(EnvChatUploadMaxBytes, "not-a-number")
	_, err := Resolve()
	if err == nil {
		t.Fatal("expected Resolve to fail when env is invalid")
	}
}
