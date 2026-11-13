import hmac
import hashlib
import pickle
from django.core.exceptions import ImproperlyConfigured
from kombu.serialization import register

from maxkb.const import CONFIG

_local_secret_key = CONFIG.get('HMAC_SIGNED_SERIALIZER_SECRET_KEY') or CONFIG.get('SECRET_KEY')
try:
    from xpack import get_md5
    _local_secret_key = get_md5()
except ImportError:
    pass

def _sign(data):
    if not _local_secret_key:
        raise ImproperlyConfigured('Configure the same MAXKB_SECRET_KEY for the API and worker.')
    return hmac.digest(_local_secret_key.encode(), data, hashlib.sha256)


def secure_dumps(obj):
    data = pickle.dumps(obj)
    return _sign(data) + data

def secure_loads(signed_data):
    if len(signed_data) < 32:
        raise ValueError("Invalid signed data packet")
    signature = signed_data[:32]
    payload = signed_data[32:]
    expected_signature = _sign(payload)
    if hmac.compare_digest(signature, expected_signature):
        return pickle.loads(payload)
    else:
        raise ValueError("Security Alert: Task signature mismatch! Potential tampering detected.")

def register_hmac_signed_serializer():
    register(
        'hmac_signed_serializer',
        secure_dumps,
        secure_loads,
        content_type='application/x-python-hmac-signed-serialize',
        content_encoding='binary'
    )
