# apps/users/utils.py (create this new file)
import re

def normalize_phone_number(phone: str) -> str:
    """
    Convert any Nigerian phone number to +234XXXXXXXXXX format.
    
    Examples:
        '08012345678' → '+2348012345678'
        '2348012345678' → '+2348012345678'
        '+2348012345678' → '+2348012345678'
        '080 123 45678' → '+2348012345678'
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # Check if it's a valid Nigerian number
    if len(digits) == 10 and digits.startswith('0'):
        # Local format: 08012345678
        return '+234' + digits[1:]
    elif len(digits) == 12 and digits.startswith('234'):
        # International without +: 2348012345678
        return '+' + digits
    elif len(digits) == 13 and digits.startswith('234'):
        # Already has + (13 digits after removing +)
        return '+' + digits
    else:
        raise ValueError(f"Invalid Nigerian phone number: {phone}")

def format_phone_for_sms(phone: str) -> str:
    """Format phone number for Africa's Talking API."""
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) == 10 and digits.startswith('0'):
        return '+234' + digits[1:]
    elif len(digits) == 12 and digits.startswith('234'):
        return '+' + digits
    elif len(digits) == 13 and digits.startswith('234'):
        return '+' + digits
    else:
        raise ValueError(f"Invalid phone number for SMS: {phone}")