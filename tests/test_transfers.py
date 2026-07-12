"""Transfer service tests (WH-03): register_transfer + recent_transfers.

Pitfall 1 backstop: "transfer" must be registered in THREE runtime
collections at once (OPERATION_TYPES, OPERATION_TYPE_LABELS,
STOCK_AFFECTING_TYPES) or record_operation silently mistreats it.
"""

from app.models import OPERATION_TYPE_LABELS, OPERATION_TYPES
from app.services.ledger import STOCK_AFFECTING_TYPES


def test_transfer_type_registered():
    assert "transfer" in OPERATION_TYPES
    assert "transfer" in OPERATION_TYPE_LABELS
    assert OPERATION_TYPE_LABELS["transfer"]
    assert "transfer" in STOCK_AFFECTING_TYPES
