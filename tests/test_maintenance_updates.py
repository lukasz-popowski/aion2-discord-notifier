import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import notifier


class MaintenanceUpdatesTests(unittest.TestCase):
    def test_fingerprint_ignores_whitespace_and_case(self):
        self.assertEqual(notifier.maintenance_fingerprint('Hello', 'Server up'),
                         notifier.maintenance_fingerprint(' hello ', 'server   UP'))

    def test_baseline_once_and_detect_change(self):
        state = {'seen': ['123'], 'initialized': True}
        self.assertEqual(notifier.record_maintenance_baseline(state, '123', 'Maintenance', '08:30'), 'baseline')
        self.assertEqual(notifier.record_maintenance_baseline(state, '123', 'Maintenance', '08:30'), 'unchanged')
        self.assertEqual(notifier.record_maintenance_baseline(state, '123', 'Maintenance', '09:30'), 'changed')

    def test_status_does_not_assume_online(self):
        self.assertEqual(notifier.maintenance_status('Maintenance', 'Expected end 09:30'),
                         'Aktualizacja oficjalnego komunikatu')
        self.assertIn('Przedłużenie', notifier.maintenance_status('Maintenance', 'Extended maintenance'))
        self.assertIn('Zakończenie', notifier.maintenance_status('Maintenance completed', 'All servers online'))

    def test_seen_announcement_bootstraps_without_post_then_alerts_on_edit(self):
        article = {'gid': '123', 'title': 'Server maintenance', 'contents': 'Maintenance planned at 08:30', 'date': 1, 'url': 'https://example.org'}
        state = {'seen': ['123'], 'initialized': True, 'chars_by_month': {}}
        args = SimpleNamespace(dry_run=False, test_notification=False)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(notifier, 'STATE_FILE', Path(tmp) / 'state.json'), \
                 patch.object(notifier, 'fetch_json', return_value={'appnews': {'newsitems': [article]}}), \
                 patch.object(notifier, 'translate', side_effect=lambda text, api, st: text), \
                 patch.object(notifier, 'post_discord') as post, \
                 patch.object(notifier, 'load_state', return_value=state), \
                 patch.dict(notifier.os.environ, {'GOOGLE_TRANSLATE_API_KEY': 'x', 'DISCORD_WEBHOOK_URL': 'https://example.org'}):
                notifier.run(args)
                post.assert_not_called()
                self.assertIn('123', state['maintenance_versions'])
                article['contents'] = 'Maintenance extended to 10:30'
                notifier.run(args)
                self.assertEqual(post.call_count, 1)
                notifier.run(args)
                self.assertEqual(post.call_count, 1)


if __name__ == '__main__':
    unittest.main()
