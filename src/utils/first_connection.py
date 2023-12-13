import requests

AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"


def get_first_connexion_credentials(client_id, consumer_secret, callback_url):
    params_url = {
        "response_type": "code",
        "client_id": client_id,
        "state": "OK",
        "scope": "user.metrics",
        "redirect_uri": callback_url,
    }

    url = AUTHORIZE_URL + "?"
    for key, value in params_url.items():
        url = url + key + "=" + value + "&"

    print(f"Go to {url} and get authentification code.")
    authentification_code = input("Token : ")

    params = {
        "action": "requesttoken",
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": consumer_secret,
        "code": authentification_code,
        "redirect_uri": callback_url,
    }

    req = requests.post(TOKEN_URL, params)
    resp = req.json()
    body = resp.get("body")

    print("Access token: ", body.get("access_token"))
    print("Refresh token: ", body.get("refresh_token"))
    print("Authentification code: ", authentification_code)
