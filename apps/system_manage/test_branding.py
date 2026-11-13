import base64
import json
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image
from rest_framework.test import APIRequestFactory

from common.exception.app_exception import AppAuthenticationFailed, AppUnauthorizedFailed
from system_manage.models.system_setting import SettingType, SystemSetting
from system_manage.views.branding import BrandingAuthentication, BrandingSerializer, BrandingView


def png_uri(size=(8, 8), trailing=b''):
    output = BytesIO()
    Image.new('RGBA', size, '#164b50').save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue() + trailing).decode('ascii')


class BrandingTests(SimpleTestCase):
    def test_public_read_defaults_and_admin_write(self):
        with patch.object(SystemSetting.objects, 'filter') as query:
            query.return_value.values_list.return_value.first.return_value = None
            self.assertEqual(json.loads(BrandingView().get(None).content)['data'], {'name': 'LiteKB', 'icon': ''})
        request = SimpleNamespace(auth=SimpleNamespace(role_list=['ADMIN'], permission_list=[]),
                                  data={'name': '  Customer Studio ', 'icon': ''})
        with patch.object(SystemSetting.objects, 'update_or_create') as save:
            self.assertEqual(json.loads(BrandingView().put(request).content)['data']['name'], 'Customer Studio')
            save.assert_called_once_with(type=SettingType.BRANDING, defaults={'meta': {'name': 'Customer Studio', 'icon': ''}})

    def test_anonymous_and_non_admin_cannot_write(self):
        factory = APIRequestFactory()
        auth = BrandingAuthentication()
        self.assertIsNone(auth.authenticate(factory.get('/branding')))
        with self.assertRaises(AppAuthenticationFailed):
            auth.authenticate(factory.put('/branding'))
        request = SimpleNamespace(auth=SimpleNamespace(role_list=['USER'], permission_list=[]))
        with self.assertRaises(AppUnauthorizedFailed):
            BrandingView().put(request)

    def test_icons_are_bounded_static_pngs(self):
        for value in ['data:image/svg+xml;base64,AAA=', 'data:image/png;base64,bad!', png_uri((513, 1)),
                      png_uri(trailing=b'x' * (256 * 1024))]:
            with self.subTest(icon=value[:40]):
                self.assertFalse(BrandingSerializer(data={'name': 'Test', 'icon': value}).is_valid())
        form = BrandingSerializer(data={'name': 'Test', 'icon': png_uri(trailing=b'unused')})
        self.assertTrue(form.is_valid(), form.errors)
        raw = base64.b64decode(form.validated_data['icon'].partition(',')[2])
        self.assertNotIn(b'unused', raw)
        with Image.open(BytesIO(raw)) as image:
            self.assertEqual(image.size, (8, 8))
