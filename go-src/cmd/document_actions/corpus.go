package main

import (
	"time"

	"github.com/odysseus/odysseus/document_actions"
)

// exampleCorpus returns a small fixture covering the four tidy outcomes:
//   - junk title                       -> deleted
//   - duplicate of an existing doc     -> deleted
//   - email reply-chain only           -> deleted
//   - short legitimate note            -> kept
func exampleCorpus() []document_actions.DocumentView {
	mk := func(id, owner, title, body string, created string) *document_actions.Document {
		ts, _ := time.Parse(time.RFC3339, created)
		return &document_actions.Document{
			ID: id, Owner: owner, Title: title, CurrentContent: body,
			CreatedAt: &ts, UpdatedAt: &ts,
		}
	}
	body := "Today I wrote the document_actions Go port. It mirrors the Python helper that scrubs junk and duplicate documents from the library."
	return []document_actions.DocumentView{
		mk("1", "alice", "test", "anything goes", "2026-06-01T09:00:00Z"),
		mk("2", "alice", "My Report", body, "2026-06-01T09:00:00Z"),
		mk("3", "alice", "My Report", body, "2026-06-02T09:00:00Z"),
		mk("4", "alice", "grocery list", "milk, eggs", "2026-06-03T09:00:00Z"),
		mk("5", "alice", "Re: meeting",
			"> quoted text from a previous email\n"+
				"> another line of quoted text\n"+
				"> third line of quoted text\n"+
				"On Mon, Jun 1, 2026, alice@example.com wrote:\n"+
				"> fourth quoted line\n",
			"2026-06-04T09:00:00Z"),
	}
}
