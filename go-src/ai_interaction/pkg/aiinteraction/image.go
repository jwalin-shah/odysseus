package aiinteraction

import (
	"fmt"
	"strings"
)

// ParseImageRequest parses the do_generate_image content string.
//
// Content format:
//
//	Line 1: prompt describing the image
//	Line 2: model name (optional, default auto-detects)
//	Line 3: size (optional, defaults to 1024x1024)
//	Line 4: quality (optional, defaults to medium)
//
// The function mirrors the Python source: each line is trimmed and
// missing trailing lines default to the empty string. The caller
// (do_generate_image itself, or a test) is responsible for filling
// in model/size/quality defaults from settings or auto-detection.
func ParseImageRequest(content string) (*ImageRequest, error) {
	rawLines := strings.Split(strings.TrimSpace(content), "\n")
	if len(rawLines) == 0 {
		return nil, fmt.Errorf("error: Image prompt is required (line 1)")
	}
	req := &ImageRequest{Prompt: strings.TrimSpace(rawLines[0])}
	if req.Prompt == "" {
		return nil, fmt.Errorf("error: Image prompt is required (line 1)")
	}
	if len(rawLines) > 1 {
		req.Model = strings.TrimSpace(rawLines[1])
	}
	if len(rawLines) > 2 && strings.TrimSpace(rawLines[2]) != "" {
		req.Size = strings.TrimSpace(rawLines[2])
	} else {
		req.Size = "1024x1024"
	}
	if len(rawLines) > 3 && strings.TrimSpace(rawLines[3]) != "" {
		req.Quality = strings.TrimSpace(rawLines[3])
	} else {
		req.Quality = "medium"
	}
	return req, nil
}

// ClassifyImageModel mirrors the three-way branch in do_generate_image:
//
//   - is_gpt_image   — "gpt-image" substring in model_id (case-insensitive)
//   - is_dalle       — "dall-e" substring in model_id
//   - is_local_diff  — neither of the above
//
// The Go port uses strings.Contains with ToLower to match the Python
// `in` check on a lowered model_id.
func ClassifyImageModel(modelID string) (isGPTImage, isDalle, isLocalDiff bool) {
	low := strings.ToLower(modelID)
	isGPTImage = strings.Contains(low, "gpt-image")
	isDalle = strings.Contains(low, "dall-e")
	isLocalDiff = !isGPTImage && !isDalle
	return
}

// NormalizeImageSize applies the size-validation logic do_generate_image
// performs for the chosen model class:
//
//   - gpt-image-* sizes must be in ValidGPTSizes; otherwise default to
//     1024x1024.
//   - dall-e-3 sizes must be in ValidDalle3Sizes; otherwise default to
//     1024x1024.
//   - local diffusion accepts any size verbatim.
//
// The function returns the (possibly defaulted) size.
func NormalizeImageSize(size string, isGPTImage, isDalle bool) string {
	if isGPTImage {
		if !inSet(ValidGPTSizes, size) {
			return "1024x1024"
		}
		return size
	}
	if isDalle {
		if !inSet(ValidDalle3Sizes, size) {
			return "1024x1024"
		}
		return size
	}
	return size
}

// NormalizeImageQuality applies the quality-validation logic. The
// Python source uses "medium" as the default when the value isn't
// recognised; the Go port mirrors that.
func NormalizeImageQuality(quality string, isGPTImage, isLocalDiff bool) string {
	if !isGPTImage && !isLocalDiff {
		// DALL-E does not accept a quality field; strip it.
		return ""
	}
	if !KnownImageQuality(quality) {
		return "medium"
	}
	return quality
}

// ImageAPIPayload renders the request body the Python source POSTs to
// /v1/images/generations. The fields returned depend on the model
// class: gpt-image-* and local diffusion include "quality"; DALL-E
// does not.
func ImageAPIPayload(modelID, prompt, size, quality string, isGPTImage, isDalle, isLocalDiff bool) map[string]any {
	payload := map[string]any{
		"model":  modelID,
		"prompt": prompt,
		"n":      1,
		"size":   size,
	}
	if isGPTImage || isLocalDiff {
		if quality == "" {
			quality = "medium"
		}
		payload["quality"] = quality
	}
	return payload
}

// ImageURLFromResponse mirrors the dispatch do_generate_image performs
// on the first image in the response:
//
//   - if b64_json is present, save the decoded PNG to the generated
//     images dir and return the web-facing URL plus the gallery id;
//   - if url is present, validate via the URL safety check (the Go
//     port surfaces this as a callback so the caller wires the real
//     check) and either download + save or fall back to the external
//     URL;
//   - if neither, return an error.
//
// The image_dir / filename pair is filled by the caller; the function
// returns the URL plus the bytes to write (when b64_json is present).
type ImageBytes struct {
	Filename string
	Data     []byte
}

// ImageResponse mirrors the do_generate_image return dict. The Go port
// keeps the same field names so a caller can serialise it back to JSON
// without translation.
type ImageResponse struct {
	ImageURL     string `json:"image_url,omitempty"`
	ImageID      string `json:"image_id,omitempty"`
	ImagePrompt  string `json:"image_prompt,omitempty"`
	ImageModel   string `json:"image_model,omitempty"`
	ImageSize    string `json:"image_size,omitempty"`
	ImageQuality string `json:"image_quality,omitempty"`
	Error        string `json:"error,omitempty"`
}

// DecodeBase64Image decodes a b64_json string into raw PNG bytes. The
// Python source uses `base64.b64decode` directly; the Go port uses
// stdlib's encoding/base64.
func DecodeBase64Image(b64 string) ([]byte, error) {
	return base64Decode(b64)
}
