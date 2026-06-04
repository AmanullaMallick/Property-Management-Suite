"""
invoice_engine.py - Itemized billing statement generator (Production Version).
Integrates seamlessly with thread-safe DatabaseManager connection pools.
"""

from typing import List
from datetime import datetime

class InvoiceEngine:
    def __init__(self, db_manager):
        self.db = db_manager

    def generate_statement(self, unit_id: str, period_start: str, period_end: str) -> str:
        """
        Gathers ledger transactional data slices, queries utility logs, 
        and prints a cleanly aligned, plaintext invoice matrix string.
        """
        tenant = self.db.get_tenant(unit_id)
        if not tenant:
            raise ValueError(f"Active tenant {unit_id} not found.")

        all_ledger = self.db.get_ledger_for_tenant(unit_id)

        # Filter ledger transactions for the period safely
        period_txs = [tx for tx in all_ledger if period_start <= tx['transaction_date'] <= period_end]

        # Calculate previous outstanding balance safely by parsing historical data steps
        previous_balance = 0.0
        for tx in all_ledger:
            if tx['transaction_date'] < period_start:
                previous_balance = tx['running_balance']
            else:
                break

        # Sum up standard billing categories
        rent_total = sum(tx['amount'] for tx in period_txs if tx['transaction_type'] == 'Rent Charge')
        maintenance_total = sum(tx['amount'] for tx in period_txs if tx['transaction_type'] == 'Maintenance Split')
        late_fee_total = sum(tx['amount'] for tx in period_txs if tx['transaction_type'] == 'Late Fee')
        brokerage_total = sum(tx['amount'] for tx in period_txs if tx['transaction_type'] == 'Brokerage Expense')
        payments_total = sum(tx['amount'] for tx in period_txs if tx['transaction_type'] == 'Payment Received')

        # Build Statement String Data Block
        lines = []
        lines.append("=" * 60)
        lines.append(f"{'STATEMENT OF ACCOUNT':^60}")
        lines.append(f"  Unit: {unit_id:<10} |  Tenant: {tenant['tenant_name']}")
        lines.append(f"  Billing Period: {period_start}  to  {period_end}")
        lines.append(f"  Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append(f"{'Item Description':<45}{'Amount':>15}")
        lines.append("-" * 60)

        # 1. Print Rent
        if rent_total > 0:
            lines.append(f"{'Base Rent':<45}{self._fmt_amount(rent_total):>15}")

        # 2. Print Utilities (Fixed: Properly routes queries to safe thread links)
        utility_items = self._get_utility_entries(unit_id, period_start, period_end)
        utility_total = 0.0
        for u in utility_items:
            charge = round(u['units_consumed'] * u['tenant_charge_rate'], 2)
            utility_total += charge
            desc = f"{u['utility_type']} ({u['units_consumed']:.1f} units @ ₹{u['tenant_charge_rate']:.2f}/u)"
            lines.append(f"{desc:<45}{self._fmt_amount(charge):>15}")

        # 3. Print Maintenance Splits Individual Line Items
        for tx in period_txs:
            if tx['transaction_type'] == 'Maintenance Split':
                lines.append(f"{tx['description'][:44]:<45}{self._fmt_amount(tx['amount']):>15}")

        # 4. Print Overdue Late Fees
        if late_fee_total > 0:
            lines.append(f"{'Late Fee / Penalties':<45}{self._fmt_amount(late_fee_total):>15}")

        # 5. Print Brokerage
        if brokerage_total > 0:
            lines.append(f"{'Brokerage Finder Fee':<45}{self._fmt_amount(brokerage_total):>15}")

        # Final Master Accounting Ledger Sums
        current_month_charges = rent_total + utility_total + maintenance_total + late_fee_total + brokerage_total
        total_accountable = current_month_charges + previous_balance
        net_outstanding = total_accountable + payments_total  # payments_total is naturally negative

        lines.append("-" * 60)
        lines.append(f"{'TOTAL CURRENT MONTH CHARGES:':<45}{self._fmt_amount(current_month_charges):>15}")
        lines.append(f"{'PREVIOUS OUTSTANDING BALANCE:':<45}{self._fmt_amount(previous_balance):>15}")
        lines.append("-" * 60)
        lines.append(f"{'TOTAL AMOUNT ACCOUNTABLE:':<45}{self._fmt_amount(total_accountable):>15}")
        if payments_total != 0:
            lines.append(f"{'LESS PAYMENTS RECEIVED:':<45}{self._fmt_amount(payments_total):>15}")
        lines.append("-" * 60)
        lines.append(f"{'NET OUTSTANDING BALANCE DUE:':<45}{self._fmt_amount(net_outstanding):>15}")
        lines.append("=" * 60)
        
        if net_outstanding > 0:
            lines.append(f"{'*** Amount Payable Immediately ***':^60}")
        else:
            lines.append(f"{'*** Credit Balance - Settle at Exit ***':^60}")
            
        lines.append("=" * 60)
        lines.append(f"{'Security Deposit Held (Trust Asset):':<45}{self._fmt_amount(tenant['security_deposit_held']):>15}")
        lines.append("=" * 60)
        
        return "\n".join(lines)

    def _get_utility_entries(self, unit_id: str, start: str, end: str) -> List[dict]:
        """
        Correctly queries via the database manager's connection pooling wrapper.
        Safely maps relational rates without manual connection exposures.
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT ul.*, urm.tenant_charge_rate
                   FROM Utility_Logs ul
                   JOIN Utility_Rates_Matrix urm ON ul.rate_applied_id = urm.rate_id
                   WHERE ul.unit_id = ? AND ul.reading_capture_date BETWEEN ? AND ?
                   ORDER BY ul.reading_capture_date""", (unit_id, start, end)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _fmt_amount(amount: float) -> str:
        """Returns clean currency spacing with clear sign rules."""
        if amount < 0:
            return f"-₹{abs(amount):,.2f}"
        return f"₹{amount:,.2f}"