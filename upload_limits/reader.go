package upload_limits

import (
	"errors"
	"fmt"
	"io"
)

// ErrUploadTooLarge is the sentinel returned by ReadUploadLimited when the
// source stream delivers more than the requested limit. Callers can match it
// with errors.Is to convert it to an HTTP 413 (or any other protocol-level
// response) without inspecting error strings.
var ErrUploadTooLarge = errors.New("upload exceeds limit")

// ReadUploadLimited reads from r until it has at most limit bytes. If the
// source yields more than limit bytes it returns ErrUploadTooLarge wrapped
// with a human-readable message that includes the label and a formatted
// limit. The label defaults to "Upload" when empty, matching the Python
// helper's default. Any non-EOF read error from the underlying source is
// returned as-is (so callers can use errors.Is to detect ErrUploadTooLarge
// independently of transport failures).
func ReadUploadLimited(r io.Reader, limit int, label string) ([]byte, error) {
	if label == "" {
		label = "Upload"
	}
	if limit < 1 {
		return nil, fmt.Errorf("limit must be greater than 0: %d", limit)
	}
	// We use a LimitReader at limit+1 so we can detect "more than allowed"
	// without an extra read. If the reader hits EOF before reaching that
	// extra byte, the result is under the cap and we return it directly.
	buf, err := io.ReadAll(io.LimitReader(r, int64(limit)+1))
	if err != nil {
		return nil, err
	}
	if len(buf) > limit {
		return nil, fmt.Errorf("%w: %s exceeds %s limit", ErrUploadTooLarge, label, FormatByteLimit(limit))
	}
	return buf, nil
}
