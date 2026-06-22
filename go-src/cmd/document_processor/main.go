// Command document_processor is the demo binary for the document_processor
// package. It exercises the public surface end-to-end: it creates a
// scratch upload directory, writes a small text attachment, runs the
// language detection / inline-truncation pipeline, and prints the result.
//
// Usage:
//
//	document_processor [--text="Hello world"] [--budget=24000] [--workdir=/tmp/dp]
//
// All flags are optional. The binary never touches the network.
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/odysseus/odysseus/document_processor"
)

func main() {
	text := flag.String("text", "Summary of the attached document:", "user message text")
	budget := flag.Int("budget", document_processor.MaxInlineAttachmentChars, "override the inline attachment budget for the demo (1..MaxInlineAttachmentChars)")
	workdir := flag.String("workdir", "", "scratch upload directory; defaults to a fresh temp dir")
	flag.Parse()

	if *budget <= 0 || *budget > document_processor.MaxInlineAttachmentChars {
		fmt.Fprintf(os.Stderr, "budget must be between 1 and %d\n", document_processor.MaxInlineAttachmentChars)
		os.Exit(2)
	}

	dir := *workdir
	if dir == "" {
		var err error
		dir, err = os.MkdirTemp("", "document-processor-demo-")
		if err != nil {
			log.Fatalf("create workdir: %v", err)
		}
		defer os.RemoveAll(dir)
	}

	// Write a small text file and a fake "image" (zero bytes is fine — the
	// demo only exercises the routing branches, not the real encoders).
	txtPath := filepath.Join(dir, "notes.txt")
	if err := os.WriteFile(txtPath, []byte("hello world\n"), 0o600); err != nil {
		log.Fatalf("write notes.txt: %v", err)
	}

	handler := &demoHandler{root: dir, txtPath: txtPath}

	docs := document_processor.AutoOpenedDoc{}
	autoOpened := []document_processor.AutoOpenedDoc{}

	result := document_processor.BuildUserContent(document_processor.BuildUserContentInput{
		Text:            *text,
		AttachmentIDs:   []string{"notes", "img1"},
		UploadHandler:   handler,
		AutoOpenedDocs:  &autoOpened,
		DocumentHandler: &demoDocHandler{root: dir},
		Owner:           "demo-user",
		ResolvedUploads: map[string]document_processor.UploadInfo{
			"notes": {Path: txtPath, Name: "notes.txt", Mime: "text/plain"},
			"img1":  {Path: filepath.Join(dir, "missing.png"), Name: "missing.png", Mime: "image/png"},
		},
	})

	fmt.Println("=== document_processor demo ===")
	fmt.Printf("workdir:           %s\n", dir)
	fmt.Printf("inline budget:     %d chars (default %d)\n", *budget, document_processor.MaxInlineAttachmentChars)
	fmt.Printf("text-file cap:     30000 chars (10000 for .log)\n")
	fmt.Printf("PDF marker:        %q\n", document_processor.PDFContentMarker)
	fmt.Printf("strip marker:      %q\n", document_processor.StripPDFContentMarker(document_processor.PDFContentMarker+"body"))
	fmt.Printf("VL error sentinel: %v\n", document_processor.ErrNoVisionModel)
	fmt.Println("--- BuildUserContent result ---")

	switch v := result.(type) {
	case string:
		fmt.Println(v)
	case []document_processor.ContentPart:
		for i, p := range v {
			fmt.Printf("[%d] %v\n", i, p)
		}
	default:
		fmt.Printf("unexpected result type %T: %v\n", v, v)
	}

	_ = docs
}

// demoHandler is a tiny UploadHandler for the binary's end-to-end demo.
type demoHandler struct {
	root    string
	txtPath string
}

func (h *demoHandler) ResolveUpload(_, _ string) (document_processor.UploadInfo, bool) {
	return document_processor.UploadInfo{}, false
}
func (h *demoHandler) IsImageFile(name, mime string) bool {
	return mime == "image/png" || mime == "image/jpeg"
}
func (h *demoHandler) IsAudioFile(name, mime string) bool {
	return mime == "audio/mpeg" || mime == "audio/wav"
}
func (h *demoHandler) IsDocumentFile(name, mime string) bool {
	return mime != "" && (mime == "application/pdf" || mime == "text/plain" ||
		mime == "application/msword" || mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
}
func (h *demoHandler) InsideBaseDir(path string) bool {
	rel, err := filepath.Rel(h.root, path)
	return err == nil && !filepath.IsAbs(rel) && rel[:1] != ".."
}

// demoDocHandler renders a small inline body. Real binaries wire this to
// the PDF/Office pipelines.
type demoDocHandler struct {
	root string
}

func (d *demoDocHandler) HandleDocument(path, displayName, mime, sessionID, owner string, autoOpened *[]document_processor.AutoOpenedDoc) string {
	body, _ := os.ReadFile(path)
	return fmt.Sprintf("\n\n[Document content — %s]:\n%s", displayName, string(body))
}
