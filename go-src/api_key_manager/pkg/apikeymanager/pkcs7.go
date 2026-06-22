package apikeymanager

// pkcs7Pad returns plaintext padded to a multiple of blockSize per PKCS#7
// (RFC 5652 §6.3). Always appends at least one byte so the round-trip is
// unambiguous even when plaintext length is already a multiple of
// blockSize.
func pkcs7Pad(plaintext []byte, blockSize int) []byte {
	padLen := blockSize - (len(plaintext) % blockSize)
	out := make([]byte, len(plaintext)+padLen)
	copy(out, plaintext)
	for i := len(plaintext); i < len(out); i++ {
		out[i] = byte(padLen)
	}
	return out
}

// pkcs7Unpad reverses pkcs7Pad. Returns an error when the padding is
// malformed (wrong pad length or pad bytes not matching padLen).
func pkcs7Unpad(padded []byte, blockSize int) ([]byte, error) {
	if len(padded) == 0 || len(padded)%blockSize != 0 {
		return nil, errBadPadding
	}
	padLen := int(padded[len(padded)-1])
	if padLen <= 0 || padLen > blockSize {
		return nil, errBadPadding
	}
	if padLen > len(padded) {
		return nil, errBadPadding
	}
	for i := len(padded) - padLen; i < len(padded); i++ {
		if padded[i] != byte(padLen) {
			return nil, errBadPadding
		}
	}
	return padded[:len(padded)-padLen], nil
}
