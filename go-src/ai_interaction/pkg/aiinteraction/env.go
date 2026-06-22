package aiinteraction

import "os"

// getDataDir mirrors the Python
// DATA_DIR = os.environ.get('ODYSSEUS_DATA_DIR', './data')
// default used in src/constants.py. The Go port keeps the same fallback
// so callers that wire up DefaultGeneratedImagesDir in production get
// the equivalent of "DATA_DIR/generated_images".
func getDataDir() string {
	if v := os.Getenv("ODYSSEUS_DATA_DIR"); v != "" {
		return v
	}
	return "./data"
}
