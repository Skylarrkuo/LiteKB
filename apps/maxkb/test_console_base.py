from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from maxkb.urls import web


class ConsoleEntryTests(SimpleTestCase):
    def test_nested_navigation_uses_the_canonical_asset_root(self):
        template = Path(__file__).resolve().parents[2] / 'ui' / 'admin.html'
        with TemporaryDirectory() as root:
            static = Path(root) / 'admin'
            static.mkdir()
            (static / 'index.html').write_text(template.read_text(encoding='utf-8'), encoding='utf-8')
            prefix, chat = '/product/studio', '/product/chat'
            request = RequestFactory().get(prefix + '/settings/branding')
            with (patch.object(web.settings, 'STATIC_ROOT', root),
                  patch.object(web, 'admin_ui_prefix', prefix),
                  patch.object(web, 'chat_ui_prefix', chat),
                  patch.dict(web.static_dict, {prefix: []})):
                response = web.page_not_found(request, None)
                self.assertEqual(response.content, web.admin_index(request).content)
            html = response.content.decode()
            self.assertIn('href="/product/studio/"', html)
            self.assertIn('data-chat-prefix="/product/chat"', html)
            self.assertLess(html.index('<base '), html.index('<link '))
