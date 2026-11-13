import csv
import json
from ctypes import c_long, sizeof
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase


class StartupTests(SimpleTestCase):
    def test_wsgi_entry_loads_template_formatter_and_serves_capabilities(self):
        from langchain_core.prompts.string import DEFAULT_FORMATTER_MAPPING
        from maxkb.const import CONFIG
        from maxkb.wsgi.web import application

        status = []
        path = CONFIG.get_admin_path() + '/api/capabilities'
        response = application(RequestFactory().get(path).environ, lambda code, _: status.append(code))
        try:
            self.assertEqual(status, ['200 OK'])
            self.assertIn('media_nodes', json.loads(b''.join(response))['data'])
        finally:
            response.close()
        self.assertEqual(csv.field_size_limit(), (1 << (sizeof(c_long) * 8 - 1)) - 1)
        self.assertEqual(DEFAULT_FORMATTER_MAPPING['jinja2']('{{ x | random }}', x=['hi']), 'hi')

    def test_worker_files_are_created_and_removed_in_its_runtime_directory(self):
        heartbeat = import_module('ops.celery.heartbeat')
        sender = SimpleNamespace(hostname='native@host')
        sender.eventer = sender
        with TemporaryDirectory() as directory:
            state = Path(directory) / 'tmp'
            with patch.object(heartbeat, '_worker_state_dir', state):
                heartbeat.worker_ready(sender)
                heartbeat.heartbeat(sender)
                self.assertEqual({p.name for p in state.iterdir()}, {'worker_ready_native', 'worker_heartbeat_native'})
                heartbeat.worker_shutdown(sender)
                self.assertEqual(list(state.iterdir()), [])

    def test_task_signing_requires_and_uses_a_shared_key(self):
        from ops.celery import hmac_signed_serializer as signer

        with patch.object(signer, '_local_secret_key', None), self.assertRaisesRegex(ImproperlyConfigured, 'SECRET_KEY'):
            signer.secure_dumps({'node': 'start'})
        with patch.object(signer, '_local_secret_key', 'test-worker'):
            packet = signer.secure_dumps({'node': 'start'})
            self.assertEqual(signer.secure_loads(packet), {'node': 'start'})
        with patch.object(signer, '_local_secret_key', 'other-worker'), self.assertRaisesRegex(ValueError, 'mismatch'):
            signer.secure_loads(packet)

    def test_tool_execution_on_unsupported_platform_never_starts_a_process(self):
        from application.flow.backend.sandbox_mcp import SandboxMCPBackend
        from application.flow.backend.sandbox_shell import SandboxShellBackend
        from common.mcp.config import InternalMCPConfig
        from common.mcp.sandbox import CONFIG
        from common.utils.tool_code import ToolExecutor

        tool = ToolExecutor()
        with patch('sys.platform', 'win32'), patch.dict(CONFIG, {'SANDBOX': '0'}), patch('subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'require Linux'):
                tool.exec_code('', {})
            with self.assertRaisesRegex(ValueError, 'require Linux'):
                tool.generate_mcp_server_code('', {}, 't', '', '1')
            with self.assertRaisesRegex(ValueError, 'require Linux'):
                SandboxMCPBackend({'local': InternalMCPConfig(transport='stdio')})
            with self.assertRaisesRegex(ValueError, 'require Linux'):
                SandboxMCPBackend({'remote': {'transport': 'sse', 'url': 'https://example.invalid'}})
            result = SandboxShellBackend.execute(None, 'unused')
            self.assertEqual(result.exit_code, 1)
            self.assertIn('Linux', result.output)
            popen.assert_not_called()


class CollationMigrationTests(SimpleTestCase):
    def test_only_rebuilds_current_database_for_a_known_version_change(self):
        migration = import_module('system_manage.migrations.0002_refresh_collation_reindex')
        db_name = 'test"kb'
        for recorded, current, rebuild in ((None, None, False), ('1', None, False), ('1', '1', False), ('1', '2', True)):
            with self.subTest(recorded=recorded, current=current):
                connection = MagicMock(vendor='postgresql', pg_version=170000)
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchone.return_value = db_name, recorded, current
                migration.re_index(None, SimpleNamespace(connection=connection))
                calls = cursor.execute.call_args_list
                self.assertIn('current_database()', calls[0].args[0])
                statements = [call.args[0].as_string() for call in calls[1:]]
                self.assertEqual(statements, [
                    'REINDEX DATABASE "test""kb"', 'ALTER DATABASE "test""kb" REFRESH COLLATION VERSION',
                ] if rebuild else [])
