from app import create_app, db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)

    print("=" * 80)
    print("Fixing PostgreSQL sequences...")
    print("=" * 80)

    fixed = 0
    skipped = 0

    for table in inspector.get_table_names():
        pk = inspector.get_pk_constraint(table)

        if not pk or not pk.get("constrained_columns"):
            skipped += 1
            continue

        columns = pk["constrained_columns"]

        # Only support single-column integer primary keys
        if len(columns) != 1:
            skipped += 1
            continue

        column = columns[0]

        try:
            seq = db.session.execute(
                text(
                    """
                    SELECT pg_get_serial_sequence(:table, :column)
                    """
                ),
                {"table": table, "column": column},
            ).scalar()

            if not seq:
                print(f"SKIPPED : {table} (no sequence)")
                skipped += 1
                continue

            db.session.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', '{column}'),
                        COALESCE((SELECT MAX({column}) FROM {table}), 1),
                        true
                    );
                    """
                )
            )

            print(f"FIXED    : {table}")
            fixed += 1

        except Exception as e:
            print(f"FAILED   : {table}")
            print(e)

    db.session.commit()

    print("=" * 80)
    print(f"Completed. Fixed: {fixed} | Skipped: {skipped}")
    print("=" * 80)