// Command appinit is a small wiring demo for the app_initializer Go port.
//
// Usage:
//
//	appinit --data-dir <path> --personal-dir <path> --runbook-dir <path> \
//	        --upload-dir <path> --base-dir <path>
//
// It runs CreateDirectories then Initialize with the DefaultRegistry and
// prints the resulting AppContext as a one-line-per-field summary so a human
// (or a CI smoke check) can eyeball which components were wired.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"reflect"

	contextappinit "github.com/odysseus/app_initializer/pkg/appinit"
)

func main() {
	var cfg contextappinit.Config
	flag.StringVar(&cfg.BaseDir, "base-dir", "", "base directory forwarded to UploadHandler")
	flag.StringVar(&cfg.DataDir, "data-dir", "", "data directory (e.g. .odysseus/data)")
	flag.StringVar(&cfg.PersonalDir, "personal-dir", "", "personal documents directory")
	flag.StringVar(&cfg.RunbookDir, "runbook-dir", "", "runbook documents directory")
	flag.StringVar(&cfg.UploadDir, "upload-dir", "", "upload directory")
	flag.StringVar(&cfg.SessionsFile, "sessions-file", "", "sessions.json path")
	flag.StringVar(&cfg.APIKeysFile, "api-keys-file", "", "api_keys.json path")
	flag.Parse()

	if err := contextappinit.CreateDirectories(cfg); err != nil {
		fmt.Fprintf(os.Stderr, "CreateDirectories failed: %v\n", err)
		os.Exit(1)
	}

	ctx, err := contextappinit.Initialize(cfg, contextappinit.Registry{})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Initialize failed: %v\n", err)
		os.Exit(1)
	}

	printSummary(cfg, ctx)
}

// printSummary emits a stable, machine-readable view of the AppContext so a
// reviewer can see which slots are wired vs. left nil. We use a struct that
// tags every component with its Go type — a nil component shows up as
// "<nil>", a wired component as its concrete type name.
func printSummary(cfg contextappinit.Config, ctx *contextappinit.AppContext) {
	resolved := cfg.WithDefaults()

	fmt.Printf("== app_initializer summary ==\n")
	fmt.Printf("base_dir:        %s\n", resolved.BaseDir)
	fmt.Printf("data_dir:        %s\n", resolved.DataDir)
	fmt.Printf("personal_dir:    %s\n", resolved.PersonalDir)
	fmt.Printf("runbook_dir:     %s\n", resolved.RunbookDir)
	fmt.Printf("upload_dir:      %s\n", resolved.UploadDir)
	fmt.Printf("sessions_file:   %s\n", resolved.SessionsFile)
	fmt.Printf("api_keys_file:   %s\n", resolved.APIKeysFile)

	fmt.Printf("\n== components ==\n")
	type row struct {
		Name string
		Val  any
	}
	rows := []row{
		{"memory_manager", ctx.MemoryManager},
		{"memory_vector", ctx.MemoryVector},
		{"memory_provider_registry", ctx.MemoryProviderRegistry},
		{"skills_manager", ctx.SkillsManager},
		{"session_manager", ctx.SessionManager},
		{"upload_handler", ctx.UploadHandler},
		{"personal_docs_manager", ctx.PersonalDocsManager},
		{"api_key_manager", ctx.APIKeyManager},
		{"preset_manager", ctx.PresetManager},
		{"chat_processor", ctx.ChatProcessor},
		{"research_handler", ctx.ResearchHandler},
		{"chat_handler", ctx.ChatHandler},
		{"model_discovery", ctx.ModelDiscovery},
	}
	for _, r := range rows {
		if r.Val == nil {
			fmt.Printf("- %-26s <nil>\n", r.Name)
			continue
		}
		fmt.Printf("- %-26s %s\n", r.Name, reflect.TypeOf(r.Val).String())
	}

	// PersonalIndex / CurrentPresets in compact JSON so a CI parser can pick
	// them up if needed.
	piJSON, _ := json.Marshal(ctx.PersonalIndex)
	cpJSON, _ := json.Marshal(ctx.CurrentPresets)
	fmt.Printf("\npersonal_index:  %s\n", string(piJSON))
	fmt.Printf("current_presets: %s\n", string(cpJSON))
}
