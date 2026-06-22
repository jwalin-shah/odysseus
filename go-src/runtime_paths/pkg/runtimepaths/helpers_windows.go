//go:build windows

package runtimepaths

import "os"

// homeEnvVar is the environment variable consulted on Windows.
const homeEnvVar = "USERPROFILE"

// homeFromEnv reads USERPROFILE and returns it cleaned + absolute.
// Returns "" when unset.
func homeFromEnv() string {
	return cleanAbs(os.Getenv(homeEnvVar))
}
