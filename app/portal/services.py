from datetime import datetime


class PortalService:
    """
    Client Portal Business Logic
    """

    @staticmethod
    def dashboard_summary(client):
        """
        Dashboard summary data.
        (Will be connected to DB in next step.)
        """
        return {
            "total_shipments": 0,
            "active_shipments": 0,
            "delivered_shipments": 0,
            "closed_shipments": 0,
            "recent_shipments": []
        }

    @staticmethod
    def find_shipment(shipment_reference):
        """
        Find shipment using shipment_reference.
        """
        return None

    @staticmethod
    def shipment_documents(shipment):
        """
        Return shipment documents.
        """
        return []

    @staticmethod
    def shipment_milestones(shipment):
        """
        Shipment progress timeline.
        """
        return [
            "Booked",
            "Cargo Picked Up",
            "In Transit",
            "Arrived at Destination",
            "Customs Clearance",
            "Out for Delivery",
            "Delivered",
            "Closed / Completed"
        ]

    @staticmethod
    def submit_support_request(client, subject, message):
        """
        Support request placeholder.
        """
        return {
            "success": True,
            "submitted_at": datetime.utcnow()
        }