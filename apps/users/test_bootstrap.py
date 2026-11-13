from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from common.utils.common import password_encrypt
from users import bootstrap
from users.serializers.user import PASSWORD_REGEX, suggested_user_password


class BootstrapPasswordTests(SimpleTestCase):
    def test_admin_secret_is_separate_from_suggested_user_passwords(self):
        with patch.dict(bootstrap.CONFIG, {"BOOTSTRAP_ADMIN_PASSWORD": "fixture-admin", "DEFAULT_PASSWORD": "fixture-user"}):
            self.assertEqual(bootstrap.initial_admin_password(), "fixture-admin")
            generated = {suggested_user_password() for _ in range(8)}
            self.assertEqual(len(generated), 8)
            self.assertTrue(all(PASSWORD_REGEX.fullmatch(value) for value in generated))
            self.assertNotIn("fixture-admin", generated)

    def test_upgraded_admin_with_upstream_initial_password_is_prompted(self):
        user = SimpleNamespace(username="admin", source="LOCAL", password=password_encrypt(bootstrap.LEGACY_DEFAULT_PASSWORD))
        with patch.dict(bootstrap.CONFIG, {"BOOTSTRAP_ADMIN_PASSWORD": "current-installation"}):
            self.assertTrue(bootstrap.uses_initial_password(user))
            user.source = "LDAP"
            self.assertFalse(bootstrap.uses_initial_password(user))
