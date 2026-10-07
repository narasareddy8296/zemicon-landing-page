import sqlite3
from pathlib import Path

from flask import current_app, g


DEFAULT_CHARGES = {
    "DIGIKEY_FREE_SHIPPING_THRESHOLD_INR": ("7000", "INR"),
    "DIGIKEY_INTERNATIONAL_FREIGHT_INR": ("1200", "INR"),
    "REMITTANCE_CHARGE_INR": ("3000", "INR"),
    "CHA_PORT_DUES_INR": ("1100", "INR"),
    "DOMESTIC_TRUCKING_INR": ("500", "INR"),
    "IGST_RATE_PERCENT": ("18", "percent"),
}


def _database_path():
    configured = current_app.config.get("LANDING_V2_DATABASE")
    if configured:
        return Path(configured)
    return Path(current_app.instance_path) / "landing_price_v2.sqlite"


def _master_path():
    configured = current_app.config.get("DIGIKEY_MASTER_FILE")
    if configured:
        return Path(configured)
    return Path(current_app.root_path) / "static" / "digikey-1.xlsx"


def get_database():
    cached = g.get("landing_v2_database")
    if cached is not None:
        return cached
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    g.landing_v2_database = connection
    return connection


def close_database(_error=None):
    connection = g.pop("landing_v2_database", None)
    if connection is not None:
        connection.close()


def initialize_database(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS digikey_master (
            mpn_norm TEXT PRIMARY KEY,
            mpn TEXT NOT NULL,
            category TEXT NOT NULL,
            hsn_code TEXT NOT NULL,
            bcd_rate TEXT NOT NULL,
            sws_rate TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS landing_charge_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            currency TEXT NOT NULL,
            effective_from TEXT NOT NULL DEFAULT CURRENT_DATE,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS landing_v2_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO landing_charge_config (key, value, currency)
        VALUES (?, ?, ?)
        """,
        [(key, value, currency) for key, (value, currency) in DEFAULT_CHARGES.items()],
    )
    connection.commit()

    seeded = connection.execute(
        "SELECT value FROM landing_v2_metadata WHERE key = 'master_seeded'"
    ).fetchone()
    if seeded:
        return

    master_path = _master_path()
    if master_path.is_file():
        from .excel_import import read_seed_master
        from .master_lookup import normalize_master_record

        rows = read_seed_master(master_path)
        normalized = [normalize_master_record(row, source="DigiKey Excel", spreadsheet_fraction=True) for row in rows]
        with connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO digikey_master
                    (mpn_norm, mpn, category, hsn_code, bcd_rate, sws_rate, source)
                VALUES (:mpn_norm, :mpn, :category, :hsn_code, :bcd_rate, :sws_rate, :source)
                """,
                normalized,
            )

    with connection:
        connection.execute(
            "INSERT INTO landing_v2_metadata (key, value) VALUES ('master_seeded', '1')"
        )


def get_active_charge_config():
    database = get_database()
    rows = database.execute(
        "SELECT key, value FROM landing_charge_config WHERE active = 1"
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}
