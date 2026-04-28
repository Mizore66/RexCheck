import urllib.request
import urllib.error
import json
import sys
import time

def fetch_recent_tokens(networks):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json'
    }
    
    results = {}

    for network in networks:
        print(f"\nFetching recent pools for network: {network.upper()}...")
        # GeckoTerminal endpoint for new pools by network
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/new_pools"
        
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                status_code = response.getcode()
                if status_code == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    pools = data.get("data", [])
                    
                    results[network] = pools
                    print(f"✅ Found {len(pools)} recent pools for {network}")
                    
                    # Print the top 3 pools as an example
                    for pool in pools[:3]:
                        name = pool['attributes']['name']
                        address = pool['attributes']['address']
                        price = pool['attributes'].get('base_token_price_usd', 'N/A')
                        print(f"   -> {name}")
                        print(f"      Address: {address} | Price (USD): ${price}")
                else:
                    print(f"⚠️ Warning: Non-200 status code {status_code} for {network}")
                    
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP Error for {network}: {e.code} - {e.reason}")
        except Exception as e:
            print(f"❌ Unexpected Error for {network}: {e}")
            
        # Sleep slightly to avoid hitting strict rate limits
        time.sleep(1)

    # Save all output to a json file in testcases
    output_file = "testcases/recent_tokens_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Full data saved locally to {output_file}")


if __name__ == "__main__":
    # GeckoTerminal network identifiers
    target_networks = ['solana', 'eth', 'bsc', 'near', 'polygon_pos']
    fetch_recent_tokens(target_networks)
