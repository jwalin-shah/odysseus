//go:build !windows

package runtimepaths

import "os"

// homeEnvVar is the environment variable consulted on Unix-likes.
// USERPROFILE on Windows is handled in helpers_windows.go.
const homeEnvVar = "HOME"

// homeFromEnv reads HOME (Unix) and returns it cleaned + absolute.
// Returns "" when unset.
func homeFromEnv() string {
	return cleanAbs(os.Getenv(homeEnvVar))
}
