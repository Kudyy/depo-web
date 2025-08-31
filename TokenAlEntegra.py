import requests

BASE_URL = "https://apiv2.entegrabilisim.com/"

def entegrabilisim_token_al():
    url = BASE_URL + "api/user/token/obtain/"
    data = {
        "email": "apionlinesatis@temel.com.tr",
        "password": "Temel124578."
    }
    try:
        r = requests.post(url, json=data)
        print("Status:", r.status_code)
        print("Response:", r.text)
        if r.status_code == 200 or r.status_code == 201:
            access = r.json().get("access")
            print("Access Token:", access)
            return access
        else:
            print("Token alınamadı, hata:", r.text)
            return None
    except Exception as e:
        print("HATA:", str(e))
        return None

# Kullanım:
entegrabilisim_token_al()
