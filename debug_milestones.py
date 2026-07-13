from app import create_app
from app.models import Shipment, ShipmentMilestone

app = create_app()

with app.app_context():

    print("=" * 70)
    print("SHIPMENTS")
    print("=" * 70)

    for shipment in Shipment.query.order_by(Shipment.id).all():

        print(f"\nShipment : {shipment.shipment_reference}")
        print(f"Current Stage : {shipment.current_stage}")
        print(f"Status : {shipment.shipment_status}")

        milestones = (
            ShipmentMilestone.query
            .filter_by(shipment_id=shipment.id)
            .order_by(ShipmentMilestone.completed_at)
            .all()
        )

        print("Completed Milestones:")

        if not milestones:
            print("  None")
        else:
            for m in milestones:
                print(f"  - {m.stage}")

    print("\n" + "=" * 70)