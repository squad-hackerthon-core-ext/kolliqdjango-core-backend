"""
Squad Co-operative MFB — Complete API Integration
==================================================
Built directly from: https://docs.squadco.com/

Key facts from the docs:
- Auth: Bearer {SECRET_KEY} in every request header
- All amounts Squad sends/receives are in KOBO (multiply naira × 100)
- Virtual account webhook fires to your URL on every incoming payment
- Webhook signature (v3): HMAC-SHA512 of 6 pipe-joined fields
- Transfer references MUST include your Merchant ID as prefix
- Settlement account must be a GTBank account
- BVN validation is strict in production, lenient in sandbox
"""

import requests
import hmac
import hashlib
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class SquadAPIError(Exception):
    """Raised when Squad returns an error or the network fails."""
    def __init__(self, message: str, status_code: int = None, raw: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw or {}


def naira_to_kobo(amount: Decimal) -> int:
    """Squad expects amounts in kobo. Convert naira Decimal → kobo int."""
    return int(amount * 100)


def kobo_to_naira(kobo: int) -> Decimal:
    """Convert kobo int → naira Decimal."""
    return Decimal(str(kobo)) / 100


class SquadService:
    """
    One class, one session, every Squad endpoint we use.
    Instantiate per-request — don't share across threads.
    """

    def __init__(self):
        self.secret_key = settings.SQUAD_SECRET_KEY
        self.base_url = settings.SQUAD_BASE_URL.rstrip('/')
        self.merchant_id = settings.SQUAD_MERCHANT_ID
        self.beneficiary_account = getattr(settings, 'SQUAD_BENEFICIARY_ACCOUNT', '')

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        })

    # ── Internal request helpers ──────────────────────────────────

    def _post(self, endpoint: str, data: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.post(url, json=data, timeout=30)
            return self._handle_response(resp, endpoint)
        except requests.exceptions.Timeout:
            raise SquadAPIError(f"Squad timeout on POST {endpoint}", status_code=408)
        except requests.exceptions.RequestException as e:
            raise SquadAPIError(f"Squad network error on POST {endpoint}: {e}")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=30)
            return self._handle_response(resp, endpoint)
        except requests.exceptions.Timeout:
            raise SquadAPIError(f"Squad timeout on GET {endpoint}", status_code=408)
        except requests.exceptions.RequestException as e:
            raise SquadAPIError(f"Squad network error on GET {endpoint}: {e}")

    def _delete(self, endpoint: str) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.delete(url, timeout=30)
            return self._handle_response(resp, endpoint)
        except requests.exceptions.RequestException as e:
            raise SquadAPIError(f"Squad network error on DELETE {endpoint}: {e}")

    def _handle_response(self, resp: requests.Response, endpoint: str) -> dict:
        """Parse Squad response — raise SquadAPIError on any failure."""
        try:
            body = resp.json()
        except Exception:
            raise SquadAPIError(
                f"Squad returned non-JSON response on {endpoint}",
                status_code=resp.status_code
            )

        success = body.get('success', False)
        status = body.get('status', resp.status_code)

        if not success or resp.status_code not in (200, 201):
            message = body.get('message', 'Unknown Squad error')
            logger.error(
                f"Squad error [{endpoint}] status={status}: {message} | raw={body}"
            )
            raise SquadAPIError(message, status_code=resp.status_code, raw=body)

        return body.get('data', body)

    # ── VIRTUAL ACCOUNTS ─────────────────────────────────────────

    def create_virtual_account(
        self,
        customer_identifier: str,
        first_name: str,
        last_name: str,
        middle_name: str,
        phone: str,
        email: str,
        dob: str = '',
        bvn: str = '',
        gender: str = '1',
        address: str = '',
        beneficiary_account: str = '',
    ) -> dict:
        """
        POST /virtual-account
        Creates a dedicated virtual account for a customer.

        Docs: customer_identifier must be unique per user.
        BVN is required in production but optional in sandbox.
        Settlement goes to SQUAD_BENEFICIARY_ACCOUNT (your GTBank account).

        Returns:
            {
                'virtual_account_number': '7834927713',
                'bank_code': '058',
                'customer_identifier': '...',
                'first_name': '...',
                'last_name': '...',
            }
        """
        # Squad phone format: 11 digits, no +234 prefix
        phone_clean = phone.replace('+234', '0').replace('+', '').replace(' ', '')
        if phone_clean.startswith('234'):
            phone_clean = '0' + phone_clean[3:]

        payload = {
            'customer_identifier': customer_identifier,
            'first_name': first_name,
            'last_name': last_name,
            'middle_name': middle_name,
            'mobile_num': phone_clean[:11],
            'email': email,
            'dob': dob,                    # format: mm/dd/yyyy
            'gender': gender,               # '1' = Male, '2' = Female
            'address': address,
            'bvn': bvn,
            'beneficiary_account': beneficiary_account or self.beneficiary_account,
        }

        result = self._post('/virtual-account', payload)

        logger.info(
            f"Squad VA created: identifier={customer_identifier} "
            f"account={result.get('virtual_account_number')}"
        )
        return {
            'virtual_account_number': result.get('virtual_account_number', ''),
            'bank_code': result.get('bank_code', '058'),
            'bank_name': 'GTBank',            # Squad VAs are always GTBank
            'customer_identifier': result.get('customer_identifier', customer_identifier),
            'first_name': result.get('first_name', first_name),
            'last_name': result.get('last_name', last_name),
        }

    def get_customer_by_identifier(self, customer_identifier: str) -> dict:
        """
        GET /virtual-account/{customer_identifier}
        Fetch a customer's virtual account details using their identifier.
        Use this to confirm VA was created or get the account number.
        """
        return self._get(f'/virtual-account/{customer_identifier}')

    def get_customer_by_va_number(self, virtual_account_number: str) -> dict:
        """
        GET /virtual-account/customer/{virtual_account_number}
        Lookup who owns a virtual account number.
        Useful when a payment arrives and you need to identify the recipient.
        """
        return self._get(f'/virtual-account/customer/{virtual_account_number}')

    def list_merchant_virtual_accounts(
        self, page: int = 1, per_page: int = 100,
        start_date: str = '', end_date: str = ''
    ) -> dict:
        """
        GET /virtual-account/merchant/accounts
        List all virtual accounts you've created.
        Useful for admin reconciliation.
        Dates format: YY-MM-DD
        """
        params = {'page': page, 'perPage': per_page}
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['EndDate'] = end_date
        return self._get('/virtual-account/merchant/accounts', params=params)

    def simulate_payment(
        self, virtual_account_number: str, amount_naira: Decimal
    ) -> dict:
        """
        POST /virtual-account/simulate/payment
        SANDBOX ONLY — triggers a fake payment to a virtual account.
        This fires your webhook exactly as a real payment would.
        Use this to test the full Tunde/Amina payment flow locally.

        amount_naira: Decimal naira amount (e.g. Decimal('3500'))
        """
        payload = {
            'virtual_account_number': virtual_account_number,
            'amount': str(naira_to_kobo(amount_naira)),
        }
        result = self._post('/virtual-account/simulate/payment', payload)
        logger.info(
            f"Squad payment simulated: VA={virtual_account_number} "
            f"amount=₦{amount_naira}"
        )
        return result

    # ── TRANSACTIONS ─────────────────────────────────────────────

    def get_customer_transactions(self, customer_identifier: str) -> list:
        """
        GET /virtual-account/customer/transactions/{customer_identifier}
        All transactions for a specific customer.
        Use this for reconciliation or building transaction history.
        """
        result = self._get(
            f'/virtual-account/customer/transactions/{customer_identifier}'
        )
        return result if isinstance(result, list) else result.get('rows', [])

    def get_all_merchant_transactions(
        self,
        page: int = 1,
        per_page: int = 50,
        virtual_account: str = '',
        customer_identifier: str = '',
        start_date: str = '',
        end_date: str = '',
        transaction_reference: str = '',
        direction: str = 'DESC',
    ) -> dict:
        """
        GET /virtual-account/merchant/transactions/all
        Query all your transactions with filters.
        Dates format: MM-DD-YYYY (e.g. '09-19-2022')
        direction: 'DESC' or 'ASC'
        """
        params = {
            'page': page,
            'perPage': per_page,
            'dir': direction,
        }
        if virtual_account:
            params['virtualAccount'] = virtual_account
        if customer_identifier:
            params['customerIdentifier'] = customer_identifier
        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date
        if transaction_reference:
            params['transactionReference'] = transaction_reference

        return self._get('/virtual-account/merchant/transactions/all', params=params)

    # ── WEBHOOK ERROR LOG ─────────────────────────────────────────

    def get_webhook_error_log(self, page: int = 1, per_page: int = 100) -> dict:
        """
        GET /virtual-account/webhook/logs
        Retrieve missed webhook notifications.
        Squad keeps these so you don't lose payments if your server was down.

        IMPORTANT: after processing each one, call delete_webhook_log()
        or it will keep appearing in the top 100.
        """
        params = {'page': page, 'perPage': per_page}
        return self._get('/virtual-account/webhook/logs', params=params)

    def delete_webhook_log(self, transaction_ref: str) -> dict:
        """
        DELETE /virtual-account/webhook/logs/{transaction_ref}
        Mark a missed webhook as processed so it stops appearing.
        Call this AFTER you've successfully processed the transaction.
        """
        result = self._delete(f'/virtual-account/webhook/logs/{transaction_ref}')
        logger.info(f"Squad webhook log deleted: {transaction_ref}")
        return result

    # ── TRANSFERS (PAYOUT / ESCROW RELEASE) ──────────────────────

    def account_lookup(self, bank_code: str, account_number: str) -> dict:
        """
        POST /payout/account/lookup
        Verify an account name before transferring to it.
        Squad docs say: always look up before transferring —
        they won't be liable for transfers to wrong accounts.

        Returns: { 'account_name': 'JENNY SQUAD', 'account_number': '...' }
        """
        payload = {
            'bank_code': bank_code,
            'account_number': account_number,
        }
        return self._post('/payout/account/lookup', payload)

    def initiate_transfer(
        self,
        amount_naira: Decimal,
        bank_code: str,
        account_number: str,
        account_name: str,
        reference_suffix: str,
        narration: str = '',
    ) -> dict:
        """
        POST /payout/transfer
        Transfer from your Squad Wallet to any Nigerian bank account.

        CRITICAL from docs:
        - Reference MUST be prefixed with your Merchant ID
          e.g. '{MERCHANT_ID}_{your_unique_ref}'
        - Amount is in KOBO
        - Always requery on 424 (timeout) — do NOT retry with new reference

        Returns: {
            'transaction_reference': '...',
            'response_description': 'Approved or completed successfully',
            'nip_transaction_reference': '...',  ← confirms NIP routing
            'account_number': '...',
            'account_name': '...',
            'destination_institution_name': '...',
        }
        """
        # Merchant ID prefix is REQUIRED by Squad
        transaction_reference = f"{self.merchant_id}_{reference_suffix}"

        payload = {
            'transaction_reference': transaction_reference,
            'amount': str(naira_to_kobo(amount_naira)),
            'bank_code': bank_code,
            'account_number': account_number,
            'account_name': account_name,
            'currency_id': 'NGN',
            'remark': narration or f'Kolliq payment {reference_suffix}',
        }

        result = self._post('/payout/transfer', payload)

        # Docs best practice: check nip_transaction_reference was returned
        # If missing, requery before assuming success
        if not result.get('nip_transaction_reference'):
            logger.warning(
                f"Squad transfer missing nip_transaction_reference: "
                f"ref={transaction_reference} — requery recommended"
            )

        logger.info(
            f"Squad transfer initiated: ref={transaction_reference} "
            f"amount=₦{amount_naira} to={account_number} bank={bank_code}"
        )
        return {**result, 'full_reference': transaction_reference}

    def requery_transfer(self, reference_suffix: str) -> dict:
        """
        POST /payout/requery
        Check status of a transfer — use when you get a 424 (timeout/failed)
        or when nip_transaction_reference was missing from the original response.

        Docs say: on 424, ALWAYS requery before creating a new transfer.
        Error codes: 200=success, 400=bad req, 422=unprocessed,
                     424=timeout/re-query, 404=not found, 412=reversed
        """
        full_reference = f"{self.merchant_id}_{reference_suffix}"
        payload = {'transaction_reference': full_reference}
        result = self._post('/payout/requery', payload)
        logger.info(f"Squad transfer requeried: ref={full_reference}")
        return result

    def list_transfers(
        self, page: int = 1, per_page: int = 50, direction: str = 'DESC'
    ) -> list:
        """
        GET /payout/list
        All transfers made from your Squad wallet.
        """
        params = {'page': page, 'perPage': per_page, 'dir': direction}
        result = self._get('/payout/list', params=params)
        return result if isinstance(result, list) else []

    # ── MERCHANT ──────────────────────────────────────────────────

    def get_ledger_balance(self) -> dict:
        """
        GET /merchant/balance?currency_id=NGN
        Your Squad merchant wallet balance.
        NOTE: returned in KOBO — we convert to naira before returning.

        Returns: { 'balance_naira': Decimal('23670.13'), 'merchant_id': '...' }
        """
        result = self._get('/merchant/balance', params={'currency_id': 'NGN'})
        balance_kobo = int(result.get('balance', 0))
        return {
            'balance_naira': kobo_to_naira(balance_kobo),
            'balance_kobo': balance_kobo,
            'currency': 'NGN',
            'merchant_id': result.get('merchant_id', ''),
        }

    # ── WEBHOOK VERIFICATION ──────────────────────────────────────

    def verify_webhook_signature(
        self, payload: dict, signature_header: str
    ) -> bool:
        """
        Verify Squad webhook using v3 method (current as of docs).

        v3 hashes exactly 6 fields joined by pipes:
          transaction_reference|virtual_account_number|currency|
          principal_amount|settled_amount|customer_identifier

        Uses HMAC-SHA512 with your SECRET KEY.
        Compare against x-squad-signature header.

        IMPORTANT: the docs also show v1 (hash whole body) and v2.
        Use v3 — it's what Squad sends now. If signature fails,
        also try v1 as fallback (Squad may send either during transition).
        """
        try:
            signature_string = '|'.join([
                str(payload.get('transaction_reference', '')),
                str(payload.get('virtual_account_number', '')),
                str(payload.get('currency', '')),
                str(payload.get('principal_amount', '')),
                str(payload.get('settled_amount', '')),
                str(payload.get('customer_identifier', '')),
            ])

            expected = hmac.new(
                self.secret_key.encode('utf-8'),
                signature_string.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            v3_valid = hmac.compare_digest(
                expected.lower(),
                signature_header.lower()
            )
            if v3_valid:
                return True

            # Fallback: v1 hashes the entire JSON body string
            # (older Squad webhook versions)
            import json
            body_string = json.dumps(payload, separators=(',', ':'))
            expected_v1 = hmac.new(
                self.secret_key.encode('utf-8'),
                body_string.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            v1_valid = hmac.compare_digest(
                expected_v1.lower(),
                signature_header.lower()
            )
            if v1_valid:
                logger.info("Webhook validated via v1 fallback")
            return v1_valid

        except Exception as e:
            logger.error(f"Webhook signature verification error: {e}")
            return False

    def parse_webhook_payload(self, payload: dict) -> dict:
        """
        Normalise a Squad webhook payload into a consistent internal format.
        Handles v1, v2, and v3 webhook shapes.

        Returns a clean dict our tasks can work with without caring about version.
        """
        return {
            'transaction_reference': payload.get('transaction_reference', ''),
            'virtual_account_number': payload.get('virtual_account_number', ''),
            'principal_amount': Decimal(str(payload.get('principal_amount', '0'))),
            'settled_amount': Decimal(str(payload.get('settled_amount', '0'))),
            'fee_charged': Decimal(str(payload.get('fee_charged', '0'))),
            'customer_identifier': payload.get('customer_identifier', ''),
            'sender_name': payload.get('sender_name', ''),
            'remarks': payload.get('remarks', ''),
            'currency': payload.get('currency', 'NGN'),
            'channel': payload.get('channel', 'virtual-account'),
            'transaction_date': payload.get('transaction_date', ''),
            'transaction_indicator': payload.get('transaction_indicator', 'C'),
            'session_id': payload.get('session_id', ''),
            'version': payload.get('version', 'v1'),
            'is_frozen': bool(
                payload.get('meta', {}) and
                payload.get('meta', {}).get('freeze_transaction_ref')
            ),
        }

    # ── NIGERIAN BANKS LIST ───────────────────────────────────────────

NIGERIAN_BANKS = [
    {"name": "Access Bank", "code": "044"},
    {"name": "Citibank Nigeria", "code": "023"},
    {"name": "Ecobank Nigeria", "code": "050"},
    {"name": "Fidelity Bank", "code": "070"},
    {"name": "First Bank of Nigeria", "code": "011"},
    {"name": "First City Monument Bank", "code": "214"},
    {"name": "Globus Bank", "code": "00103"},
    {"name": "Guaranty Trust Bank", "code": "058"},
    {"name": "Heritage Bank", "code": "030"},
    {"name": "Keystone Bank", "code": "082"},
    {"name": "Kuda Bank", "code": "50211"},
    {"name": "Moniepoint MFB", "code": "50515"},
    {"name": "OPay", "code": "100004"},
    {"name": "Palmpay", "code": "100033"},
    {"name": "Polaris Bank", "code": "076"},
    {"name": "Providus Bank", "code": "101"},
    {"name": "Stanbic IBTC Bank", "code": "221"},
    {"name": "Standard Chartered Bank", "code": "068"},
    {"name": "Sterling Bank", "code": "232"},
    {"name": "Titan Trust Bank", "code": "102"},
    {"name": "Union Bank of Nigeria", "code": "032"},
    {"name": "United Bank for Africa", "code": "033"},
    {"name": "Unity Bank", "code": "215"},
    {"name": "VFD Microfinance Bank", "code": "566"},
    {"name": "Wema Bank", "code": "035"},
    {"name": "Zenith Bank", "code": "057"},
]

_BANK_CODE_MAP = {b["code"]: b["name"] for b in NIGERIAN_BANKS}


def get_bank_name(bank_code: str) -> str:
    """Return a bank's display name given its code, or the code itself as fallback."""
    return _BANK_CODE_MAP.get(bank_code, bank_code)


def verify_bank_account(bank_code: str, account_number: str) -> dict:
    """
    Verify a bank account via Squad's account lookup API.
    Returns: { 'account_name': str, 'account_number': str }
    Raises ValueError on Squad error, Exception on network failure.
    """
    squad = SquadService()
    try:
        result = squad.account_lookup(bank_code, account_number)
        account_name = result.get('account_name', '')
        if not account_name:
            raise ValueError("Could not retrieve account name. Check account details.")
        return {
            'account_name': account_name,
            'account_number': account_number,
        }
    except SquadAPIError as e:
        raise ValueError(str(e))