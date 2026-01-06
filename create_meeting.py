import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcGlrZXkiOiIxNjFmY2NjNS1kMjQ3LTQ1MTctYTBhOC0zNDI0MDMxMWIzMDEiLCJwZXJtaXNzaW9ucyI6WyJhbGxvd19qb2luIl0sImlhdCI6MTc2Njk3NjcxNSwiZXhwIjoxODk2NTc2NzE1fQ.IF_R_-kfANNHE0-kGyXSW-0afRJWmWzz1mbvIztv7OQ"

url = "https://api.videosdk.live/v2/rooms"
headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

response = requests.post(url, headers=headers)
print(response.json())
