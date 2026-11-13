"""Initial administrator credentials for installations and upgraded databases."""
from common.utils.common import password_verify
from maxkb.const import CONFIG

# Older databases may still contain a hash of the upstream bootstrap password.
LEGACY_DEFAULT_PASSWORD = "MaxKB@123.."


def initial_admin_password():
    return CONFIG.get("BOOTSTRAP_ADMIN_PASSWORD") or CONFIG.get("DEFAULT_PASSWORD") or LEGACY_DEFAULT_PASSWORD


def uses_initial_password(user):
    if user.source != "LOCAL":
        return False
    candidates = [CONFIG.get("DEFAULT_PASSWORD"), LEGACY_DEFAULT_PASSWORD]
    if user.username == "admin":
        candidates.insert(0, initial_admin_password())
    return any(password_verify(candidate, user.password) for candidate in dict.fromkeys(candidates) if candidate)
