// Command taskendpoint-demo demonstrates the wiring of the taskendpoint
// package. It exercises Resolve() against three representative inputs:
//
//   - admin settings configured  → returns Source="admin"
//   - no admin settings, only fallbacks → returns Source="fallback"
//   - no admin settings, no fallbacks  → returns Source="empty"
//
// Each scenario is printed as a one-line summary so a human reviewer can
// eyeball the resolution path without writing a test program.
package main

import (
	"fmt"
	"os"

	contexttask "github.com/odysseus/task_endpoint/pkg/taskendpoint"
)

func printScenario(label string, r contexttask.Resolution) {
	fmt.Printf("[%s]\n", label)
	fmt.Printf("  source = %s\n", r.Source)
	fmt.Printf("  url    = %q\n", r.URL)
	fmt.Printf("  model  = %q\n", r.Model)
	if len(r.Headers) > 0 {
		fmt.Printf("  headers:\n")
		for k, v := range r.Headers {
			fmt.Printf("    - %s: %s\n", k, v)
		}
	} else {
		fmt.Printf("  headers: (none)\n")
	}
	fmt.Println()
}

func main() {
	fmt.Println("== taskendpoint demo ==")
	fmt.Println()

	// 1. Admin-configured path: admin settings carry a URL and model,
	//    so they win over the fallbacks.
	admin := contexttask.Settings{
		EndpointID:      "task-primary",
		EndpointURL:     "https://admin.example/v1",
		EndpointModel:   "admin-model",
		EndpointHeaders: map[string]string{"X-Admin": "yes"},
	}
	r1 := contexttask.Resolve(admin,
		"https://fallback.example/v1", "fallback-model",
		map[string]string{"Authorization": "Bearer xyz"}, "owner-1")
	printScenario("admin wins", r1)

	// 2. Fallback path: no admin settings, fallbacks supplied.
	r2 := contexttask.Resolve(contexttask.Settings{},
		"https://fallback.example/v1", "fallback-model",
		map[string]string{"Authorization": "Bearer xyz"}, "")
	printScenario("fallback", r2)

	// 3. Empty path: nothing configured, nothing supplied.
	r3 := contexttask.Resolve(contexttask.Settings{}, "", "", nil, "")
	printScenario("empty", r3)

	// Exit non-zero on the empty path so callers can wire it into CI as
	// a smoke test that the resolver surfaced the missing-config signal.
	if r3.Source != "empty" {
		fmt.Fprintln(os.Stderr, "expected empty scenario to surface Source=empty")
		os.Exit(2)
	}
}
