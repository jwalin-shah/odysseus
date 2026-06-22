package odyexceptions

import "errors"

// errorsAs is a thin shim around errors.As so AsError in helpers.go can be
// expressed without importing "errors" there (keeping helpers.go readable).
func errorsAs(err error, target any) bool {
	return errors.As(err, target)
}
