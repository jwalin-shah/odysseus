package agentloop

import "time"

// timeAfter / millis — tiny indirection so verifier.go doesn't need a
// time import in every callsite. We could just use time.After and
// time.Millisecond directly; this exists so the stub can be replaced with
// a fake clock in tests without rewiring imports.
var (
	timeAfter = func(d time.Duration) <-chan time.Time { return time.After(d) }
	millis    = time.Millisecond
)
