import unittest

from app.main import BUSINESS_TYPES


class BusinessLabelTest(unittest.TestCase):
    def test_date_labels_match_each_business(self):
        self.assertEqual(BUSINESS_TYPES["hotel"]["dateLabel"], "Checkout date")
        self.assertEqual(BUSINESS_TYPES["restaurant"]["dateLabel"], "Visit date")
        self.assertEqual(BUSINESS_TYPES["salon_spa"]["dateLabel"], "Appointment date")
