// Command runtimepaths-demo exercises the runtime_paths public surface.
//
// Usage:
//
//	runtimepaths-demo --print
//
// It builds an Environment from os.Args[0] + HOME (or USERPROFILE on
// Windows) and prints both GetAppRoot and GetDefaultDataDir so a
// reviewer (or CI smoke check) can eyeball the resolution.
package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	contextrp "github.com/odysseus/runtime_paths/pkg/runtimepaths"
)

func main() {
	printFlag := flag.Bool("print", false, "print resolved paths and exit")
	flag.Parse()

	if !*printFlag {
		fmt.Fprintf(os.Stderr, "usage: runtimepaths-demo --print\n")
		os.Exit(2)
	}

	exe, err := os.Executable()
	if err != nil {
		exe = os.Args[0]
	}

	home := os.Getenv("HOME")
	if home == "" {
		home = os.Getenv("USERPROFILE")
	}

	// Auto-detect "frozen" via the bundle-marker heuristic so the demo
	// works on a developer's machine AND inside a packaged binary.
	frozen, bundle, err := contextrp.FrozenProbe()
	if err != nil {
		fmt.Fprintf(os.Stderr, "FrozenProbe: %v\n", err)
	}

	env := contextrp.Environment{
		Frozen:    frozen,
		BundleDir: bundle,
		ExecPath:  exe,
		HomeDir:   home,
	}

	root := contextrp.GetAppRoot(env)
	data := contextrp.GetDefaultDataDir(env)
	info := contextrp.Describe(env)

	fmt.Printf("== runtime_paths summary ==\n")
	fmt.Printf("exec_path:    %s\n", filepath.Clean(exe))
	fmt.Printf("home_dir:     %s\n", home)
	fmt.Printf("frozen:       %t\n", info.Frozen)
	if info.Frozen {
		fmt.Printf("bundle_dir:   %s\n", info.BundleDir)
	}
	fmt.Printf("app_root:     %s\n", root)
	fmt.Printf("data_dir:     %s\n", data)
}
