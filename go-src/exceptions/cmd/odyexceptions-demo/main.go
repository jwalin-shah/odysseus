// Command odyexceptions-demo is a small CLI that constructs each typed
// exception from the odyexceptions package and walks a few representative
// errors.Is / errors.As / Unwrap chains so a human reviewer can eyeball the
// hierarchy without writing a test program.
package main

import (
	"errors"
	"fmt"
	"os"

	contextodexc "github.com/odysseus/exceptions/pkg/odyexceptions"
)

func main() {
	fmt.Println("== odyexceptions demo ==")

	// 1. Direct construction of each typed error (mirrors `raise Foo(...)`
	//    in Python).
	sessionErr := contextodexc.NewSessionNotFound("sess-42")
	uploadErr := contextodexc.NewInvalidFileUpload("file too large: 9.9MB > 5MB", "huge.pdf")
	llmErr := contextodexc.NewLLMService("HTTP 503 from upstream", "https://api.example/v1")
	webErr := contextodexc.NewWebSearch("dns lookup failed", "odysseus exceptions")

	all := []*contextodexc.Error{sessionErr, uploadErr, llmErr, webErr}
	for _, e := range all {
		fmt.Printf("- code=%-22s message=%-46s err=%q\n", e.Code, e.Message, e.Error())
		fmt.Printf("  sentinels match: session=%v upload=%v llm=%v web=%v\n",
			errors.Is(e, contextodexc.ErrSessionNotFound),
			errors.Is(e, contextodexc.ErrInvalidFileUpload),
			errors.Is(e, contextodexc.ErrLLMService),
			errors.Is(e, contextodexc.ErrWebSearch),
		)
	}

	// 2. errors.As extraction against the LLM error.
	fmt.Println("\n== errors.As walk-up ==")
	var extracted *contextodexc.Error
	if errors.As(llmErr, &extracted) {
		fmt.Printf("extracted: code=%s endpoint=%q\n", extracted.Code, extracted.Endpoint)
	}

	// 3. Wrap chain: stdlib net error → typed LLM error → outer wrapper.
	fmt.Println("\n== Wrap chain ==")
	root := errors.New("dial tcp 1.2.3.4:443: i/o timeout")
	typed := contextodexc.Wrap(root, contextodexc.CodeLLMService, "stream interrupted")
	outer := &contextodexc.Error{
		Code:    contextodexc.CodeLLMService,
		Message: "agent loop failed",
		Cause:   typed,
	}
	fmt.Printf("outer.Error() = %q\n", outer.Error())
	fmt.Printf("errors.Is(outer, root)               = %v\n", errors.Is(outer, root))
	fmt.Printf("errors.Is(outer, ErrLLMService)      = %v\n", errors.Is(outer, contextodexc.ErrLLMService))
	fmt.Printf("errors.Is(sessionErr, ErrLLMService) = %v (cross-class, should be false)\n",
		errors.Is(sessionErr, contextodexc.ErrLLMService))

	// 4. AsError convenience helper.
	fmt.Println("\n== AsError convenience ==")
	if e := contextodexc.AsError(outer); e != nil {
		fmt.Printf("AsError(outer).Code = %s\n", e.Code)
	}
	if e := contextodexc.AsError(errors.New("plain")); e == nil {
		fmt.Println("AsError(plain error) -> nil (expected)")
	}

	// 5. Code.String mapping table.
	fmt.Println("\n== Code string mapping ==")
	for _, c := range []contextodexc.Code{
		contextodexc.CodeUnknown,
		contextodexc.CodeSessionNotFound,
		contextodexc.CodeInvalidFileUpload,
		contextodexc.CodeLLMService,
		contextodexc.CodeWebSearch,
	} {
		fmt.Printf("- %d -> %s\n", c, c.String())
	}

	// 6. Demonstrate that a real-world chained error still matches the
	//    typed sentinel — this is what production callers want.
	fmt.Println("\n== end-to-end sentinel match through chain ==")
	chained := fmt.Errorf("orchestrator: %w",
		contextodexc.Wrap(
			contextodexc.NewLLMService("rate limit", "https://api/v1"),
			contextodexc.CodeLLMService,
			"chat completion",
		),
	)
	fmt.Printf("chained.Error() = %q\n", chained.Error())
	fmt.Printf("errors.Is(chained, ErrLLMService) = %v\n", errors.Is(chained, contextodexc.ErrLLMService))

	_ = os.Stdout
}
