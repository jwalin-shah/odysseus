import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from sys_vault import set_secret, get_secret, delete_secret, VaultError

def test_vault_operations():
    service = "OdysseusV2TestService"
    account = "test_user"
    secret = "test_super_secret"

    # Cleanup before test
    try:
        delete_secret(service, account)
    except VaultError:
        pass

    # Set secret
    set_secret(service, account, secret)

    # Get secret
    retrieved = get_secret(service, account)
    assert retrieved == secret, f"Expected {secret}, got {retrieved}"

    # Update secret
    new_secret = "new_secret_456"
    set_secret(service, account, new_secret)
    retrieved = get_secret(service, account)
    assert retrieved == new_secret, f"Expected {new_secret}, got {retrieved}"

    # Delete secret
    delete_secret(service, account)

    # Get secret should fail
    with pytest.raises(VaultError):
        get_secret(service, account)
