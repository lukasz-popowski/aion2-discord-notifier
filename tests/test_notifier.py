import unittest
from unittest.mock import patch
import notifier

class NotifierTests(unittest.TestCase):
    def test_maintenance_eu(self):
        self.assertEqual(notifier.categorize('[Notice] Maintenance Oct 8', ''), 'maintenance')
        self.assertTrue(notifier.relevant('[Notice] Maintenance Oct 8', 'Affected services: All services'))
    def test_other_region(self):
        self.assertFalse(notifier.relevant('NA only Maintenance', 'North America servers'))
    def test_other_region_even_when_body_global(self):
        self.assertFalse(notifier.relevant('NA only Maintenance', 'All services affected'))
    def test_server_specific(self):
        self.assertTrue(notifier.relevant('Phernos downtime', 'Server Phernos'))
    def test_ambiguous_no_send(self):
        self.assertFalse(notifier.relevant('New Event', 'Details soon'))
    def test_code(self):
        self.assertEqual(notifier.categorize('A Thank You Gift', 'Redeem code TAKEFLIGHTAION2'), 'code')
    def test_html_sanitize(self):
        self.assertEqual(notifier.strip_markup('<b>Hello</b> &amp; [b]friends[/b]'), 'Hello & friends')
    def test_embed_mentions_disabled(self):
        with patch('builtins.print') as p:
            notifier.post_discord('', 'Test', '@everyone', 'https://steamcommunity.com/', 'event', 0, dry_run=True)
            self.assertIn('"parse": []', p.call_args.args[0])

if __name__ == '__main__':
    unittest.main()
