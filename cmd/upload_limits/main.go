// Command upload_limits is a small CLI for inspecting the effective per-route
// upload caps and exercising ReadUploadLimited against stdin. It exists so
// operators can sanity-check env overrides in production-like environments
// without booting the full FastAPI server.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"

	"odysseus/upload_limits"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "upload_limits:", err)
		os.Exit(1)
	}
}

func run() error {
	limits, err := upload_limits.Resolve()
	if err != nil {
		return err
	}

	fmt.Printf("chat                 = %d bytes (%s)\n", limits.Chat, upload_limits.FormatByteLimit(limits.Chat))
	fmt.Printf("gallery              = %d bytes (%s)\n", limits.Gallery, upload_limits.FormatByteLimit(limits.Gallery))
	fmt.Printf("gallery_transform    = %d bytes (%s)\n", limits.GalleryTransform, upload_limits.FormatByteLimit(limits.GalleryTransform))
	fmt.Printf("memory_import        = %d bytes (%s)\n", limits.MemoryImport, upload_limits.FormatByteLimit(limits.MemoryImport))
	fmt.Printf("personal             = %d bytes (%s)\n", limits.Personal, upload_limits.FormatByteLimit(limits.Personal))
	fmt.Printf("email_compose        = %d bytes (%s)\n", limits.EmailCompose, upload_limits.FormatByteLimit(limits.EmailCompose))
	fmt.Printf("stt                  = %d bytes (%s)\n", limits.STT, upload_limits.FormatByteLimit(limits.STT))
	fmt.Printf("ics                  = %d bytes (%s)\n", limits.ICS, upload_limits.FormatByteLimit(limits.ICS))

	data, err := upload_limits.ReadUploadLimited(os.Stdin, limits.Chat, "Chat")
	if err != nil {
		// Translate the sentinel to a clear single-line message; the
		// binary is meant to be human-inspected.
		if errors.Is(err, upload_limits.ErrUploadTooLarge) {
			return fmt.Errorf("stdin payload exceeds chat limit (%s)", upload_limits.FormatByteLimit(limits.Chat))
		}
		if errors.Is(err, io.EOF) {
			// No data piped in — treat as a successful no-op read so the
			// limits dump is still useful.
			fmt.Println("stdin read: 0 bytes (EOF)")
			return nil
		}
		return err
	}
	fmt.Printf("stdin read: %d bytes\n", len(data))
	return nil
}
