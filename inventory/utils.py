# inventory/utils.py
import random
import string


def generate_paystack_reference():
    """
    Generates a mock/test Paystack transaction reference.
    Used to simulate payment creation or verification.
    """
    prefix = "PSK"
    unique_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"{prefix}-{unique_id}"
