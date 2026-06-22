package markitdown_runtime

import (
	"archive/zip"
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"strings"
)

// wordNS is the WordprocessingML 2006 namespace used for <w:p> and <w:t>.
const wordNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

// ExtractDocxNative walks word/document.xml inside a .docx (a zip archive)
// and concatenates the text of each <w:p> paragraph. Returns the joined
// text on success, or ("", err) on any I/O / parse / format failure.
//
// Mirrors the Python `_extract_docx_native`: missing zip entry, bad zip,
// missing word/document.xml, malformed XML, or an unparseable root all
// surface as an error so Convert can downgrade to "empty result + log".
func ExtractDocxNative(path string) (string, error) {
	zr, err := zip.OpenReader(path)
	if err != nil {
		return "", fmt.Errorf("open zip: %w", err)
	}
	defer zr.Close()

	var docXML []byte
	for _, f := range zr.File {
		if f.Name == "word/document.xml" {
			rc, err := f.Open()
			if err != nil {
				return "", fmt.Errorf("open word/document.xml: %w", err)
			}
			data, err := io.ReadAll(rc)
			rc.Close()
			if err != nil {
				return "", fmt.Errorf("read word/document.xml: %w", err)
			}
			docXML = data
			break
		}
	}
	if docXML == nil {
		return "", errors.New("word/document.xml not found in zip")
	}

	paragraphs, err := parseWordParagraphs(docXML)
	if err != nil {
		return "", err
	}
	if len(paragraphs) == 0 {
		return "", nil
	}
	return strings.Join(paragraphs, "\n\n"), nil
}

// parseWordParagraphs extracts non-empty paragraph strings from a
// word/document.xml payload. The WordprocessingML schema nests <w:t> runs
// under <w:r> under <w:p>, so we walk every node and group <w:t> text
// fragments by their enclosing <w:p>.
func parseWordParagraphs(data []byte) ([]string, error) {
	dec := xml.NewDecoder(bytes.NewReader(data))
	var (
		paragraphs  []string
		current     []string
		inParagraph bool
	)
	for {
		tok, err := dec.Token()
		if err != nil {
			if errors.Is(err, io.EOF) {
				break
			}
			return nil, fmt.Errorf("decode word/document.xml: %w", err)
		}
		switch t := tok.(type) {
		case xml.StartElement:
			switch {
			case t.Name.Space == wordNS && t.Name.Local == "p":
				inParagraph = true
				current = current[:0]
			case inParagraph && t.Name.Space == wordNS && t.Name.Local == "t":
				var text string
				if err := dec.DecodeElement(&text, &t); err != nil {
					return nil, fmt.Errorf("decode w:t: %w", err)
				}
				current = append(current, text)
			}
		case xml.EndElement:
			if inParagraph && t.Name.Space == wordNS && t.Name.Local == "p" {
				line := strings.TrimSpace(strings.Join(current, ""))
				if line != "" {
					paragraphs = append(paragraphs, line)
				}
				inParagraph = false
			}
		}
	}
	return paragraphs, nil
}
