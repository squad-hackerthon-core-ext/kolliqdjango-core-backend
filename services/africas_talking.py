"""
Africa's Talking SMS service.
Docs: https://developers.africastalking.com/docs/sms/sending
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class ATService:

    def __init__(self):
        self.username = settings.AT_USERNAME
        self.api_key = settings.AT_API_KEY
        self.sender_id = settings.AT_SENDER_ID
        self.base_url = 'https://api.africastalking.com/version1'

        if self.username == 'sandbox':
            self.base_url = 'https://api.sandbox.africastalking.com/version1'

    def send_sms(self, phone: str, message: str) -> dict:
        """
        Send SMS to a single number.
        phone: Nigerian number e.g. +2348012345678
        """
        url = f"{self.base_url}/messaging"
        headers = {
            'apiKey': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        data = {
            'username': self.username,
            'to': phone,
            'message': message,
            'from': self.sender_id,
        }
        try:
            response = requests.post(url, headers=headers, data=data, timeout=15)
            result = response.json()
            recipients = result.get('SMSMessageData', {}).get('Recipients', [])
            if recipients and recipients[0].get('status') == 'Success':
                logger.info(f"SMS sent to {phone}")
                return {'success': True, 'message_id': recipients[0].get('messageId')}
            else:
                logger.warning(f"SMS to {phone} may have failed: {result}")
                return {'success': False, 'result': result}
        except Exception as e:
            logger.error(f"SMS send failed to {phone}: {e}")
            return {'success': False, 'error': str(e)}

    def send_bulk_sms(self, phones: list, message: str) -> dict:
        """Send same message to multiple numbers."""
        return self.send_sms(','.join(phones), message)