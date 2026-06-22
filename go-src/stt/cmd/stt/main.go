// Command stt is a small demo of the stt package: it transcribes a .webm file
// using the configured provider from data/settings.json.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	stt "github.com/odysseus/stt/pkg/stt"
)

func main() {
	file := flag.String("file", "", "path to .webm audio file to transcribe")
	flag.Parse()

	if *file == "" {
		fmt.Fprintf(os.Stderr, "Usage: stt --file <audio.webm>\n")
		os.Exit(1)
	}

	audio, err := os.ReadFile(*file)
	if err != nil {
		log.Fatalf("read audio file: %v", err)
	}

	svc := stt.New()

	stats := svc.Stats()
	fmt.Printf("STT service: provider=%s model=%s available=%v\n",
		stats.Provider, stats.Model, stats.Available)

	if !stats.Available {
		log.Fatal("STT service is not available with current settings")
	}

	text, err := svc.Transcribe(context.Background(), audio)
	if err != nil {
		log.Fatalf("transcription failed: %v", err)
	}

	fmt.Println(text)
}
