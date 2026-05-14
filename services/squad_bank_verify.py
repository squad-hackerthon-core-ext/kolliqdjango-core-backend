# services/squad_bank_verify.py
"""
Squad Bank Account Verification
=================================
Adds account name lookup to your existing SquadService.
Paste the verify_bank_account method into your SquadService class,
or use this standalone function directly.

Squad endpoint:
  POST /payout/account/lookup
  { "bank_code": "058", "account_number": "0123456789" }

Response:
  { "status": 200, "data": { "account_name": "JOHN DOE", "account_number": "...", "bank_code": "..." } }
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Standalone function (can be used without SquadService) ────────────────────

def verify_bank_account(bank_code: str, account_number: str) -> dict:
    """
    Verify a Nigerian bank account number via Squad's account lookup API.

    Returns:
        {
            'verified': True,
            'account_name': 'JOHN DOE',
            'account_number': '0123456789',
            'bank_code': '058',
        }

    Raises:
        ValueError: if Squad returns an error or account not found
        requests.RequestException: on network failure
    """
    url = f"{settings.SQUAD_BASE_URL}/payout/account/lookup"

    headers = {
        'Authorization': f'Bearer {settings.SQUAD_SECRET_KEY}',
        'Content-Type':  'application/json',
    }

    payload = {
        'bank_code':      bank_code,
        'account_number': account_number,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()
    except requests.RequestException as e:
        logger.error(f"Squad bank verify network error: {e}")
        raise

    if response.status_code != 200 or data.get('status') not in (200, '200'):
        message = data.get('message', 'Account verification failed')
        logger.warning(
            f"Squad bank verify failed: bank={bank_code} "
            f"acct={account_number} response={data}"
        )
        raise ValueError(message)

    account_data = data.get('data', {})
    account_name = account_data.get('account_name', '').strip()

    if not account_name:
        raise ValueError('Account name not returned by bank')

    logger.info(
        f"Bank verified: {account_number} ({bank_code}) → {account_name}"
    )

    return {
        'verified':       True,
        'account_name':   account_name,
        'account_number': account_data.get('account_number', account_number),
        'bank_code':      account_data.get('bank_code', bank_code),
    }


# ── Method to paste into your existing SquadService class ────────────────────
"""
Add this method to services/squad.py inside your SquadService class:

    def verify_bank_account(self, bank_code: str, account_number: str) -> dict:
        from services.squad_bank_verify import verify_bank_account
        return verify_bank_account(bank_code, account_number)
"""