# services/nigerian_banks.py
"""
Nigerian Banks Directory
========================
Complete list of Nigerian banks with their transfer codes.
Compatible with Squad, Paystack, and Flutterwave.

Usage:
    from services.nigerian_banks import NIGERIAN_BANKS, get_bank_by_code, search_banks

    # Full list for frontend dropdown
    banks = NIGERIAN_BANKS

    # Lookup by code
    bank = get_bank_by_code('058')  # → {'code': '058', 'name': 'Guaranty Trust Bank'}

    # Search
    results = search_banks('access')  # → [{'code': '044', 'name': 'Access Bank'}, ...]
"""

NIGERIAN_BANKS = [
    {'code': '044', 'name': 'Access Bank'},
    {'code': '063', 'name': 'Access Bank (Diamond)'},
    {'code': '035A', 'name': 'ALAT by WEMA'},
    {'code': '401', 'name': 'ASO Savings and Loans'},
    {'code': '023', 'name': 'Citibank Nigeria'},
    {'code': '050', 'name': 'Ecobank Nigeria'},
    {'code': '562', 'name': 'Ekondo Microfinance Bank'},
    {'code': '070', 'name': 'Fidelity Bank'},
    {'code': '011', 'name': 'First Bank of Nigeria'},
    {'code': '214', 'name': 'First City Monument Bank (FCMB)'},
    {'code': '058', 'name': 'Guaranty Trust Bank (GTBank)'},
    {'code': '030', 'name': 'Heritage Bank'},
    {'code': '301', 'name': 'Jaiz Bank'},
    {'code': '082', 'name': 'Keystone Bank'},
    {'code': '606', 'name': 'Kuda Bank'},
    {'code': '526', 'name': 'Parallex Bank'},
    {'code': '076', 'name': 'Polaris Bank'},
    {'code': '101', 'name': 'Providus Bank'},
    {'code': '125', 'name': 'Rubies MFB'},
    {'code': '100', 'name': 'Suntrust Bank'},
    {'code': '032', 'name': 'Union Bank of Nigeria'},
    {'code': '033', 'name': 'United Bank for Africa (UBA)'},
    {'code': '215', 'name': 'Unity Bank'},
    {'code': '035', 'name': 'Wema Bank'},
    {'code': '057', 'name': 'Zenith Bank'},
    {'code': '304', 'name': 'Stanbic IBTC Bank'},
    {'code': '068', 'name': 'Standard Chartered Bank'},
    {'code': '221', 'name': 'Stanbic Mobile'},
    {'code': '501', 'name': 'Mutual Trust Microfinance Bank'},
    {'code': '090175', 'name': 'PalmPay'},
    {'code': '999991', 'name': 'OPay (PayCom)'},
    {'code': '090405', 'name': 'Moniepoint MFB'},
    {'code': '50515', 'name': 'Carbon (One Finance)'},
    {'code': '000013', 'name': 'GTBank MFB'},            # Squad MFB code
    {'code': '090267', 'name': 'Kuda Microfinance Bank'},
    {'code': '120001', 'name': ' 9PSB (9 Payment Service Bank)'},
    {'code': '090110', 'name': 'VFD Microfinance Bank'},
    {'code': '090303', 'name': 'Mint MFB'},
    {'code': '090129', 'name': 'Boctrust Microfinance Bank'},
    {'code': '090317', 'name': 'PatrickGold Microfinance Bank'},
    {'code': '090115', 'name': 'TCF MFB'},
    {'code': '090251', 'name': 'Covenant MFB'},
    {'code': '090300', 'name': 'FBN Mortgages Limited'},
    {'code': '090112', 'name': 'VFD MFB'},
    
]

# Sort alphabetically for clean dropdown display
NIGERIAN_BANKS = sorted(NIGERIAN_BANKS, key=lambda b: b['name'])

_CODE_INDEX = {b['code']: b for b in NIGERIAN_BANKS}
_NAME_INDEX  = {b['name'].lower(): b for b in NIGERIAN_BANKS}


def get_bank_by_code(code: str) -> dict | None:
    """Return bank dict by code, or None if not found."""
    return _CODE_INDEX.get(code)


def get_bank_name(code: str) -> str:
    """Return bank name string by code, or empty string."""
    bank = _CODE_INDEX.get(code)
    return bank['name'] if bank else ''


def search_banks(query: str) -> list[dict]:
    """Case-insensitive search across bank names."""
    q = query.lower().strip()
    return [b for b in NIGERIAN_BANKS if q in b['name'].lower()]