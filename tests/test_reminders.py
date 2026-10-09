import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import notifier

class ReminderTests(unittest.TestCase):
    def test_eu_datetime(self):
        start = notifier.parse_maintenance_start('[Notice] Temporary Maintenance', 'When: October 9, 2026 at 08:30 CEST. All services')
        self.assertEqual(start, int(dt.datetime(2026, 10, 9, 6, 30, tzinfo=dt.timezone.utc).timestamp()))

    def test_eu_preferred_over_utc(self):
        result = notifier.parse_maintenance_start('Maintenance', 'October 9, 2026 at 08:30 CEST / October 9, 2026 at 07:00 UTC')
        self.assertEqual(result, int(dt.datetime(2026, 10, 9, 6, 30, tzinfo=dt.timezone.utc).timestamp()))

    def test_reject_wrong_dst(self):
        self.assertIsNone(notifier.parse_maintenance_start('Maintenance', 'October 9, 2026 at 08:30 CET'))

    def test_no_invented_date(self):
        self.assertIsNone(notifier.parse_maintenance_start('Maintenance', 'Tomorrow at 08:30 CEST'))

    def test_no_non_eu_only(self):
        self.assertIsNone(notifier.parse_maintenance_start('NA only Maintenance', 'October 9, 2026 at 08:30 CEST'))

    def test_once_and_schedule_start(self):
        when = int(dt.datetime(2026, 10, 9, 6, 30, tzinfo=dt.timezone.utc).timestamp())
        state = {'maintenance_schedules': {'x': {'start': when, 'title': 'Maintenance', 'url': 'https://example.org', 'reminder_sent': False, 'start_sent': False}}}
        with patch.object(notifier, 'post_discord') as send, patch.object(notifier, 'save_state'):
            notifier.send_due_reminders(state, 'test', now=when - 1200)
            notifier.send_due_reminders(state, 'test', now=when - 800)
            self.assertEqual(send.call_count, 1)
            notifier.send_due_reminders(state, 'test', now=when + 120)
            notifier.send_due_reminders(state, 'test', now=when + 200)
            self.assertEqual(send.call_count, 2)
            self.assertIn('nie potwierdzenie', send.call_args.args[2])

    def test_reschedule(self):
        when = 1791527400
        state = {}
        self.assertTrue(notifier.register_maintenance_schedule(state, 'x', 'Maintenance', 'October 9, 2026 at 08:30 CEST', 'https://example.org', now=when-3600))
        state['maintenance_schedules']['x']['reminder_sent'] = True
        self.assertFalse(notifier.register_maintenance_schedule(state, 'x', 'Maintenance', 'October 9, 2026 at 08:30 CEST', 'https://example.org', now=when-3600))
        self.assertTrue(notifier.register_maintenance_schedule(state, 'x', 'Maintenance', 'October 9, 2026 at 09:30 CEST', 'https://example.org', now=when-3600))
        self.assertFalse(state['maintenance_schedules']['x']['reminder_sent'])

if __name__ == '__main__':
    unittest.main()
