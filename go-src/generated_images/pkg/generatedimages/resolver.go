// Package generatedimages is the Go port of src/generated_images.py.
// The Python module guards a public file-serving endpoint over a
// directory of generated images. It exposes three pieces of state and
// one resolver:
//
//	GENERATED_IMAGE_DIR = Path(GENERATED_IMAGES_DIR)
//	GENERATED_IMAGE_RE  = re.compile(r"^[a-f0-9]{8,64}\.(png|jpg|jpeg|webp|gif|mp4|mov|webm|mkv|m4v)$")
//	GENERATED_IMAGE_HEADERS = {"Cache-Control": "...", "X-Content-Type-Options": "nosniff"}
//
//	def resolve_generated_image_path(filename: str) -> Path:
//	    if not isinstance(filename, str) or not GENERATED_IMAGE_RE.fullmatch(filename):
//	        raise HTTPException(status_code=400, detail="Invalid filename")
//	    root = GENERATED_IMAGE_DIR.resolve()
//	    path = (GENERATED_IMAGE_DIR / filename).resolve()
//	    try:
//	        if os.path.commonpath([str(root), str(path)]) != str(root):
//	            raise ValueError
//	    except Exception:
//	        raise HTTPException(status_code=400, detail="Invalid filename")
//	    if not path.exists():
//	        raise HTTPException(status_code=404, detail="Image not found")
//	    return path
//
// The Go port keeps every contract. It returns a typed error (FilenameError
// / NotFoundError) rather than HTTPException because Go HTTP handlers
// translate the typed error to a status code at the boundary — that
// keeps this package free of any HTTP framework dependency.
package generatedimages

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
)

// AllowedExtensions mirrors the extension alternation in
// GENERATED_IMAGE_RE. We keep it as a string slice so error messages
// can render the same list the Python regex embeds.
var AllowedExtensions = []string{
	"png", "jpg", "jpeg", "webp", "gif",
	"mp4", "mov", "webm", "mkv", "m4v",
}

// HashPattern matches the "8-64 lowercase hex chars" portion of the
// Python regex. Combined with AllowedExtensions in Match to keep
// the alternation centralized.
var HashPattern = `^[a-f0-9]{8,64}$`

// filenameRe is the compiled form of the Python GENERATED_IMAGE_RE.
// Hex prefix + dot + one of the allowed extensions, fullmatch.
var filenameRe = regexp.MustCompile(`^[a-f0-9]{8,64}\.(png|jpg|jpeg|webp|gif|mp4|mov|webm|mkv|m4v)$`)

// ImageHeaders is the canonical response-header set served alongside
// generated images. Mirrors GENERATED_IMAGE_HEADERS in
// src/generated_images.py:
//
//	"Cache-Control": "public, max-age=31536000, immutable",
//	"X-Content-Type-Options": "nosniff",
//
// Callers should copy these into their HTTP response before writing
// the file body. Both entries are immutable strings — the demo and
// tests pin them.
var ImageHeaders = map[string]string{
	"Cache-Control":          "public, max-age=31536000, immutable",
	"X-Content-Type-Options": "nosniff",
}

// FilenameError is returned when the filename fails validation. It
// mirrors the 400 "Invalid filename" branch of the Python source.
// Callers translate this to http.StatusBadRequest at the HTTP edge.
type FilenameError struct{ Filename string }

func (e *FilenameError) Error() string {
	return fmt.Sprintf("invalid filename: %q", e.Filename)
}

// NotFoundError is returned when the filename is valid but the file
// does not exist on disk. It mirrors the 404 "Image not found"
// branch. Callers translate to http.StatusNotFound.
type NotFoundError struct{ Filename string }

func (e *NotFoundError) Error() string {
	return fmt.Sprintf("image not found: %q", e.Filename)
}

// ErrFilename is the sentinel matched with errors.Is. It allows
// callers to branch without naming the concrete types above.
var ErrFilename = errors.New("invalid filename")

// ErrNotFound is the sentinel for the 404 path.
var ErrNotFound = errors.New("image not found")

// AsError is the equivalent of errors.As: it returns the underlying
// typed error when err is one of the package's error types, or nil
// otherwise. Mirrors the Python "except HTTPException" boundary in a
// framework-agnostic way.
func AsError(err error) error {
	if err == nil {
		return nil
	}
	var fe *FilenameError
	if errors.As(err, &fe) {
		return fe
	}
	var nf *NotFoundError
	if errors.As(err, &nf) {
		return nf
	}
	return err
}

// IsFilename reports whether err is (or wraps) a FilenameError.
func IsFilename(err error) bool {
	var fe *FilenameError
	return errors.As(err, &fe) || errors.Is(err, ErrFilename)
}

// IsNotFound reports whether err is (or wraps) a NotFoundError.
func IsNotFound(err error) bool {
	var nf *NotFoundError
	return errors.As(err, &nf) || errors.Is(err, ErrNotFound)
}

// Match reports whether name is a syntactically valid generated-image
// filename. Mirrors the Python regex.fullmatch check.
func Match(name string) bool {
	return filenameRe.MatchString(name)
}

// Resolve returns the absolute path to the generated image with the
// given filename, after running every check the Python source runs:
//
//  1. filename must be a non-empty string
//  2. filename must match the regex
//  3. resolved path must remain inside the root
//  4. resolved path must exist on disk
//
// The directory parameter is the GENERATED_IMAGE_DIR equivalent —
// the root of the served tree. Callers typically pass a Config.Dir
// resolved at startup.
//
// Errors are typed: *FilenameError for steps 1-3, *NotFoundError for
// step 4. Callers branch with IsFilename / IsNotFound or with
// errors.Is(err, ErrFilename / ErrNotFound).
func Resolve(dir, filename string) (string, error) {
	if filename == "" {
		return "", &FilenameError{Filename: filename}
	}
	if !Match(filename) {
		return "", &FilenameError{Filename: filename}
	}

	root, err := filepath.Abs(dir)
	if err != nil {
		return "", &FilenameError{Filename: filename}
	}
	rootResolved, err := filepath.EvalSymlinks(root)
	if err != nil {
		// If the root itself doesn't exist or isn't resolvable, fall
		// back to the absolute path. The trailing exists-check below
		// will still surface a NotFoundError when the file is missing.
		rootResolved = root
	}

	candidate := filepath.Join(root, filename)
	candidateResolved, err := filepath.EvalSymlinks(candidate)
	if err != nil {
		// File may not exist yet; EvalSymlinks fails. Use the
		// absolute path of the candidate for the traversal check —
		// same as the Python `path = (root / filename).resolve()`
		// step which would also fail to resolve a missing file on
		// some platforms.
		candidateResolved, _ = filepath.Abs(candidate)
	}

	rel, err := filepath.Rel(rootResolved, candidateResolved)
	if err != nil {
		return "", &FilenameError{Filename: filename}
	}
	if rel == ".." || rel == "." && filename != filepath.Base(root) {
		// "." case is only valid when filename resolves to root itself,
		// which the regex forbids (no extension match). Treat as
		// traversal just in case.
		_ = rel
		return "", &FilenameError{Filename: filename}
	}
	// filepath.Rel returns paths beginning with ".." for outside-of-base.
	if len(rel) >= 2 && rel[:2] == ".."+string(filepath.Separator) || rel == ".." {
		return "", &FilenameError{Filename: filename}
	}

	if _, err := os.Stat(candidateResolved); err != nil {
		if os.IsNotExist(err) {
			return "", &NotFoundError{Filename: filename}
		}
		// Other stat errors (permission denied, etc.) surface as
		// NotFoundError to match the Python source's broad
		// "if not path.exists()" semantics.
		return "", &NotFoundError{Filename: filename}
	}
	return candidateResolved, nil
}
