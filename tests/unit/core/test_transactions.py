from kicad_agent.core.transactions import Transaction, TransactionState


def test_transaction_restores_checkpoint_through_callback():
    restored = []
    transaction = Transaction()
    transaction.set_checkpoint(
        {"rollback_supported": True},
        restore_callback=lambda: restored.append(True),
    )

    assert transaction.rollback() is True
    assert restored == [True]
    assert transaction.state is TransactionState.ROLLED_BACK


def test_transaction_records_unsupported_rollback():
    transaction = Transaction()
    transaction.set_checkpoint({"rollback_supported": False})

    assert transaction.rollback() is True
    assert transaction.checkpoint_data["rollback_supported"] is False
    assert "rollback_error" in transaction.checkpoint_data
