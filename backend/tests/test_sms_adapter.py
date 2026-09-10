import os
import sys
import unittest
from unittest.mock import Mock, patch

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sms_api


class SmsAdapterTests(unittest.TestCase):
    def test_missing_sdk_or_configuration_is_reported_as_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Exception) as caught:
                sms_api._twilio_client()
        self.assertEqual(getattr(caught.exception, "status_code", None), 503)

    def test_twilio_delivery_is_mocked_at_the_adapter_boundary(self):
        sent = Mock(sid="SM_TEST", status="queued")
        client = Mock(); client.messages.create.return_value = sent
        with patch.object(sms_api, "_twilio_client", return_value=(client, "+15551234567")):
            result = sms_api._send_with_twilio("+919876543210", "Test message")
        self.assertIs(result, sent)
        client.messages.create.assert_called_once_with(to="+919876543210", from_="+15551234567", body="Test message")
