import jwt
import time

API_KEY = "161fccc5-d247-4517-a0a8-34240311b301"
SECRET_KEY = "e02ba5431eec39f8af8be829c9ada500b380edfed30c8546f8f2a2e4934282d0"

payload = {
    "apikey": API_KEY,
    "permissions": ["allow_join"],
    "iat": int(time.time()),
    "exp": int(time.time()) + 36000 * 3600  # valid for 24 hours
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
print(token)
