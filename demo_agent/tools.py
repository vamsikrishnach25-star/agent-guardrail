"""
Toy tools for the finance demo agent. These simulate what would normally
be real API calls (a banking backend, a user-management system, etc).
Week 10 (multi-agent phase) adds a second/third tool set for other agents -
this file intentionally stays simple for now.
"""

ACCOUNTS = {"ACC1234": 100000, "ACC5678": 50000}
USERS = {"user_1": "active", "user_2": "active"}


def get_balance(account: str) -> dict:
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account}")
    return {"account": account, "balance": ACCOUNTS[account]}


def transfer_money(amount: float, account: str) -> dict:
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account}")
    if ACCOUNTS[account] < amount:
        raise ValueError("insufficient funds")
    ACCOUNTS[account] -= amount
    return {"account": account, "amount": amount, "new_balance": ACCOUNTS[account]}


def delete_user(user_id: str) -> dict:
    if user_id not in USERS:
        raise ValueError(f"unknown user {user_id}")
    USERS[user_id] = "deleted"
    return {"user_id": user_id, "status": "deleted"}
