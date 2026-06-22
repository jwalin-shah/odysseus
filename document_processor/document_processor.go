// Package document_processor is a Go port of the pure-text-processing
// utilities from src/document_processor.py.
//
// Scope: this package implements the text-file path, the inline-attachment
// truncation/fitting helpers, and the PDF-marker stripper. PDF, image, and
// Office paths depend on heavy Python-only dependencies (pypdf, PIL,
// markitdown, an admin-configured VL model) and are deliberately not
// ported — callers that need them should fall through to the Python module
// or the future Go equivalents.
//
// Encoding behavior note: the Python version reads the file as UTF-8 and
// falls back to charset_normalizer.detect on UnicodeDecodeError. The Go
// port mirrors the intent without dragging in a C-backed charset detector:
// it tries UTF-8 first and, if the bytes are not valid UTF-8, replaces
// invalid sequences with the Unicode replacement character (U+FFFD). This
// is the standard Go idiom for "I don't know the encoding" and produces
// well-formed UTF-8 that downstream code can handle uniformly.
package document_processor

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

// MaxInlineAttachmentChars is the shared per-turn budget for inline
// attachment bodies. Mirrors MAX_INLINE_ATTACHMENT_CHARS in
// src/document_processor.py.
const MaxInlineAttachmentChars = 24000

// MinInlineAttachmentSlice is the smallest chunk of budget a single
// attachment is allowed to consume before we drop it to a placeholder
// instead. Mirrors MIN_INLINE_ATTACHMENT_SLICE in src/document_processor.py.
const MinInlineAttachmentSlice = 500

// PDFContentMarker is the prefix that _process_pdf prepends to extracted
// text. Exported so callers can build the marker or detect it without
// hand-copying the literal — see StripPDFContentMarker.
const PDFContentMarker = "\n\n[PDF content]:"

// textExtensions is the set of extensions _is_text_file accepts.
// Defined as a package-level set so IsTextFile is a constant-time lookup
// rather than the linear any() the Python source uses.
var textExtensions = map[string]bool{
	".txt":  true,
	".py":   true,
	".html": true,
	".htm":  true,
	".md":   true,
	".json": true,
	".csv":  true,
	".log":  true,
	".js":   true,
	".nix":  true,
}

// languageMap mirrors the language_map dict in _process_text_file.
// Extensions are stored with the leading dot and lowercase, matching the
// key produced by strings.ToLower(filepath.Ext(path)).
var languageMap = map[string]string{
	".py":   "python",
	".js":   "javascript",
	".html": "html",
	".css":  "css",
	".json": "json",
	".md":   "markdown",
	".txt":  "text",
	".csv":  "csv",
	".log":  "log",
	".sh":   "bash",
	".bash": "bash",
	".nix":  "nix",
	".yml":  "yaml",
	".yaml": "yaml",
	".xml":  "xml",
	".sql":  "sql",
	".cpp":  "cpp",
	".c":    "c",
	".java": "java",
	".go":   "go",
	".rs":   "rust",
	".php":  "php",
	".rb":   "ruby",
	".ts":   "typescript",
	".jsx":  "javascript",
	".tsx":  "typescript",
}

// codeExtensions is the set of extensions that get the fenced code-block
// treatment in ProcessTextFile. Matches the Python code_extensions set
// exactly.
var codeExtensions = map[string]bool{
	".py":   true,
	".js":   true,
	".html": true,
	".css":  true,
	".json": true,
	".md":   true,
	".sh":   true,
	".bash": true,
	".nix":  true,
	".yml":  true,
	".yaml": true,
	".xml":  true,
	".sql":  true,
	".cpp":  true,
	".c":    true,
	".java": true,
	".go":   true,
	".rs":   true,
	".php":  true,
	".rb":   true,
	".ts":   true,
	".jsx":  true,
	".tsx":  true,
}

// ErrNotTextFile is returned by ProcessTextFile when the path's extension
// is not in the text-extension allow-list. The CLI surfaces this as a
// clean refusal rather than a panic or a silent empty body.
var ErrNotTextFile = errors.New("document_processor: not a recognised text extension")

// IsTextFile reports whether path has one of the recognised text
// extensions. The match is case-insensitive (Go's filepath.Ext preserves
// case; we lowercase before lookup). Paths without an extension return
// false.
func IsTextFile(path string) bool {
	return textExtensions[strings.ToLower(filepath.Ext(path))]
}

// IsCodeExtension reports whether ext is one of the extensions rendered
// as a fenced code block by ProcessTextFile. The argument should include
// the leading dot (".py", ".go"); comparison is case-insensitive.
func IsCodeExtension(ext string) bool {
	return codeExtensions[strings.ToLower(ext)]
}

// LanguageFor returns the syntax-highlighting language id used in the
// fenced code block (or "text" for unrecognised extensions). ext should
// include the leading dot.
func LanguageFor(path string) string {
	if lang, ok := languageMap[strings.ToLower(filepath.Ext(path))]; ok {
		return lang
	}
	return "text"
}

// readAll reads the file at path, returning a UTF-8 string. If the file's
// bytes are not valid UTF-8, invalid sequences are replaced with U+FFFD —
// see the package godoc for the rationale. A read failure bubbles up as
// the underlying os error so callers can decide how to handle it.
func readAll(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if utf8.Valid(data) {
		return string(data), nil
	}
	// Replace invalid sequences with the Unicode replacement character.
	// strings.ToValidUTF8 treats the empty string as "keep as-is", so the
	// third argument (the replacement) is what gets substituted in.
	return strings.ToValidUTF8(string(data), "�"), nil
}

// formatHeader builds the "=== File: name ===\n[Type: lang, Lines: N,
// Size: S bytes]" header that leads every ProcessTextFile result. The
// size string mirrors Python's f"{file_size:,}" — comma-grouped thousands
// using the same "," separator.
func formatHeader(filename, language string, lines int, sizeBytes int64) string {
	var sizeStr string
	if sizeBytes < 0 {
		sizeStr = "unknown"
	} else {
		sizeStr = humanInt(sizeBytes)
	}
	return fmt.Sprintf("\n=== File: %s ===\n[Type: %s, Lines: %d, Size: %s bytes]",
		filename, language, lines, sizeStr)
}

// humanInt formats n with comma-grouped thousands. Matches Python's
// f"{n:,}" behavior exactly for non-negative integers.
func humanInt(n int64) string {
	if n == 0 {
		return "0"
	}
	negative := n < 0
	if negative {
		n = -n
	}
	digits := []byte{}
	for n > 0 {
		// Build reversed digit groups of 3 with commas.
		// We push 3 digits then a comma, then the next 3, etc.
		group := 3
		for n > 0 && group > 0 {
			digits = append(digits, byte('0'+n%10))
			n /= 10
			group--
		}
		if n > 0 {
			digits = append(digits, ',')
		}
	}
	if negative {
		digits = append(digits, '-')
	}
	// Reverse in place.
	for i, j := 0, len(digits)-1; i < j; i, j = i+1, j-1 {
		digits[i], digits[j] = digits[j], digits[i]
	}
	return string(digits)
}

// truncateToNewline truncates content down to maxLen, searching forward up
// to 100 characters for a newline (and falling back to a backward search
// if no forward newline exists). It returns the truncated content and a
// bool indicating whether truncation actually happened.
//
// The algorithm mirrors the Python loop exactly: if maxLen is beyond the
// content length, no truncation is performed.
func truncateToNewline(content string, maxLen int) (string, bool) {
	if len(content) <= maxLen {
		return content, false
	}
	truncationPoint := maxLen
	truncated := false

	// Forward search: up to 100 chars ahead of maxLen, or up to the end
	// of content if that is closer.
	forwardBudget := 100
	if remaining := len(content) - maxLen; remaining < forwardBudget {
		forwardBudget = remaining
	}
	for i := 0; i < forwardBudget; i++ {
		if truncationPoint+i >= len(content) {
			break
		}
		if content[truncationPoint+i] == '\n' {
			truncationPoint += i
			truncated = true
			break
		}
	}

	if !truncated {
		// Backward search: up to 100 chars behind the truncation point.
		backBudget := 100
		if truncationPoint < backBudget {
			backBudget = truncationPoint
		}
		for i := 0; i < backBudget; i++ {
			if content[truncationPoint-i] == '\n' {
				truncationPoint -= i
				truncated = true
				break
			}
		}
	}

	// Python sets truncated=True unconditionally after the loops even if no
	// newline was found; the resulting content is just content[:maxLen].
	return content[:truncationPoint], true
}

// ProcessTextFile reads the file at path and returns the formatted,
// possibly-truncated, header + body string. Behaviour matches
// _process_text_file in src/document_processor.py:
//
//   - Language is chosen from the language_map; unknown extensions render
//     as "text".
//   - .log files cap at 10_000 chars; everything else at 30_000.
//   - Truncation snaps to the nearest newline (within 100 chars) and
//     appends "[Truncated]".
//   - Code extensions render inside a fenced ```lang block; everything
//     else renders as raw content under the header.
//
// Returns ErrNotTextFile when the extension is not on the text allow-list.
// Returns a plain error (not a banner) on read failure — the Python module
// embeds the error in the result string, but the Go port keeps the error
// boundary clean so callers can decide between surfacing it or downgrading
// it to a placeholder.
func ProcessTextFile(path string) (string, error) {
	if !IsTextFile(path) {
		return "", fmt.Errorf("%w: %s", ErrNotTextFile, filepath.Ext(path))
	}

	filename := filepath.Base(path)
	ext := strings.ToLower(filepath.Ext(path))
	language := LanguageFor(path)
	maxLen := 30000
	if ext == ".log" {
		maxLen = 10000
	}

	content, err := readAll(path)
	if err != nil {
		return "", fmt.Errorf("read %s: %w", path, err)
	}

	var fileSize int64 = -1
	if info, statErr := os.Stat(path); statErr == nil {
		fileSize = info.Size()
	}

	lines := strings.Split(content, "\n")
	lineCount := len(lines)

	content, truncated := truncateToNewline(content, maxLen)

	header := formatHeader(filename, language, lineCount, fileSize)

	if IsCodeExtension(ext) {
		block := "```" + language + "\n" + content
		if truncated {
			block += "\n[Truncated]"
		}
		block += "\n```"
		return header + "\n\n" + block, nil
	}

	result := header + "\n\n" + content
	if truncated {
		result += "\n[Truncated]"
	}
	return result, nil
}

// StripPDFContentMarker removes the leading PDFContentMarker prefix that
// _process_pdf prepends. The Python implementation deliberately uses
// str.removeprefix rather than str.lstrip: lstrip treats its argument as
// a SET of characters and would chew into the following page text (e.g.
// it would strip the leading 't' from "to the board" because 't' and 'o'
// appear in the marker's character set). This is a 1-liner over
// strings.TrimPrefix for the same reason.
func StripPDFContentMarker(text string) string {
	return strings.TrimSpace(strings.TrimPrefix(text, PDFContentMarker))
}

// TruncateInline caps inline document text so a huge file can't blow the
// model's context. Mirrors _truncate_inline. The default limit is 15_000
// to match the Python default, but callers can pass a different limit
// (e.g. ProcessTextFile's 30_000) when they want a longer inline copy.
//
// Returns the (possibly capped) body and a marker string. The marker is
// empty when no truncation happened.
func TruncateInline(text string, limit int) (string, string) {
	text = strings.TrimSpace(text)
	if len(text) > limit {
		return text[:limit], "\n[…truncated for inline context.]"
	}
	return text, ""
}

// FitInlineAttachmentText fits a piece of extracted attachment text into
// the shared per-turn budget. Mirrors _fit_inline_attachment_text.
//
// Behaviour:
//   - If the text already fits, it is returned unchanged and the new
//     remaining budget is returned.
//   - If it does not fit AND remaining is below MinInlineAttachmentSlice,
//     a placeholder banner is returned and the remaining budget drops to
//     zero (the attachment is fully accounted for in the budget).
//   - Otherwise the text is truncated to `remaining` characters and a
//     marker explaining the cap is appended; the remaining budget drops
//     to zero.
func FitInlineAttachmentText(text string, remaining int, displayName string) (string, int) {
	if len(text) <= remaining {
		return text, remaining - len(text)
	}

	name := filepath.Base(displayName)
	if name == "" || name == "." || name == "/" {
		name = "attachment"
	}

	if remaining < MinInlineAttachmentSlice {
		return fmt.Sprintf(
			"\n\n[Attachment omitted from inline context: %s. "+
				"The %s-character shared inline "+
				"attachment budget was already used by earlier attachments. Ask "+
				"to inspect this file specifically if more detail is needed.]",
			name, humanInt(int64(MaxInlineAttachmentChars)),
		), 0
	}

	marker := fmt.Sprintf(
		"\n\n[Attachment content truncated: %s. "+
			"Only %s characters of this attachment fit within "+
			"the %s-character shared inline "+
			"attachment budget. Ask to inspect this file specifically if more "+
			"detail is needed.]",
		name, humanInt(int64(remaining)), humanInt(int64(MaxInlineAttachmentChars)),
	)
	return text[:remaining] + marker, 0
}
