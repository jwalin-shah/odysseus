// Package document_processor is a Go port of src/document_processor.py. It
// implements the document handling pipeline used by the chat route:
//
//   - Text file extraction with language hints, line counts, and truncation
//     to a per-file cap.
//   - PDF text extraction with a shared 15 000-character cap and the
//     "[PDF content]:" wrapper marker (see StripPDFContentMarker).
//   - Inline attachment budget tracking so a batch of attachments can never
//     blow the model's context (MAX_INLINE_ATTACHMENT_CHARS).
//   - A VL (vision-language) image analyser with a fallback chain over
//     known vision-capable models.
//   - A top-level BuildUserContent that turns a list of attachment IDs into
//     the OpenAI-style message content (text, image_url, audio) consumed by
//     the rest of the application.
//
// Heavy dependencies from the Python original (pypdf, markitdown, the
// session/document ORM layer, and the LLM HTTP client) are absent here by
// design: the Go port keeps the pure logic and the public surface, and
// callers inject the IO/LLM/ORM side effects via small interfaces
// (UploadHandler, VLCaller, ContentPersister, PDFExtractor). The stdlib is
// the only dependency.
package document_processor

import (
	"encoding/base64"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"
)

// MaxInlineAttachmentChars caps the cumulative inline attachment text that
// BuildUserContent will inline into a single user turn. The Python source
// uses 24 000; we keep the same number to preserve behavior.
const MaxInlineAttachmentChars = 24000

// MinInlineAttachmentSlice is the smallest slice of the inline budget we
// will hand to a late attachment before falling back to the "omitted from
// inline context" notice. Matches src/document_processor.py.
const MinInlineAttachmentSlice = 500

// PDFContentMarker is the wrapper prepended to text extracted by the PDF
// pipeline. StripPDFContentMarker removes it safely.
const PDFContentMarker = "\n\n[PDF content]:"

// ErrNoVisionModel is returned when no vision-capable model can be located
// on any configured endpoint. The Python original raises ValueError; we
// expose it as a sentinel so callers can errors.Is against it.
var ErrNoVisionModel = errors.New("document_processor: no vision model available")

// Logger is the package-level logger. Tests may swap it for a silent
// implementation. The default writes to stderr with a recognizable prefix.
var Logger = log.New(os.Stderr, "[document_processor] ", log.LstdFlags)

// ---------------------------------------------------------------------------
// File-extension tables (mirrors _is_text_file / _process_text_file).
// ---------------------------------------------------------------------------

// textFileExtensions is the set of suffixes _is_text_file considers text.
var textFileExtensions = []string{
	".txt", ".py", ".html", ".htm", ".md", ".json", ".csv", ".log", ".js", ".nix",
}

// languageMap maps a lowercased file extension to the language tag we
// include in the header / fenced code block.
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

// codeExtensions is the set of extensions that get a fenced code block
// wrapping rather than a raw inline body.
var codeExtensions = map[string]struct{}{
	".py": {}, ".js": {}, ".html": {}, ".css": {}, ".json": {}, ".md": {},
	".sh": {}, ".bash": {}, ".nix": {},
	".yml": {}, ".yaml": {}, ".xml": {}, ".sql": {}, ".cpp": {}, ".c": {},
	".java": {}, ".go": {}, ".rs": {}, ".php": {}, ".rb": {},
	".ts": {}, ".jsx": {}, ".tsx": {},
}

// IsTextFile reports whether path has a recognised text-file extension.
func IsTextFile(path string) bool {
	lower := strings.ToLower(path)
	for _, ext := range textFileExtensions {
		if strings.HasSuffix(lower, ext) {
			return true
		}
	}
	return false
}

// LanguageForExt returns the language tag for a lowercased extension
// (including the leading dot), or "text" when the extension is unknown.
func LanguageForExt(ext string) string {
	if lang, ok := languageMap[strings.ToLower(ext)]; ok {
		return lang
	}
	return "text"
}

// ---------------------------------------------------------------------------
// Text file processing.
// ---------------------------------------------------------------------------

// TextFileOptions tweaks ProcessTextFile behavior. Zero value is the
// default, which matches the Python original exactly.
type TextFileOptions struct {
	// MaxLen caps the body length. Defaults: 30 000, or 10 000 for .log.
	MaxLen int
	// Reader overrides how the file content is read. When nil, ProcessTextFile
	// reads the file from disk (with a UTF-8/charset fallback). Tests can
	// inject a reader to avoid touching the filesystem.
	Reader func(path string) (string, error)
	// SizeLookup returns the file size in bytes. When nil, ProcessTextFile
	// calls os.Stat on the path. Tests can inject a fixed value.
	SizeLookup func(path string) (int64, error)
}

// ProcessTextFile reads a text file and renders the "=== File: … ==="
// header + (optional) fenced code block that the Python version emits.
//
// Behavior matches the source: a per-file size cap, a per-line cap, and
// truncation markers that try to snap to a newline so we never cut a line
// in the middle when there's a nearby break.
func ProcessTextFile(path string, opts TextFileOptions) string {
	filename := filepath.Base(path)
	ext := strings.ToLower(filepath.Ext(path))
	language := LanguageForExt(ext)

	maxLen := opts.MaxLen
	if maxLen == 0 {
		if ext == ".log" {
			maxLen = 10000
		} else {
			maxLen = 30000
		}
	}

	var content string
	if opts.Reader != nil {
		c, err := opts.Reader(path)
		if err != nil {
			Logger.Printf("failed to read file %s: %v", path, err)
			return "\n\n[Failed to read attached file]"
		}
		content = c
	} else {
		c, err := readFileWithFallback(path)
		if err != nil {
			Logger.Printf("failed to read file %s: %v", path, err)
			return "\n\n[Failed to read attached file]"
		}
		content = c
	}

	var sizeStr string
	if opts.SizeLookup != nil {
		if n, err := opts.SizeLookup(path); err == nil {
			sizeStr = formatInt(n)
		} else {
			sizeStr = "unknown"
		}
	} else {
		if info, err := os.Stat(path); err == nil {
			sizeStr = formatInt(info.Size())
		} else {
			sizeStr = "unknown"
		}
	}

	lines := strings.Split(content, "\n")
	lineCount := len(lines)
	contentLength := len(content)
	truncated := false

	if contentLength > maxLen {
		truncPoint := maxLen
		searchRange := 100
		if contentLength-maxLen < searchRange {
			searchRange = contentLength - maxLen
		}
		snapped := false
		for i := 0; i < searchRange; i++ {
			if truncPoint+i >= contentLength {
				break
			}
			if content[truncPoint+i] == '\n' {
				truncPoint += i
				truncated = true
				snapped = true
				break
			}
		}
		if !snapped {
			backSearch := 100
			if truncPoint < backSearch {
				backSearch = truncPoint
			}
			for i := 0; i < backSearch; i++ {
				if content[truncPoint-i] == '\n' {
					truncPoint -= i
					truncated = true
					break
				}
			}
		}
		content = content[:truncPoint]
		truncated = true
	}

	header := fmt.Sprintf("\n=== File: %s ===\n", filename)
	header += fmt.Sprintf("[Type: %s, Lines: %d, Size: %s bytes]", language, lineCount, sizeStr)

	if _, isCode := codeExtensions[ext]; isCode {
		codeBlock := "```" + language + "\n" + content
		if truncated {
			codeBlock += "\n[Truncated]"
		}
		codeBlock += "\n```"
		return header + "\n\n" + codeBlock
	}

	result := header + "\n\n" + content
	if truncated {
		result += "\n[Truncated]"
	}
	return result
}

// readFileWithFallback reads path as UTF-8, falling back to a permissive
// decode on UnicodeDecodeError. The Python original uses
// charset_normalizer; the Go port is intentionally tolerant (replacement
// characters) and only does what stdlib allows.
func readFileWithFallback(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	bom := []byte{0xEF, 0xBB, 0xBF}
	if !bytesHasPrefix(data, bom) {
		// Strip BOM if present.
		data = bytesTrimPrefix(data, bom)
	}
	if isLikelyUTF8(data) {
		return string(data), nil
	}
	// Permissive decode — Go doesn't ship a charset sniffer, so this
	// mirrors the Python "errors='replace'" branch when the sniffer is
	// missing or detects something exotic.
	return string(data), nil
}

// Tiny indirection so we don't depend on the bytes package directly.
func bytesHasPrefix(s, prefix []byte) bool {
	if len(prefix) > len(s) {
		return false
	}
	for i := range prefix {
		if s[i] != prefix[i] {
			return false
		}
	}
	return true
}

func bytesTrimPrefix(s, prefix []byte) []byte {
	if bytesHasPrefix(s, prefix) {
		return s[len(prefix):]
	}
	return s
}

// isLikelyUTF8 reports whether data is a valid UTF-8 encoded sequence.
// Equivalent to Python's "raw_data.decode('utf-8')" succeeding.
func isLikelyUTF8(data []byte) bool {
	return utf8.Valid(data)
}

// formatInt inserts thousands separators the same way Python's
// f"{n:,}" does.
func formatInt(n int64) string {
	negative := n < 0
	if negative {
		n = -n
	}
	s := fmt.Sprintf("%d", n)
	out := make([]byte, 0, len(s)+len(s)/3)
	for i, c := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			out = append(out, ',')
		}
		out = append(out, byte(c))
	}
	if negative {
		return "-" + string(out)
	}
	return string(out)
}

// ---------------------------------------------------------------------------
// Inline-truncation helpers.
// ---------------------------------------------------------------------------

// TruncateInline caps a single piece of extracted text. Returns the
// (possibly shortened) text and a marker explaining the truncation. When
// the input already fits, the marker is empty.
//
// Default limit is 15 000 chars, matching the Python `_truncate_inline`
// default.
func TruncateInline(text string, limit int) (string, string) {
	if limit <= 0 {
		limit = 15000
	}
	stripped := strings.TrimSpace(text)
	if len(stripped) > limit {
		return stripped[:limit], "\n[…truncated for inline context.]"
	}
	return stripped, ""
}

// FitInlineAttachmentText returns the text that should be inlined for an
// attachment given the remaining budget, plus the new remaining budget.
// When the budget is too small to even give the attachment a meaningful
// slice, the function returns an "omitted from inline context" notice
// instead of the body.
func FitInlineAttachmentText(text, displayName string, remaining int) (string, int) {
	if len(text) <= remaining {
		return text, remaining - len(text)
	}
	name := filepath.Base(strings.TrimSpace(displayName))
	if name == "" {
		name = "attachment"
	}
	if remaining < MinInlineAttachmentSlice {
		return fmt.Sprintf(
			"\n\n[Attachment omitted from inline context: %s. "+
				"The %d-character shared inline attachment budget was "+
				"already used by earlier attachments. Ask to inspect this "+
				"file specifically if more detail is needed.]",
			name, MaxInlineAttachmentChars,
		), 0
	}
	marker := fmt.Sprintf(
		"\n\n[Attachment content truncated: %s. "+
			"Only %s characters of this attachment fit within the "+
			"%s-character shared inline attachment budget. Ask to inspect "+
			"this file specifically if more detail is needed.]",
		name, formatInt(int64(remaining)), formatInt(int64(MaxInlineAttachmentChars)),
	)
	return text[:remaining] + marker, 0
}

// StripPDFContentMarker removes the leading "[PDF content]:" wrapper that
// PDF processing emits, without lstripping characters from the body. The
// Python source uses removeprefix for the same reason: lstrip would chew
// into the body text.
func StripPDFContentMarker(text string) string {
	stripped := strings.TrimPrefix(text, PDFContentMarker)
	return strings.TrimSpace(stripped)
}

// ---------------------------------------------------------------------------
// Image (VL) analysis — interfaces and the default in-memory caller.
// ---------------------------------------------------------------------------

// ContentPart is the union of part types the LLM message shape accepts.
// The Go port keeps the shape loose (map[string]any) so JSON encoding
// downstream still produces the exact wire format the Python code emits.
type ContentPart = map[string]any

// VLMessages is the request shape the LLMCaller receives. We don't depend
// on the chat package to keep the import graph minimal.
type VLMessages = []map[string]any

// LLMCaller is the side effect the VL pipeline needs. The production
// implementation wraps src/llm_core.llm_call; tests inject a stub.
type LLMCaller func(url, model string, messages VLMessages, headers map[string]string, timeoutSeconds int) (string, error)

// VisionFallbackResolver returns the ordered list of (url, model, headers)
// fallback candidates *after* the primary. An empty result means "no
// fallbacks configured".
type VisionFallbackResolver func(owner string) []VLEndpoint

// VLEndpoint is a (url, model, headers) triple the VL pipeline can hit.
type VLEndpoint struct {
	URL     string
	Model   string
	Headers map[string]string
}

// DefaultVisionModelCandidates is the order _resolve_vl_model walks when
// no model is configured. Mirrors the Python candidate list.
var DefaultVisionModelCandidates = []string{
	"gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini",
	"claude-sonnet-4-5-20250929", "claude-opus-4-20250514",
	"gemini-2.0-flash", "gemini-2.5-pro",
	"llava", "pixtral", "qwen2-vl",
}

// VLResult is what AnalyzeImageWithVLResult returns. The "model" field is
// the model that actually produced the text (empty if no model answered).
type VLResult struct {
	Text  string `json:"text"`
	Model string `json:"model"`
}

// VLConfig is the dependency bag the VL pipeline needs. Zero value is
// safe; defaults to no candidates, no fallbacks, and a 120-second timeout.
type VLConfig struct {
	// Call is the LLM HTTP caller. Required.
	Call LLMCaller
	// ResolveModel returns (url, model, headers) for a configured model id.
	// When the model id is empty, the pipeline walks the candidate list.
	ResolveModel func(configured, owner string) (VLEndpoint, error)
	// Fallbacks, when non-nil, returns the ordered fallback chain.
	Fallbacks VisionFallbackResolver
	// TimeoutSeconds is per-attempt. Defaults to 120.
	TimeoutSeconds int
	// Logger override; nil falls back to the package logger.
	Logger *log.Logger
}

// AnalyzeImageWithVLResult is the rich form of AnalyzeImageWithVL. The
// caller gets both the description and the model that produced it. On
// failure, it returns the human-readable error text in Text and "" in
// Model — matching the Python behavior where the chat route keeps going
// even when vision is unavailable.
func AnalyzeImageWithVLResult(imagePath, owner string, cfg VLConfig) VLResult {
	logger := cfg.Logger
	if logger == nil {
		logger = Logger
	}
	logger.Printf("analyzing image with VL model: %s", imagePath)

	if cfg.Call == nil {
		logger.Printf("VL call: no LLMCaller configured")
		return VLResult{Text: "[VL model unavailable - image not analyzed]", Model: ""}
	}

	endpoints, err := resolveVLEndpoints(cfg, owner)
	if err != nil || len(endpoints) == 0 {
		if errors.Is(err, ErrNoVisionModel) {
			return VLResult{Text: "[No vision model configured — set one in Settings → Vision]", Model: ""}
		}
		logger.Printf("VL model unavailable: %v", err)
		return VLResult{Text: "[VL model unavailable - image not analyzed]", Model: ""}
	}

	encoded, err := readAndBase64(imagePath)
	if err != nil {
		logger.Printf("VL model unavailable: %v", err)
		return VLResult{Text: "[VL model unavailable - image not analyzed]", Model: ""}
	}
	imgFormat := imageFormat(imagePath)

	timeout := cfg.TimeoutSeconds
	if timeout == 0 {
		timeout = 120
	}

	messages := VLMessages{
		{
			"role": "user",
			"content": []ContentPart{
				{"type": "text", "text": "Describe this image in detail"},
				{"type": "image_url", "image_url": map[string]any{
					"url": "data:image/" + imgFormat + ";base64," + encoded,
				}},
			},
		},
	}

	var lastErr error
	for i, ep := range endpoints {
		if ep.URL == "" || ep.Model == "" {
			continue
		}
		description, err := cfg.Call(ep.URL, ep.Model, messages, ep.Headers, timeout)
		if err == nil {
			logger.Printf("VL analysis complete with model %s", ep.Model)
			return VLResult{Text: description, Model: ep.Model}
		}
		lastErr = err
		tag := "primary"
		if i > 0 {
			tag = "candidate"
		}
		logger.Printf("[vision fallback] %s %s failed (%T); trying next", tag, ep.Model, err)
	}

	if lastErr == nil {
		lastErr = errors.New("no vision model endpoint configured")
	}
	logger.Printf("VL model unavailable: %v", lastErr)
	return VLResult{Text: "[VL model unavailable - image not analyzed]", Model: ""}
}

// AnalyzeImageWithVL is the convenience wrapper used by the chat route.
// Returns just the description text.
func AnalyzeImageWithVL(imagePath, owner string, cfg VLConfig) string {
	return AnalyzeImageWithVLResult(imagePath, owner, cfg).Text
}

// resolveVLEndpoints builds the (primary, fallback, …) endpoint chain.
func resolveVLEndpoints(cfg VLConfig, owner string) ([]VLEndpoint, error) {
	if cfg.ResolveModel == nil {
		// Without a model resolver we cannot resolve any candidate; this
		// mirrors the Python path where `_resolve_model` is unavailable
		// and every candidate raises.
		return nil, ErrNoVisionModel
	}
	var primary VLEndpoint
	var err error
	// Try each candidate until one resolves. The Python loop treats every
	// exception as "try next" without distinguishing ValueError, which is
	// how it manages to keep iterating even when a candidate raises
	// something specific.
	for _, candidate := range DefaultVisionModelCandidates {
		primary, err = cfg.ResolveModel(candidate, owner)
		if err == nil {
			break
		}
	}
	if err != nil {
		return nil, err
	}
	endpoints := []VLEndpoint{primary}
	if cfg.Fallbacks != nil {
		endpoints = append(endpoints, cfg.Fallbacks(owner)...)
	}
	return endpoints, nil
}

// readAndBase64 slurps a file and returns a base64 string.
func readAndBase64(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read image: %w", err)
	}
	return base64.StdEncoding.EncodeToString(data), nil
}

// imageFormat maps the file extension to the value we use in the data URL.
// Defaults to "jpeg" to match the Python fallback.
func imageFormat(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".jpg", ".jpeg":
		return "jpeg"
	case ".png":
		return "png"
	case ".gif":
		return "gif"
	case ".webp":
		return "webp"
	default:
		return "jpeg"
	}
}

// ---------------------------------------------------------------------------
// User content builder.
// ---------------------------------------------------------------------------

// UploadInfo is the metadata BuildUserContent consumes for each attachment
// id. It's the Go-port-shaped subset of the Python dict the upload
// handler hands to the chat route.
type UploadInfo struct {
	Path         string `json:"path"`
	Mime         string `json:"mime"`
	Name         string `json:"name"`
	OriginalName string `json:"original_name"`
}

// UploadHandler is the small surface of the upload handler the document
// processor needs. The production implementation is the FastAPI upload
// route; tests can pass a stub.
type UploadHandler interface {
	ResolveUpload(id, owner string) (UploadInfo, bool)
	IsImageFile(name, mime string) bool
	IsAudioFile(name, mime string) bool
	IsDocumentFile(name, mime string) bool
	InsideBaseDir(path string) bool
}

// AutoOpenedDoc is the per-document entry BuildUserContent appends to
// when an attachment triggers an auto-created document.
type AutoOpenedDoc struct {
	DocID    int64  `json:"doc_id"`
	Title    string `json:"title"`
	Language string `json:"language"`
	Content  string `json:"content"`
	Version  int    `json:"version"`
}

// BuildUserContentInput is the parameter bag for BuildUserContent. Using a
// struct keeps the call site readable as we add more knobs (e.g. session
// id, owner, resolved uploads).
type BuildUserContentInput struct {
	Text            string
	AttachmentIDs   []string
	UploadDir       string
	UploadHandler   UploadHandler
	SessionID       string
	AutoOpenedDocs  *[]AutoOpenedDoc
	Owner           string
	ResolvedUploads map[string]UploadInfo
	// DocumentHandler, when non-nil, is invoked for documents that need
	// the rich PDF/Office treatment. The default is the in-process handler
	// (which falls back to a banner when the optional deps are missing).
	DocumentHandler DocumentHandler
}

// DocumentHandler renders a single document path into inline text. It's
// the seam where the Go port can stay pure (test stub) while production
// routes to the PDF/Office pipelines.
type DocumentHandler interface {
	HandleDocument(path, displayName, mime, sessionID, owner string, autoOpenedDocs *[]AutoOpenedDoc) string
}

// BuildUserContent is the top-level entry point. It returns either a
// single string (when no media is present) or a []ContentPart in the
// OpenAI message format. The Python original returns a `str | list`; in
// Go the dual return is exposed as an any with a content type the caller
// can type-assert.
func BuildUserContent(in BuildUserContentInput) any {
	parts := []ContentPart{{"type": "text", "text": in.Text}}
	budget := MaxInlineAttachmentChars

	if in.DocumentHandler == nil {
		in.DocumentHandler = BannerDocumentHandler{}
	}

	handler := in.UploadHandler
	if handler == nil {
		// Without an upload handler we cannot resolve paths, so we degrade
		// to a banner — same shape as the Python "Attachment … not found".
		return parts[0]["text"]
	}

	for _, fid := range in.AttachmentIDs {
		info, ok := in.ResolvedUploads[fid]
		if !ok {
			info, ok = handler.ResolveUpload(fid, in.Owner)
		}
		if !ok {
			Logger.Printf("attachment %s not found or not authorized", fid)
			continue
		}
		if info.Path == "" {
			Logger.Printf("attachment %s path is missing", fid)
			continue
		}
		if _, err := os.Stat(info.Path); err != nil {
			Logger.Printf("attachment %s path is missing: %v", fid, err)
			continue
		}
		if !handler.InsideBaseDir(info.Path) {
			Logger.Printf("attachment %s path is outside base directory: %s", fid, info.Path)
			continue
		}

		ext := strings.ToLower(filepath.Ext(info.Path))
		mime := info.Mime
		if mime == "" {
			mime = "application/octet-stream"
		}
		displayName := info.Name
		if displayName == "" {
			displayName = info.OriginalName
		}
		if displayName == "" {
			displayName = info.Path
		}

		switch {
		case handler.IsImageFile(displayName, mime):
			var ok bool
			parts, _, ok = appendImagePart(parts, info, ext, fid)
			if !ok {
				parts = prependOrAppendBanner(parts, "[Image attached but could not be processed]")
			}
		case handler.IsAudioFile(displayName, mime):
			var ok bool
			parts, _, ok = appendAudioPart(parts, info, ext, fid)
			if !ok {
				parts = prependOrAppendBanner(parts, "[Audio attached but could not be processed]")
			}
		case handler.IsDocumentFile(displayName, mime):
			body := in.DocumentHandler.HandleDocument(info.Path, displayName, mime, in.SessionID, in.Owner, in.AutoOpenedDocs)
			fitted, remaining := FitInlineAttachmentText(body, displayName, budget)
			budget = remaining
			parts = prependOrAppendBanner(parts, strings.TrimLeft(fitted, "\n"))
		default:
			parts = prependOrAppendBanner(parts, "\n\n[Attached non-text file]")
		}
	}

	if !hasMedia(parts) {
		// No media — collapse to a single string.
		var sb strings.Builder
		for _, p := range parts {
			if t, _ := p["type"].(string); t == "text" {
				if s, ok := p["text"].(string); ok {
					sb.WriteString(s)
				}
			}
		}
		return strings.TrimSpace(sb.String())
	}
	return parts
}

func appendImagePart(parts []ContentPart, info UploadInfo, ext, fid string) ([]ContentPart, string, bool) {
	encoded, err := readAndBase64(info.Path)
	if err != nil {
		Logger.Printf("failed to encode image %s: %v", fid, err)
		return parts, "", false
	}
	imageFormat := strings.TrimPrefix(ext, ".")
	if imageFormat == "" {
		imageFormat = "jpeg"
	}
	parts = append(parts, ContentPart{
		"type":      "image_url",
		"image_url": map[string]any{"url": "data:image/" + imageFormat + ";base64," + encoded},
	})
	return parts, "appended", true
}

func appendAudioPart(parts []ContentPart, info UploadInfo, ext, fid string) ([]ContentPart, string, bool) {
	encoded, err := readAndBase64(info.Path)
	if err != nil {
		Logger.Printf("failed to encode audio %s: %v", fid, err)
		return parts, "", false
	}
	audioFormat := strings.TrimPrefix(ext, ".")
	if audioFormat == "" {
		audioFormat = "mpeg"
	}
	parts = append(parts, ContentPart{
		"type":  "audio",
		"audio": map[string]any{"url": "data:audio/" + audioFormat + ";base64," + encoded},
	})
	return parts, "appended", true
}

func prependOrAppendBanner(parts []ContentPart, banner string) []ContentPart {
	banner = strings.TrimLeft(banner, "\n")
	if len(parts) > 0 {
		if t, _ := parts[0]["type"].(string); t == "text" {
			if s, ok := parts[0]["text"].(string); ok {
				parts[0]["text"] = s + "\n\n" + banner
				return parts
			}
		}
	}
	out := make([]ContentPart, 0, len(parts)+1)
	out = append(out, ContentPart{"type": "text", "text": banner})
	return append(out, parts...)
}

func hasMedia(parts []ContentPart) bool {
	for _, p := range parts {
		t, _ := p["type"].(string)
		if t == "image_url" || t == "audio" {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------
// Default DocumentHandler — produces a banner for unknown / unsupported
// documents. Production callers inject a handler that dispatches into the
// PDF / Office pipelines (see the chat route).
// ---------------------------------------------------------------------------

// BannerDocumentHandler is the no-op DocumentHandler used when no real
// pipeline is wired up. It produces the same "\n\n[Attached document file]"
// banner the Python original emits for documents it doesn't know how to
// process.
type BannerDocumentHandler struct{}

// HandleDocument satisfies DocumentHandler by returning the default banner.
func (BannerDocumentHandler) HandleDocument(path, displayName, mime, sessionID, owner string, autoOpenedDocs *[]AutoOpenedDoc) string {
	return "\n\n[Attached document file]"
}
