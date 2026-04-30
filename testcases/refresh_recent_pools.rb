require "net/http"
require "uri"
require "json"

# This script refreshes the data for the 20 most recently added pools
pools = Pool.order("created_at DESC").limit(20)

puts "Refreshing data for the latest 20 pools from GeckoTerminal..."
puts "=" * 80

pools.each do |pool|
  network = pool.network_id
  address = pool.pool_address

  url = "https://api.geckoterminal.com/api/v2/networks/#{network}/pools/#{address}"
  uri = URI(url)
  req = Net::HTTP::Get.new(uri)
  req["Accept"] = "application/json;version=20230302"
  
  res = Net::HTTP.start(uri.hostname, uri.port, use_ssl: true) {|http|
    http.request(req)
  }
  
  if res.code != "200"
    puts "Failed to fetch #{network}/#{address}: HTTP #{res.code}"
    next
  end

  data = JSON.parse(res.body)["data"]
  attrs = data["attributes"]
  attrs_deep = attrs.deep_symbolize_keys

  volume_usd = attrs_deep.dig(:volume_usd, :h24).to_f
  reserve_in_usd = attrs_deep[:reserve_in_usd].to_f

  result = RiskCalculator.new(attributes: attrs_deep).call

  # Create a new scan
  pool.pool_scans.create!(
    volume_usd: volume_usd,
    reserve_in_usd: reserve_in_usd,
    health_score: result.health_score,
    flags: result.flags,
    scanned_at: Time.current
  )

  puts "Updated #{pool.pool_name.strip} (#{network}/#{address})"
  puts "  Volume: $#{volume_usd.round(2)} | Reserve: $#{reserve_in_usd.round(2)}"
  
  sleep 1.5 # respect rate limits
end

puts "=" * 80
puts "Refresh complete."
