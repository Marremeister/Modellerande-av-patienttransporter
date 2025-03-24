import unittest
from unittest.mock import MagicMock

from Model.model_transport_manager import TransportManager
from Model.hospital_model import Hospital
from Model.model_patient_transporters import PatientTransporter
from Model.model_transportation_request import TransportationRequest


class TestTransportManager(unittest.TestCase):
    def setUp(self):
        # 🧪 Use real hospital but mocked socketio
        self.hospital = Hospital()
        self.mock_socketio = MagicMock()
        self.tm = TransportManager(self.hospital, self.mock_socketio)

    def tearDown(self):
        # Clear global request lists to avoid test bleed
        TransportationRequest.pending_requests.clear()
        TransportationRequest.ongoing_requests.clear()
        TransportationRequest.completed_requests.clear()

    def test_add_transporter(self):
        transporter = PatientTransporter(self.hospital,"Alice", self.mock_socketio)
        self.tm.add_transporter(transporter)
        self.assertEqual(len(self.tm.transporters), 1)
        self.assertEqual(self.tm.transporters[0].name, "Alice")

    def test_create_transport_request(self):
        request = self.tm.create_transport_request("ER", "ICU", "wheelchair", True)
        self.assertIn(request, TransportationRequest.pending_requests)
        self.assertEqual(request.origin, "ER")
        self.assertTrue(request.urgent)

    def test_assign_transport_sets_transporter(self):
        transporter = PatientTransporter(self.hospital, "Bob", self.mock_socketio)
        self.tm.add_transporter(transporter)
        request = self.tm.create_transport_request("ER", "XRay")

        result = self.tm.assign_transport(transporter.name, request)
        self.assertIn("status", result)
        self.assertEqual(request.get_transporter_name(), "Bob")
        self.assertEqual(request.status, "ongoing")

    def test_cannot_assign_to_inactive_transporter(self):
        transporter = PatientTransporter(self.hospital, "InactiveTom", self.mock_socketio)
        transporter.set_inactive()
        self.tm.add_transporter(transporter)

        request = self.tm.create_transport_request("A", "B")
        result, status_code = self.tm.assign_transport(transporter.name, request)

        self.assertEqual(status_code, 400)
        self.assertIn("inactive", result["error"].lower())

    def test_completed_request_gets_tracked(self):
        transporter = PatientTransporter(self.hospital, "Cathy", self.mock_socketio)
        self.tm.add_transporter(transporter)

        request = self.tm.create_transport_request("ER", "ICU")
        self.tm.assign_transport(transporter.name, request)
        request.mark_as_completed()

        self.assertEqual(request.status, "completed")
        self.assertIn(request, TransportationRequest.completed_requests)

    def test_get_assignable_requests(self):
        self.tm.create_transport_request("Reception", "Pharmacy")
        assignable = self.tm.get_assignable_requests()
        self.assertGreater(len(assignable), 0)

    def test_has_assignable_work_true(self):
        self.tm.create_transport_request("Reception", "Pharmacy")
        self.assertTrue(self.tm.has_assignable_work())

    def test_has_assignable_work_false(self):
        self.assertFalse(self.tm.has_assignable_work())


if __name__ == '__main__':
    unittest.main()
