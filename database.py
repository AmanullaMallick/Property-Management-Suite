"""
database.py - Production-grade SQLite Storage Engine for PropManager Pro.
Handles active tenant states, ledger records, binary image storage, rate matrix,
late fee automation, move-out archiving, and rental agreement ingestion.
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# ----------------------------------------------------------------------
# Global Configuration Metrics
# ----------------------------------------------------------------------
LATE_FEE_PERCENTAGE = 0.02   # 2% of outstanding rent
GRACE_PERIOD_DAYS = 5        # Days after rent due before late fee applies


class DatabaseManager:
    """Central database handler for all tenant, ledger, utility, and archival operations."""

    def __init__(self, db_directory: str):
        self.db_directory = db_directory
        self.db_path = os.path.join(db_directory, "active_ledger.db")
        self._init_db()

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------
    def _get_connection(self):
        """Returns a connection with foreign keys enforced and rows as dicts."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ------------------------------------------------------------------
    # Schema Initialization & Seeds
    # ------------------------------------------------------------------
    def _init_db(self):
        """Create tables and seed baseline utility rates if absent."""
        with self._get_connection() as conn:
            conn.executescript("""
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS Tenants (
                    unit_id TEXT PRIMARY KEY,
                    tenant_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    permanent_address TEXT NOT NULL,
                    govt_id_type TEXT NOT NULL,
                    govt_id_number TEXT NOT NULL,
                    base_rent REAL NOT NULL,
                    security_deposit_held REAL NOT NULL DEFAULT 0.0,
                    parent_1_name TEXT NOT NULL,
                    parent_1_phone TEXT NOT NULL,
                    parent_2_name TEXT,
                    parent_2_phone TEXT,
                    profession_type TEXT CHECK(profession_type IN (
                        'Student', 'Working Professional', 'Government', 'Private', 'Other'
                    )),
                    organization_or_college TEXT,
                    designation_or_course TEXT,
                    required_notice_days INTEGER NOT NULL DEFAULT 30,
                    notice_penalty_type TEXT NOT NULL DEFAULT 'Forfeit Full Security',
                    onboarding_date TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Archived')),
                    water_fixed_charge REAL NOT NULL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS Tenant_Documents (
                    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id TEXT NOT NULL,
                    document_type TEXT NOT NULL CHECK(document_type IN ('Rental Agreement', 'Other')),
                    file_path TEXT NOT NULL,
                    FOREIGN KEY (unit_id) REFERENCES Tenants(unit_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS Utility_Rates_Matrix (
                    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    effective_date TEXT NOT NULL,
                    utility_type TEXT NOT NULL CHECK(utility_type IN ('Electricity', 'Water')),
                    landlord_base_rate REAL NOT NULL,
                    tenant_charge_rate REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS Utility_Logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id TEXT NOT NULL,
                    utility_type TEXT NOT NULL CHECK(utility_type IN ('Electricity', 'Water')),
                    billing_period TEXT NOT NULL,
                    previous_reading REAL NOT NULL,
                    current_reading REAL NOT NULL,
                    units_consumed REAL NOT NULL,
                    rate_applied_id INTEGER NOT NULL,
                    reading_capture_date TEXT NOT NULL,
                    meter_image_blob BLOB,
                    FOREIGN KEY (unit_id) REFERENCES Tenants(unit_id) ON DELETE CASCADE,
                    FOREIGN KEY (rate_applied_id) REFERENCES Utility_Rates_Matrix(rate_id)
                );

                CREATE TABLE IF NOT EXISTS Financial_Ledger (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id TEXT NOT NULL,
                    transaction_date TEXT NOT NULL,
                    log_timestamp TEXT NOT NULL,
                    transaction_type TEXT NOT NULL CHECK(transaction_type IN (
                        'Rent Charge', 'Utility Charge', 'Maintenance Split',
                        'Late Fee', 'Brokerage Expense', 'Payment Received'
                    )),
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    running_balance REAL NOT NULL,
                    FOREIGN KEY (unit_id) REFERENCES Tenants(unit_id) ON DELETE CASCADE
                );
            """)

            # Seed initial utility rates if the matrix is empty
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Utility_Rates_Matrix")
            if cursor.fetchone() == 0:
                today = datetime.now().strftime("%Y-%m-%d")
                cursor.execute(
                    "INSERT INTO Utility_Rates_Matrix (effective_date, utility_type, landlord_base_rate, tenant_charge_rate) VALUES (?, 'Electricity', 7.00, 12.00)",
                    (today,)
                )
                cursor.execute(
                    "INSERT INTO Utility_Rates_Matrix (effective_date, utility_type, landlord_base_rate, tenant_charge_rate) VALUES (?, 'Water', 4.00, 6.00)",
                    (today,)
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Tenant CRUD (Correctly Nested Under Class Scope)
    # ------------------------------------------------------------------
    def add_tenant(self, data: dict) -> None:
        """Insert a raw tenant profile configuration block."""
        with self._get_connection() as conn:
            placeholders = ', '.join(['?'] * len(data))
            columns = ', '.join(data.keys())
            conn.execute(f"INSERT INTO Tenants ({columns}) VALUES ({placeholders})", list(data.values()))
            conn.commit()

    def get_tenant(self, unit_id: str) -> Optional[Dict]:
        """Fetches active tenant dataset properties."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM Tenants WHERE unit_id = ? AND status = 'Active'", (unit_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_active_tenants(self) -> List[Dict]:
        """Fetches list pointers for UI dashboard grids."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM Tenants WHERE status = 'Active' ORDER BY unit_id"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_tenant(self, unit_id: str, **kwargs) -> None:
        """Modifies targeted column fields safely."""
        allowed = {
            "tenant_name", "phone", "email", "permanent_address",
            "govt_id_type", "govt_id_number", "base_rent", "security_deposit_held",
            "parent_1_name", "parent_1_phone", "parent_2_name", "parent_2_phone",
            "profession_type", "organization_or_college", "designation_or_course",
            "required_notice_days", "notice_penalty_type", "water_fixed_charge"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [unit_id]
        with self._get_connection() as conn:
            conn.execute(f"UPDATE Tenants SET {set_clause} WHERE unit_id = ?", values)
            conn.commit()

    # ------------------------------------------------------------------
    # Rental Agreement Ingestion
    # ------------------------------------------------------------------
    def attach_rental_agreement(self, unit_id: str, source_pdf_path: str) -> str:
        """Copies PDF, renames to Unit_<id>_Rental_Agreement.pdf, and records path."""
        docs_dir = os.path.join(self.db_directory, "documents")
        os.makedirs(docs_dir, exist_ok=True)
        dest_filename = f"Unit_{unit_id}_Rental_Agreement.pdf"
        dest_path = os.path.join(docs_dir, dest_filename)
        shutil.copy2(source_pdf_path, dest_path)

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO Tenant_Documents (unit_id, document_type, file_path) VALUES (?, 'Rental Agreement', ?)",
                (unit_id, dest_path)
            )
            conn.commit()
        return dest_path

    def get_tenant_documents(self, unit_id: str) -> List[Dict]:
        """Returns document tracking arrays link paths."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM Tenant_Documents WHERE unit_id = ?", (unit_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Utility Rates (Effective-Date Aware Matrix Engine)
    # ------------------------------------------------------------------
    def add_utility_rate(self, effective_date: str, utility_type: str,
                         landlord_rate: float, tenant_rate: float) -> int:
        """Injects custom variable rate scales without breaking historic log links."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO Utility_Rates_Matrix
                   (effective_date, utility_type, landlord_base_rate, tenant_charge_rate)
                   VALUES (?,?,?,?)""",
                (effective_date, utility_type, landlord_rate, tenant_rate)
            )
            conn.commit()
            return cur.lastrowid

    def get_active_rate(self, utility_type: str, for_date: str) -> Optional[Dict]:
        """Returns the rate effective on or before 'for_date' (YYYY-MM-DD)."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM Utility_Rates_Matrix
                   WHERE utility_type = ? AND effective_date <= ?
                   ORDER BY effective_date DESC LIMIT 1""",
                (utility_type, for_date)
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Utility Reading Logging (Atomic with Financial Posting)
    # ------------------------------------------------------------------
    def log_utility_reading(self, unit_id: str, u_type: str, billing_period: str,
                            current_reading: float, capture_date: str,
                            image_blob: Optional[bytes] = None) -> None:
        """Inserts utility log and corresponding ledger charge within a single transaction."""
        with self._get_connection() as conn:
            prev_row = conn.execute(
                """SELECT current_reading FROM Utility_Logs
                   WHERE unit_id = ? AND utility_type = ?
                   ORDER BY reading_capture_date DESC, log_id DESC LIMIT 1""",
                (unit_id, u_type)
            ).fetchone()
            prev_reading = prev_row['current_reading'] if prev_row else 0.0

            units_used = round(current_reading - prev_reading, 2)
            if units_used < 0:
                raise ValueError("Current reading cannot be lower than previous reading.")

            rate = self.get_active_rate(u_type, capture_date)
            if not rate:
                raise ValueError(f"No utility rate found for {u_type} on {capture_date}.")
            rate_id = rate['rate_id']
            unit_charge = round(units_used * rate['tenant_charge_rate'], 2)

            # 1. Log structural metrics entry data
            conn.execute(
                """INSERT INTO Utility_Logs
                   (unit_id, utility_type, billing_period, previous_reading,
                    current_reading, units_consumed, rate_applied_id,
                    reading_capture_date, meter_image_blob)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (unit_id, u_type, billing_period, prev_reading, current_reading,
                 units_used, rate_id, capture_date, image_blob)
            )

            # 2. Append balance charge instantly to ledger flow
            if unit_charge > 0:
                self._post_ledger_entry(
                    conn, unit_id, capture_date, 'Utility Charge',
                    f"{u_type} ({units_used} u @ ₹{rate['tenant_charge_rate']}/u)",
                    unit_charge
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Financial Ledger Operations (Atomic, Running Balance)
    # ------------------------------------------------------------------
    def _post_ledger_entry(self, conn: sqlite3.Connection, unit_id: str,
                           transaction_date: str, transaction_type: str,
                           description: str, amount: float) -> None:
        """Internal helper: posts a ledger row and updates running balance securely."""
        last_row = conn.execute(
            """SELECT running_balance FROM Financial_Ledger
               WHERE unit_id = ?
               ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1""",
            (unit_id,)
        ).fetchone()
        current_balance = last_row['running_balance'] if last_row else 0.0
        new_balance = round(current_balance + amount, 2)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT INTO Financial_Ledger
               (unit_id, transaction_date, log_timestamp, transaction_type,
                description, amount, running_balance)
               VALUES (?,?,?,?,?,?,?)""",
            (unit_id, transaction_date, now, transaction_type, description, amount, new_balance)
        )

    def post_payment(self, unit_id: str, amount: float, effective_date: str,
                     description: str = "Rent Payment") -> None:
        """Record a payment received transaction line item."""
        with self._get_connection() as conn:
            self._post_ledger_entry(conn, unit_id, effective_date,
                                    'Payment Received', description, -amount)
            conn.commit()

    def post_charge(self, unit_id: str, charge_type: str, amount: float,
                    effective_date: str, description: str) -> None:
        """Post any positive fee charge balance modifier allocation."""
        with self._get_connection() as conn:
            self._post_ledger_entry(conn, unit_id, effective_date,
                                    charge_type, description, amount)
            conn.commit()

    def get_ledger_for_tenant(self, unit_id: str) -> List[Dict]:
        """Returns transactional chronological lists."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM Financial_Ledger WHERE unit_id = ?
                   ORDER BY transaction_date ASC, transaction_id ASC""",
                (unit_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_current_balance(self, unit_id: str) -> float:
        """Pulls true net system liability index values."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT running_balance FROM Financial_Ledger
                   WHERE unit_id = ?
                   ORDER BY transaction_date DESC, transaction_id DESC LIMIT 1""",
                (unit_id,)
            ).fetchone()
            return row['running_balance'] if row else 0.0

    # ------------------------------------------------------------------
    # Onboarding Wizard Execution Pipelines
    # ------------------------------------------------------------------
    def onboard_tenant(self, tenant_data: dict, brokerage_fee: float = 0.0) -> None:
        """Creates tenant profile, posts first rent charge, and records brokerage expense."""
        with self._get_connection() as conn:
            columns = ', '.join(tenant_data.keys())
            placeholders = ', '.join(['?'] * len(tenant_data))
            conn.execute(
                f"INSERT INTO Tenants ({columns}) VALUES ({placeholders})",
                list(tenant_data.values())
            )

            self._post_ledger_entry(
                conn, tenant_data['unit_id'], tenant_data['onboarding_date'],
                'Rent Charge', 'First Month Rent (Onboarding)', tenant_data['base_rent']
            )

            if brokerage_fee > 0:
                self._post_ledger_entry(
                    conn, tenant_data['unit_id'], tenant_data['onboarding_date'],
                    'Brokerage Expense', 'Upfront Brokerage Fee', -brokerage_fee
                )
            conn.commit()

    # ------------------------------------------------------------------
    # Automated Late Fee Engine (FIFO Logic Engine)
    # ------------------------------------------------------------------
    def apply_late_fees(self, unit_id: str, as_of_date: str = None) -> int:
        """
        Scans all rent charges, checks if overdue beyond grace period,
        and posts one late fee per unpaid rent period via FIFO allocation maps.
        """
        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y-%m-%d")
        as_of_dt = datetime.strptime(as_of_date, "%Y-%m-%d")

        tenant = self.get_tenant(unit_id)
        if not tenant:
            return 0

        try:
            onboard_dt = datetime.strptime(tenant['onboarding_date'], "%Y-%m-%d")
            due_day = onboard_dt.day
        except:
            due_day = 1

        with self._get_connection() as conn:
            ledger = conn.execute(
                "SELECT * FROM Financial_Ledger WHERE unit_id = ? ORDER BY transaction_date, transaction_id",
                (unit_id,)
            ).fetchall()

            outstanding_rents = []
            for tx in ledger:
                if tx['transaction_type'] == 'Rent Charge':
                    tx_dt = datetime.strptime(tx['transaction_date'], "%Y-%m-%d")
                    try:
                        due_date = tx_dt.replace(day=due_day)
                    except ValueError:
                        # Fallback for short months (e.g., matching 31st on Feb)
                        due_date = tx_dt + timedelta(days=1)
                    outstanding_rents.append({
                        'txn_id': tx['transaction_id'],
                        'amount': tx['amount'],
                        'due_date': due_date,
                        'description': tx['description']
                    })
                elif tx['transaction_type'] == 'Payment Received':
                    remaining = -tx['amount']
                    for rent in outstanding_rents[:]:
                        if remaining <= 0:
                            break
                        if rent['amount'] <= remaining:
                            remaining -= rent['amount']
                            outstanding_rents.remove(rent)
                        else:
                            rent['amount'] -= remaining
                            remaining = 0
                            break

            new_fees = 0
            for rent in outstanding_rents:
                if rent['due_date'] + timedelta(days=GRACE_PERIOD_DAYS) < as_of_dt:
                    late_desc = f"Late fee for rent due {rent['due_date'].strftime('%Y-%m-%d')}"
                    existing = conn.execute(
                        "SELECT COUNT(*) FROM Financial_Ledger WHERE unit_id = ? AND transaction_type = 'Late Fee' AND description = ?",
                        (unit_id, late_desc)
                    ).fetchone()
                    if existing == 0:
                        fee = round(rent['amount'] * LATE_FEE_PERCENTAGE, 2)
                        if fee > 0:
                            self._post_ledger_entry(conn, unit_id, as_of_date,
                                                    'Late Fee', late_desc, fee)
                            new_fees += 1

            conn.commit()
            return new_fees

    # ------------------------------------------------------------------
    # Move-Out Archive & Surgical Purge Flow
    # ------------------------------------------------------------------
    def archive_tenant(self, unit_id: str, leaving_date: str) -> float:
        """
        Calculates refund (penalty + final balance), creates a standalone database 
        in Old_Tenants_Archive/Year_YYYY/, copies all asset data, and purges workspace.
        """
        tenant = self.get_tenant(unit_id)
        if not tenant:
            raise ValueError("Active tenant profile statement reference target completely missing.")

        penalty = 0.0
        if tenant['notice_penalty_type'] == 'Forfeit Full Security':
            penalty = tenant['security_deposit_held']
        elif tenant['notice_penalty_type'].startswith('Fixed'):
            try:
                penalty = float(tenant['notice_penalty_type'].split()[-1])
            except:
                penalty = 0.0

        final_balance = self.get_current_balance(unit_id)
        net_refund = tenant['security_deposit_held'] - final_balance - penalty

        year = datetime.strptime(leaving_date, "%Y-%m-%d").year
        archive_dir = os.path.join(self.db_directory, "Old_Tenants_Archive", f"Year_{year}")
        os.makedirs(archive_dir, exist_ok=True)
        safe_name = "".join(c for c in tenant['tenant_name'] if c.isalnum() or c == ' ').replace(' ', '_')
        archive_path = os.path.join(archive_dir, f"Unit_{unit_id}_{safe_name}.db")

        with self._get_connection() as conn:
            conn.execute("ATTACH DATABASE ? AS archive", (archive_path,))

            conn.execute("CREATE TABLE archive.Tenants AS SELECT * FROM main.Tenants WHERE unit_id = ?", (unit_id,))
            conn.execute("CREATE TABLE archive.Tenant_Documents AS SELECT * FROM main.Tenant_Documents WHERE unit_id = ?", (unit_id,))
            conn.execute("""
                CREATE TABLE archive.Utility_Rates_Matrix AS
                SELECT DISTINCT URM.* FROM main.Utility_Rates_Matrix URM
                JOIN main.Utility_Logs UL ON URM.rate_id = UL.rate_applied_id
                WHERE UL.unit_id = ?
            """, (unit_id,))
            conn.execute("CREATE TABLE archive.Utility_Logs AS SELECT * FROM main.Utility_Logs WHERE unit_id = ?", (unit_id,))
            conn.execute("CREATE TABLE archive.Financial_Ledger AS SELECT * FROM main.Financial_Ledger WHERE unit_id = ?", (unit_id,))

            conn.execute("DETACH archive")
            conn.execute("DELETE FROM Tenants WHERE unit_id = ?", (unit_id,))
            conn.commit()

        return round(net_refund, 2)

    # ------------------------------------------------------------------
    # Utility Arbitrage Profit Metrics Dashboard Tracker
    # ------------------------------------------------------------------
    def get_utility_arbitrage_metrics(self) -> Dict[str, float]:
        """Calculates true net profit margins on sub-meter pricing distributions."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    UL.utility_type,
                    SUM(UL.units_consumed * URM.tenant_charge_rate) as total_charged,
                    SUM(UL.units_consumed * URM.landlord_base_rate) as total_cost
                FROM Utility_Logs UL
                JOIN Utility_Rates_Matrix URM ON UL.rate_applied_id = URM.rate_id
                GROUP BY UL.utility_type
            """).fetchall()
            metrics = {"Electricity": 0.0, "Water": 0.0}
            for r in rows:
                profit = (r['total_charged'] or 0.0) - (r['total_cost'] or 0.0)
                metrics[r['utility_type']] = round(profit, 2)
            return metrics

    # New method added for fixed water charge posting
    def post_fixed_water_charge(self, unit_id: str, month_date: str) -> None:
        '''
        Posts a fixed water charge for the given month if water_fixed_charge > 0.
        month_date should be 'YYYY-MM-01' (first day of the billing month).
        '''
        tenant = self.get_tenant(unit_id)
        if not tenant or tenant['water_fixed_charge'] <= 0:
            return
        desc = f"Fixed Water Charge - {month_date[:7]}"
        existing = self.get_ledger_for_tenant(unit_id)
        if any(tx['transaction_type'] == 'Utility Charge' and desc in tx['description'] for tx in existing):
            return
        self.post_charge(
            unit_id,
            "Utility Charge",
            tenant['water_fixed_charge'],
            month_date,
            desc
        )


# ------------------------------------------------------------------
# Read-Only Archive Access (Static Independent Link Wrapper)
# ------------------------------------------------------------------
@staticmethod
def open_archive_read_only(archive_path: str) -> sqlite3.Connection:
    """Returns an isolated read-only connector channel path target."""
    uri = f"file:{archive_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn