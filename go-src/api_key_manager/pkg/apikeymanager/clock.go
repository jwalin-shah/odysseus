package apikeymanager

import "time"

// nowSeconds returns the current wall-clock time in seconds since the Unix
// epoch. The Fernet spec does not require the timestamp field to be exact
// — it is informational and receivers typically ignore it unless they
// implement rotation policies.
//
// Pulled into a function so tests can override the value via the
// nowSeconds package var without a clock injection framework.
var nowSeconds = func() uint64 { return uint64(time.Now().Unix()) }
