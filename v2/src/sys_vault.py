"""sys-vault: macOS Keychain wrapper for secure secret storage.

Stores secrets via the macOS `security` CLI. All errors raise VaultError.
"""
import subprocess


class VaultError(Exception):
    """Raised on any vault operation failure (Keychain errors, missing binary, etc.)."""
    pass


"""sys-vault: macOS Keychain wrapper for secure secret storage.

Stores secrets via the macOS `security` CLI. All errors raise VaultError.
"""
import subprocess


class VaultError(Exception):
    """Raised on any vault operation failure (Keychain errors, missing binary, etc.)."""
    pass


"""sys-vault: macOS Keychain wrapper for secure secret storage.

Stores secrets via the macOS `security` CLI. All errors raise VaultError.
"""
import subprocess


class VaultError(Exception):
    """Raised on any vault operation failure (Keychain errors, missing binary, etc.)."""
    pass


def set_secret(service: str, account: str, secret: str) -> None:
    """Store or update a secret in macOS Keychain."""
    try:
        subprocess.run(
            ["security", "add-generic-password", "-U",
             "-s", service, "-a", account, "-w", secret],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to set secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to set secret: 'security' command not found (macOS only)")


def get_secret(service: str, account: str) -> str:
    """Retrieve a secret from macOS Keychain. Returns the plaintext secret."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", service, "-a", account, "-w"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if e.returncode == 44:
            raise VaultError(f"Secret not found: service={service!r} account={account!r}")
        raise VaultError(f"Failed to get secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to get secret: 'security' command not found (macOS only)")
    except subprocess.TimeoutExpired:
        raise VaultError("Failed to get secret: timeout waiting for 'security' command")
def delete_secret(service: str, account: str) -> None:
    """Delete a secret from macOS Keychain."""
    try:
        subprocess.run(
            ["security", "delete-generic-password",
             "-s", service, "-a", account],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to delete secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to delete secret: 'security' command not found (macOS only)")
def get_secret(service: str, account: str) -> str:
    """Retrieve a secret from macOS Keychain. Returns the plaintext secret."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", service, "-a", account, "-w"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to get secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to get secret: 'security' command not found (macOS only)")
    except subprocess.TimeoutExpired:
        raise VaultError("Failed to get secret: timeout waiting for 'security' command")
def delete_secret(service: str, account: str) -> None:
    """Delete a secret from macOS Keychain."""
    try:
        subprocess.run(
            ["security", "delete-generic-password",
             "-s", service, "-a", account],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to delete secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to delete secret: 'security' command not found (macOS only)")
def get_secret(service: str, account: str) -> str:
    """Retrieve a secret from macOS Keychain. Returns the plaintext secret."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", service, "-a", account, "-w"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to get secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to get secret: 'security' command not found (macOS only)")


def delete_secret(service: str, account: str) -> None:
    """Delete a secret from macOS Keychain."""
    try:
        subprocess.run(
            ["security", "delete-generic-password",
             "-s", service, "-a", account],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise VaultError(f"Failed to delete secret: {e.stderr.strip() or str(e)}")
    except FileNotFoundError:
        raise VaultError("Failed to delete secret: 'security' command not found (macOS only)")
