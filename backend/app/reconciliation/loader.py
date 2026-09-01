"""CSV loader and validator for reconciliation engine."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, ValidationError

from backend.app.models import Payment, SettlementRecord, BankTransaction, PaymentStatus, SettlementEntityType, TransactionType


class LoadedData(BaseModel):
    """Container for all loaded CSV data."""
    payments: list[Payment] = Field(default_factory=list)
    settlements: list[SettlementRecord] = Field(default_factory=list)
    bank_transactions: list[BankTransaction] = Field(default_factory=list)


class CSVLoadError(Exception):
    """Error during CSV loading/validation."""
    pass


class CSVLoader:
    """Load and validate CSV files for reconciliation."""
    
    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        """Parse ISO 8601 datetime string."""
        if not value or not value.strip():
            raise ValueError("Empty datetime value")
        
        # Try ISO 8601 formats
        for fmt in [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse datetime: {value}")
    
    @staticmethod
    def _parse_int(value: str, field_name: str) -> int:
        """Parse integer value."""
        if not value or not value.strip():
            raise ValueError(f"Empty {field_name}")
        try:
            return int(value.strip())
        except ValueError:
            raise ValueError(f"Invalid integer for {field_name}: {value}")
    
    @staticmethod
    def _normalize_str(value: Optional[str]) -> Optional[str]:
        """Normalize string by trimming whitespace. Return None for empty."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized if normalized else None
    
    @staticmethod
    def load_payments(csv_path: Path) -> list[Payment]:
        """Load and validate payments.csv."""
        payments = []
        
        if not csv_path.exists():
            raise CSVLoadError(f"Payments file not found: {csv_path}")
        
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                required_cols = {"payment_id", "order_id", "customer_id", "amount", "currency", "payment_date", "status"}
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    missing = required_cols - set(reader.fieldnames or [])
                    raise CSVLoadError(f"Missing required columns in payments.csv: {missing}")
                
                for i, row in enumerate(reader, start=2):  # Line 2 is first data row
                    try:
                        payment = Payment(
                            payment_id=CSVLoader._normalize_str(row["payment_id"]) or "",
                            order_id=CSVLoader._normalize_str(row["order_id"]) or "",
                            customer_id=CSVLoader._normalize_str(row["customer_id"]) or "",
                            amount=CSVLoader._parse_int(row["amount"], "amount"),
                            currency=CSVLoader._normalize_str(row["currency"]) or "INR",
                            payment_date=CSVLoader._parse_datetime(row["payment_date"]),
                            status=PaymentStatus(CSVLoader._normalize_str(row["status"]) or "pending"),
                            refund_amount=CSVLoader._parse_int(row.get("refund_amount", "0"), "refund_amount"),
                        )
                        payments.append(payment)
                    except (ValueError, ValidationError) as e:
                        raise CSVLoadError(f"Invalid payment at line {i}: {e}")
        
        except (IOError, UnicodeDecodeError) as e:
            raise CSVLoadError(f"Error reading payments.csv: {e}")
        
        return payments
    
    @staticmethod
    def load_settlements(csv_path: Path) -> list[SettlementRecord]:
        """Load and validate settlement_recon.csv."""
        settlements = []
        
        if not csv_path.exists():
            raise CSVLoadError(f"Settlement file not found: {csv_path}")
        
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                required_cols = {
                    "entity_id", "type", "settlement_id", "settlement_utr",
                    "amount", "debit", "credit", "fee", "tax", "settled_at", "description"
                }
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    missing = required_cols - set(reader.fieldnames or [])
                    raise CSVLoadError(f"Missing required columns in settlement_recon.csv: {missing}")
                
                for i, row in enumerate(reader, start=2):
                    try:
                        settlement = SettlementRecord(
                            entity_id=CSVLoader._normalize_str(row["entity_id"]) or "",
                            type=SettlementEntityType(CSVLoader._normalize_str(row["type"]) or "payment"),
                            payment_id=CSVLoader._normalize_str(row.get("payment_id")),
                            order_id=CSVLoader._normalize_str(row.get("order_id")),
                            settlement_id=CSVLoader._normalize_str(row["settlement_id"]) or "",
                            settlement_utr=CSVLoader._normalize_str(row["settlement_utr"]) or "",
                            amount=CSVLoader._parse_int(row["amount"], "amount"),
                            debit=CSVLoader._parse_int(row["debit"], "debit"),
                            credit=CSVLoader._parse_int(row["credit"], "credit"),
                            fee=CSVLoader._parse_int(row["fee"], "fee"),
                            tax=CSVLoader._parse_int(row["tax"], "tax"),
                            settled_at=CSVLoader._parse_datetime(row["settled_at"]),
                            description=CSVLoader._normalize_str(row["description"]) or "",
                        )
                        settlements.append(settlement)
                    except (ValueError, ValidationError) as e:
                        raise CSVLoadError(f"Invalid settlement at line {i}: {e}")
        
        except (IOError, UnicodeDecodeError) as e:
            raise CSVLoadError(f"Error reading settlement_recon.csv: {e}")
        
        return settlements
    
    @staticmethod
    def load_bank_transactions(csv_path: Path) -> list[BankTransaction]:
        """Load and validate bank_transactions.csv."""
        bank_transactions = []
        
        if not csv_path.exists():
            raise CSVLoadError(f"Bank transactions file not found: {csv_path}")
        
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                required_cols = {
                    "bank_transaction_id", "transaction_date", "description",
                    "amount", "transaction_type"
                }
                if not required_cols.issubset(set(reader.fieldnames or [])):
                    missing = required_cols - set(reader.fieldnames or [])
                    raise CSVLoadError(f"Missing required columns in bank_transactions.csv: {missing}")
                
                for i, row in enumerate(reader, start=2):
                    try:
                        bank_transaction = BankTransaction(
                            bank_transaction_id=CSVLoader._normalize_str(row["bank_transaction_id"]) or "",
                            transaction_date=CSVLoader._parse_datetime(row["transaction_date"]),
                            description=CSVLoader._normalize_str(row["description"]) or "",
                            amount=CSVLoader._parse_int(row["amount"], "amount"),
                            transaction_type=TransactionType(CSVLoader._normalize_str(row["transaction_type"]) or "credit"),
                            utr=CSVLoader._normalize_str(row.get("utr")),
                        )
                        bank_transactions.append(bank_transaction)
                    except (ValueError, ValidationError) as e:
                        raise CSVLoadError(f"Invalid bank transaction at line {i}: {e}")
        
        except (IOError, UnicodeDecodeError) as e:
            raise CSVLoadError(f"Error reading bank_transactions.csv: {e}")
        
        return bank_transactions
    
    @staticmethod
    def load_all(data_dir: Path) -> LoadedData:
        """Load all three CSV files from a directory."""
        payments_path = data_dir / "payments.csv"
        settlements_path = data_dir / "settlement_recon.csv"
        bank_path = data_dir / "bank_transactions.csv"
        
        payments = CSVLoader.load_payments(payments_path)
        settlements = CSVLoader.load_settlements(settlements_path)
        bank_transactions = CSVLoader.load_bank_transactions(bank_path)
        
        return LoadedData(
            payments=payments,
            settlements=settlements,
            bank_transactions=bank_transactions,
        )
