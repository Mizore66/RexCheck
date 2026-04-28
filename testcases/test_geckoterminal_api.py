import urllib.request
import urllib.error
import json
import sys

def test_geckoterminal_health():
    url = "https://api.geckoterminal.com/api/v2/networks"
    print(f"Testing GeckoTerminal API Health at: {url}")
    print("-" * 50)
    
    # We add a user agent because some public APIs block default urllib/python agents
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            print(f"✅ Connection Successful! Status Code: {status_code}")
            
            data = json.loads(response.read().decode('utf-8'))
            networks = data.get("data", [])
            print(f"✅ Successfully retrieved {len(networks)} networks from the API.")
            
            if len(networks) > 0:
                print("\nSample Networks returned:")
                for net in networks[:5]:  # Just show the first 5
                    print(f" - {net['attributes']['name']} (ID: {net['id']})")
                    
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        print("Response body:", e.read().decode('utf-8'))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ URL Error: Failed to reach the server. Reason: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_geckoterminal_health()
