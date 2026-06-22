// Command document_actions is a small demo binary that exercises the
// document_actions package end-to-end. It accepts flags for an owner name
// and a JSON file of seed documents, then runs the tidy pass and prints
// the resulting report.
//
// Usage:
//
//	document_actions -owner alice -docs docs.json
//
// Where docs.json is an array of objects with id, owner, title, content,
// created_at (RFC3339), updated_at (RFC3339, optional). Use -example to
// generate a small in-memory corpus instead of reading a file.
package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/odysseus/odysseus/document_actions"
)

// docJSON is the on-disk shape of a seed document. Times are RFC3339 and
// optional (pass null or omit to mean "no timestamp").
type docJSON struct {
	ID        string  `json:"id"`
	Owner     string  `json:"owner"`
	Title     string  `json:"title"`
	Content   string  `json:"content"`
	CreatedAt *string `json:"created_at,omitempty"`
	UpdatedAt *string `json:"updated_at,omitempty"`
}

func parseTimePtr(p *string) *time.Time {
	if p == nil || *p == "" {
		return nil
	}
	t, err := time.Parse(time.RFC3339, *p)
	if err != nil {
		return nil
	}
	return &t
}

func main() {
	owner := flag.String("owner", "", "owner to scope the tidy pass to (empty = all docs)")
	path := flag.String("docs", "", "path to a JSON file of seed documents")
	example := flag.Bool("example", false, "use a built-in example corpus instead of -docs")
	verbose := flag.Bool("v", false, "print the full TidyReport")
	flag.Parse()

	var seed []document_actions.DocumentView

	switch {
	case *example:
		seed = exampleCorpus()
	case *path != "":
		raw, err := os.ReadFile(*path)
		if err != nil {
			log.Fatalf("read %s: %v", *path, err)
		}
		var items []docJSON
		if err := json.Unmarshal(raw, &items); err != nil {
			log.Fatalf("parse %s: %v", *path, err)
		}
		for _, it := range items {
			seed = append(seed, &document_actions.Document{
				ID:             it.ID,
				Owner:          it.Owner,
				Title:          it.Title,
				CurrentContent: it.Content,
				CreatedAt:      parseTimePtr(it.CreatedAt),
				UpdatedAt:      parseTimePtr(it.UpdatedAt),
			})
		}
	default:
		flag.Usage()
		fmt.Fprintln(os.Stderr, "\neither -docs <file.json> or -example is required")
		os.Exit(2)
	}

	// If owner was set, filter the in-memory seed (mirrors the SQL
	// `Document.owner == owner` clause from the Python original).
	if *owner != "" {
		filtered := seed[:0]
		for _, d := range seed {
			if d.GetOwner() == *owner {
				filtered = append(filtered, d)
			}
		}
		seed = filtered
	}

	report, err := document_actions.RunDocumentTidy(seed)
	switch {
	case err != nil:
		// TaskNoop is a normal outcome — surface a friendly message and
		// exit 0 so the demo is usable from a shell loop.
		if errors.Is(err, document_actions.ErrTaskNoop) {
			fmt.Println(err.Error())
			return
		}
		log.Fatalf("tidy: %v", err)
	}

	fmt.Printf("deleted=%d kept=%d\n", len(report.Deleted), len(report.Kept))
	if len(report.Examples) > 0 {
		fmt.Println("examples:")
		for _, e := range report.Examples {
			fmt.Printf("  - %s\n", e)
		}
	}
	if *verbose {
		for _, k := range report.Kept {
			fmt.Printf("kept: id=%s title=%q\n", k.GetID(), k.GetTitle())
		}
		for _, d := range report.Deleted {
			fmt.Printf("deleted: id=%s reason=%q\n", d.Doc.GetID(), d.Reason)
		}
	}
}
