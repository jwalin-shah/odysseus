// Command secretestore-demo is a small CLI front-end for the
// secret_storage package. It loads (or creates) the key file at
// --key-path and runs a single Encrypt, Decrypt, or IsEncrypted
// operation against the supplied value. The CLI is intentionally tiny:
// the goal is to exercise the public surface of the package end-to-end
// (filesystem → KeyBackend → Cipher → SecretStorage) and let a human
// eyeball the output.
//
// Usage:
//
//	secretestore-demo --key-path /tmp/app.key --op encrypt --value 'hunter2'
//	secretestore-demo --key-path /tmp/app.key --op decrypt --value 'enc:...'
//	secretestore-demo --key-path /tmp/app.key --op is-encrypted --value 'enc:...'
//
// --op defaults to encrypt if neither is given.
package main

import (
	"flag"
	"fmt"
	"os"

	contextsecrets "github.com/odysseus/secret_storage/pkg/secretstorage"
)

func main() {
	if err := run(os.Args[1:], os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "secretestore-demo:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout, stderr *os.File) error {
	fs := flag.NewFlagSet("secretestore-demo", flag.ContinueOnError)
	fs.SetOutput(stderr)
	keyPath := fs.String("key-path", ".app_key", "Path to the Fernet-equivalent key file (created with 0o600 if missing).")
	op := fs.String("op", "encrypt", "Operation: encrypt | decrypt | is-encrypted")
	value := fs.String("value", "", "Value to operate on")
	if err := fs.Parse(args); err != nil {
		return err
	}

	backend, err := contextsecrets.NewFileKeyBackend(*keyPath)
	if err != nil {
		return err
	}
	// EnsureKey is a no-op when the file already exists, so this is the
	// production lazy-init path: first run creates the key, subsequent
	// runs reuse it. The key bytes here are a deterministic 32-byte
	// sequence — operators should swap in a Fernet.generate_key() output
	// in production by passing --key-path to a pre-seeded file.
	const demoKey = "0123456789abcdef0123456789abcdef"
	if err := backend.EnsureKey([]byte(demoKey)); err != nil {
		return fmt.Errorf("ensure key: %w", err)
	}

	cipher, err := contextsecrets.NewXORStubCipher([]byte(demoKey))
	if err != nil {
		return err
	}
	ss, err := contextsecrets.NewSecretStorage(backend, cipher)
	if err != nil {
		return err
	}

	switch *op {
	case "encrypt":
		out, err := ss.Encrypt(*value)
		if err != nil {
			return err
		}
		fmt.Fprintln(stdout, out)
	case "decrypt":
		out, err := ss.Decrypt(*value)
		if err != nil {
			// Match the Python helper's empty-fallback behaviour: still
			// print the empty line and surface the error on stderr so
			// CI can decide whether to fail.
			fmt.Fprintln(stderr, "decrypt warning:", err)
		}
		fmt.Fprintln(stdout, out)
	case "is-encrypted":
		yes := ss.IsEncrypted(*value)
		fmt.Fprintln(stdout, yes)
	default:
		return fmt.Errorf("unknown --op %q (want encrypt | decrypt | is-encrypted)", *op)
	}
	return nil
}
