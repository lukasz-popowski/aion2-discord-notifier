import unittest
from notifier import categorize, relevant

class RegionFilterTests(unittest.TestCase):
    def test_global_maintenance_with_asia_specific_duration(self):
        self.assertTrue(relevant('Scheduled Maintenance Tue Oct 6 / Wed Oct 7',
            'Game servers. Duration 3h30. Duration (ASIA servers): 5h30.'))
    def test_maintenance_no_region(self):
        self.assertTrue(relevant('[Notice] Maintenance', 'Game server login unavailable.'))
    def test_maintenance_eu_time_zone(self):
        self.assertTrue(relevant('Maintenance Oct 7', 'When: October 7 at 08:30 CEST. All services'))
    def test_na_only_title(self):
        self.assertFalse(relevant('[Notice] NA only Maintenance', 'All servers have updates worldwide.'))
    def test_na_only_body(self):
        self.assertFalse(relevant('Event for Daevas', 'Available only to North America players. Global launch celebration.'))
    def test_eu_na_prize(self):
        self.assertTrue(relevant('A Thank You Gift to all Daevas!',
            'Redeem code TAKEFLIGHTAION2. Ends (NA) on Oct 13. Ends (EU) Oct 14. All servers.'))
    def test_unscoped_event_requires_review(self):
        self.assertFalse(relevant('New Community Event', 'Participate for prizes.'))
    def test_explicit_eu_event(self):
        self.assertTrue(relevant('Graphics Card Giveaway', 'Eligible in United States, Canada, and Europe.'))
    def test_asian_exclusive_event(self):
        self.assertFalse(relevant('Twitch Drops Asia only', 'Exclusive prizes.'))
    def test_phernos_explicit(self):
        self.assertTrue(relevant('Phernos server maintenance', 'Affected server Phernos.'))
    def test_unrelated_post(self):
        self.assertFalse(relevant('Developer interview', 'Europe players are excited.'))
    def test_classification_real_titles(self):
        self.assertEqual(categorize('Maintenance is over, welcome back!', ''), 'maintenance')
        self.assertEqual(categorize('Graphics Card Giveaway', ''), 'event')
        self.assertEqual(categorize('[Notice] Patch Notes | Oct 7', ''), 'patch')

if __name__ == '__main__':
    unittest.main()

class ScopePriorityTests(unittest.TestCase):
    def test_asia_region_first_headline(self):
        self.assertFalse(relevant('Asia server maintenance', 'All services in Asia affected.'))
    def test_generic_headline_asia_special_note(self):
        self.assertTrue(relevant('Scheduled Maintenance', 'Duration for ASIA servers is different.'))
