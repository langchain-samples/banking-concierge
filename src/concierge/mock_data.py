"""In-memory fake customer data used by the concierge tools."""

from __future__ import annotations

from typing import TypedDict


class Customer(TypedDict):
    customer_id: str
    name: str
    ssn: str
    phone: str
    email: str
    credit_cards: list[dict]
    accounts: list[dict]


class Transaction(TypedDict):
    date: str
    description: str
    amount: float
    type: str


class Branch(TypedDict):
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: str
    hours: str


# NOTE: All PII below is synthetic test data:
#   - SSNs use the 552/553 area (real but not assigned in bulk to fake records)
#   - Credit card numbers are publicly known Stripe/Visa test cards that do not
#     process real payments
#   - Phone numbers use the 555 prefix reserved for fictional use
# This data exists so the LangSmith LLM Gateway's PII / secrets redaction
# policies have realistic-looking values to act on.
CUSTOMERS: dict[str, Customer] = {
    "CUST-0001": {
        "customer_id": "CUST-0001",
        "name": "Alex Rivera",
        "ssn": "552-19-4488",
        "phone": "(415) 555-0142",
        "email": "alex.rivera@example.com",
        "credit_cards": [
            {"brand": "Visa", "number": "4242 4242 4242 4242", "cvv": "314", "exp": "08/29"},
        ],
        "accounts": [
            {"account_id": "1234", "type": "Everyday Checking", "balance": 2418.55},
            {"account_id": "5678", "type": "Way2Save Savings", "balance": 1240.12},
        ],
    },
    "CUST-0002": {
        "customer_id": "CUST-0002",
        "name": "Priya Shah",
        "ssn": "553-22-8810",
        "phone": "(212) 555-0193",
        "email": "priya.shah@example.com",
        "credit_cards": [
            {"brand": "Mastercard", "number": "5555 5555 5555 4444", "cvv": "208", "exp": "11/28"},
            {"brand": "Visa", "number": "4012 8888 8888 1881", "cvv": "551", "exp": "02/30"},
        ],
        "accounts": [
            {"account_id": "2233", "type": "Prime Checking", "balance": 18450.91},
            {"account_id": "4455", "type": "Platinum Savings", "balance": 64210.07},
        ],
    },
    "CUST-0003": {
        "customer_id": "CUST-0003",
        "name": "Jordan Lee",
        "ssn": "552-77-1230",
        "phone": "(650) 555-0117",
        "email": "jordan.lee@example.com",
        "credit_cards": [
            {"brand": "Visa", "number": "4000 0566 5566 5556", "cvv": "099", "exp": "05/27"},
        ],
        "accounts": [
            {"account_id": "9911", "type": "Clear Access Banking", "balance": 312.04},
            {"account_id": "9912", "type": "Way2Save Savings", "balance": 80.00},
        ],
    },
    "CUST-0004": {
        "customer_id": "CUST-0004",
        "name": "Sam Okonkwo",
        "ssn": "553-04-9921",
        "phone": "(704) 555-0133",
        "email": "sam.okonkwo@example.com",
        "credit_cards": [
            {"brand": "Amex", "number": "3782 822463 10005", "cvv": "9876", "exp": "07/31"},
            {"brand": "Visa", "number": "4000 0025 0000 3155", "cvv": "411", "exp": "10/29"},
        ],
        "accounts": [
            {"account_id": "7702", "type": "Premier Checking", "balance": 312_410.55},
            {"account_id": "7703", "type": "Platinum Savings", "balance": 901_233.10},
        ],
    },
    "CUST-0005": {
        "customer_id": "CUST-0005",
        "name": "Maya Patel",
        "ssn": "552-66-3344",
        "phone": "(512) 555-0188",
        "email": "maya.patel@example.com",
        "credit_cards": [
            {"brand": "Discover", "number": "6011 1111 1111 1117", "cvv": "302", "exp": "01/28"},
        ],
        "accounts": [
            {"account_id": "3030", "type": "Everyday Checking", "balance": 84.22},
        ],
    },
}


TRANSACTIONS: dict[str, list[Transaction]] = {
    "CUST-0001": [
        {"date": "2026-05-19", "description": "TRADER JOE'S", "amount": -52.18, "type": "debit"},
        {"date": "2026-05-18", "description": "DIRECT DEPOSIT - ACME CORP", "amount": 2400.00, "type": "credit"},
        {"date": "2026-05-16", "description": "PG&E AUTOPAY", "amount": -118.40, "type": "debit"},
        {"date": "2026-05-15", "description": "ZELLE FROM J SMITH", "amount": 200.00, "type": "credit"},
        {"date": "2026-05-14", "description": "STARBUCKS #4310", "amount": -6.45, "type": "debit"},
        {"date": "2026-05-12", "description": "ATM WITHDRAWAL 555 MARKET ST", "amount": -100.00, "type": "debit"},
        {"date": "2026-05-10", "description": "AMAZON.COM", "amount": -34.99, "type": "debit"},
    ],
    "CUST-0002": [
        {"date": "2026-05-20", "description": "PAYROLL - NORTHSTAR LABS", "amount": 5800.00, "type": "credit"},
        {"date": "2026-05-19", "description": "BLUE BOTTLE COFFEE", "amount": -8.25, "type": "debit"},
        {"date": "2026-05-18", "description": "DELTA AIR LINES", "amount": -612.00, "type": "debit"},
        {"date": "2026-05-17", "description": "WHOLE FOODS MARKET", "amount": -184.55, "type": "debit"},
        {"date": "2026-05-15", "description": "MORTGAGE PMT 2233", "amount": -2840.00, "type": "debit"},
    ],
    "CUST-0003": [
        {"date": "2026-05-19", "description": "STUDENT LOAN", "amount": -212.10, "type": "debit"},
        {"date": "2026-05-18", "description": "CHIPOTLE", "amount": -14.30, "type": "debit"},
        {"date": "2026-05-15", "description": "VENMO PAYMENT", "amount": -25.00, "type": "debit"},
    ],
    "CUST-0004": [
        {"date": "2026-05-20", "description": "TREASURY DIRECT BUY", "amount": -50000.00, "type": "debit"},
        {"date": "2026-05-19", "description": "WIRE TRANSFER OUT - SCHWAB", "amount": -125000.00, "type": "debit"},
        {"date": "2026-05-19", "description": "WIRE FEE - INTL OUT", "amount": -45.00, "type": "debit"},
        {"date": "2026-05-18", "description": "DIVIDEND - VOO ETF", "amount": 3210.55, "type": "credit"},
    ],
    "CUST-0005": [
        {"date": "2026-05-21", "description": "RENT", "amount": -1500.00, "type": "debit"},
        {"date": "2026-05-20", "description": "DOORDASH", "amount": -22.18, "type": "debit"},
    ],
}


BRANCHES: list[Branch] = [
    {
        "name": "Meridian National - Market & 5th",
        "address": "550 Market St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94103",
        "phone": "(415) 555-0100",
        "hours": "Mon-Fri 9am-5pm, Sat 9am-1pm",
    },
    {
        "name": "Meridian National - Embarcadero Center",
        "address": "1 Embarcadero Center",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94111",
        "phone": "(415) 555-0148",
        "hours": "Mon-Fri 9am-5pm",
    },
    {
        "name": "Meridian National - Palo Alto University Ave",
        "address": "420 University Ave",
        "city": "Palo Alto",
        "state": "CA",
        "zip_code": "94301",
        "phone": "(650) 555-0190",
        "hours": "Mon-Fri 9am-5pm, Sat 9am-2pm",
    },
    {
        "name": "Meridian National - Midtown Manhattan",
        "address": "150 E 42nd St",
        "city": "New York",
        "state": "NY",
        "zip_code": "10017",
        "phone": "(212) 555-0220",
        "hours": "Mon-Fri 8:30am-5pm",
    },
    {
        "name": "Meridian National - West Loop Chicago",
        "address": "330 W Madison St",
        "city": "Chicago",
        "state": "IL",
        "zip_code": "60606",
        "phone": "(312) 555-0167",
        "hours": "Mon-Fri 9am-5pm",
    },
    {
        "name": "Meridian National - Downtown Austin",
        "address": "111 Congress Ave",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
        "phone": "(512) 555-0181",
        "hours": "Mon-Fri 9am-5pm, Sat 9am-1pm",
    },
    {
        "name": "Meridian National - Charlotte Uptown",
        "address": "401 S Tryon St",
        "city": "Charlotte",
        "state": "NC",
        "zip_code": "28202",
        "phone": "(704) 555-0153",
        "hours": "Mon-Fri 9am-5pm",
    },
]


BRANCH_VISITS: dict[str, list[dict]] = {
    "CUST-0001": [
        {"date": "2026-05-22", "branch_id": "MNB-SF-MARKET", "branch_name": "Meridian National - Market & 5th", "purpose": "deposit", "teller_name": "A. Patel"},
        {"date": "2026-04-30", "branch_id": "MNB-SF-MARKET", "branch_name": "Meridian National - Market & 5th", "purpose": "notary", "teller_name": "J. Nguyen"},
        {"date": "2026-03-11", "branch_id": "MNB-SF-EMBARC", "branch_name": "Meridian National - Embarcadero Center", "purpose": "safe_deposit", "teller_name": "M. Alvarez"},
    ],
    "CUST-0002": [
        {"date": "2026-05-18", "branch_id": "MNB-NY-MIDTOWN", "branch_name": "Meridian National - Midtown Manhattan", "purpose": "loan_inquiry", "teller_name": "R. Goldberg"},
        {"date": "2026-04-02", "branch_id": "MNB-NY-MIDTOWN", "branch_name": "Meridian National - Midtown Manhattan", "purpose": "deposit", "teller_name": "T. Chen"},
        {"date": "2026-02-14", "branch_id": "MNB-NY-MIDTOWN", "branch_name": "Meridian National - Midtown Manhattan", "purpose": "safe_deposit", "teller_name": "R. Goldberg"},
    ],
    "CUST-0003": [
        {"date": "2026-05-09", "branch_id": "MNB-PA-UNIV", "branch_name": "Meridian National - Palo Alto University Ave", "purpose": "account_opening", "teller_name": "K. Yamada"},
        {"date": "2026-04-21", "branch_id": "MNB-PA-UNIV", "branch_name": "Meridian National - Palo Alto University Ave", "purpose": "deposit", "teller_name": "K. Yamada"},
        {"date": "2026-03-30", "branch_id": "MNB-SF-MARKET", "branch_name": "Meridian National - Market & 5th", "purpose": "notary", "teller_name": "A. Patel"},
    ],
    "CUST-0004": [
        {"date": "2026-05-20", "branch_id": "MNB-CLT-UPTOWN", "branch_name": "Meridian National - Charlotte Uptown", "purpose": "safe_deposit", "teller_name": "D. Okafor"},
        {"date": "2026-05-05", "branch_id": "MNB-CLT-UPTOWN", "branch_name": "Meridian National - Charlotte Uptown", "purpose": "loan_inquiry", "teller_name": "D. Okafor"},
        {"date": "2026-04-12", "branch_id": "MNB-CHI-WLOOP", "branch_name": "Meridian National - West Loop Chicago", "purpose": "deposit", "teller_name": "S. Kowalski"},
    ],
    "CUST-0005": [
        {"date": "2026-05-15", "branch_id": "MNB-AUS-CONGRESS", "branch_name": "Meridian National - Downtown Austin", "purpose": "deposit", "teller_name": "L. Hernandez"},
        {"date": "2026-04-08", "branch_id": "MNB-AUS-CONGRESS", "branch_name": "Meridian National - Downtown Austin", "purpose": "notary", "teller_name": "L. Hernandez"},
        {"date": "2026-03-02", "branch_id": "MNB-AUS-CONGRESS", "branch_name": "Meridian National - Downtown Austin", "purpose": "account_opening", "teller_name": "B. Reyes"},
    ],
}


def find_branch_by_zip(zip_code: str) -> Branch | None:
    """Return the branch whose zip matches; otherwise the first branch in the same first-3-digit region."""
    for branch in BRANCHES:
        if branch["zip_code"] == zip_code:
            return branch
    prefix = zip_code[:3]
    for branch in BRANCHES:
        if branch["zip_code"].startswith(prefix):
            return branch
    return None
