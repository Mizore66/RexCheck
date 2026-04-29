require "net/http"
require "uri"
require "json"

pools = Pool.joins(:pool_scans).distinct.order("created_at DESC").limit(5)
if pools.empty?
  puts "No pools in database."
  exit(0)
end

puts "Comparing local DB pool stats with live GeckoTerminal API stats..."
puts "=" * 80

total_diff_volume = 0
total_diff_reserve = 0

count = 0
pools.each do |pool|
  db_scan = pool.latest_scan
  next unless db_scan

  network = pool.network_id
  address = pool.pool_address

  # Fetch from GeckoTerminal
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
  live_volume = data["attributes"]["volume_usd"]["h24"].to_f
  live_reserve = data["attributes"]["reserve_in_usd"].to_f

  db_volume = db_scan.volume_usd.to_f
  db_reserve = db_scan.reserve_in_usd.to_f

  diff_vol = (live_volume - db_volume).abs
  diff_res = (live_reserve - db_reserve).abs

  puts "Pool: #{pool.pool_name.strip} (#{network}/#{address})"
  puts "  Live Volume:  $#{live_volume.round(2)}"
  puts "  DB Volume:    $#{db_volume.round(2)}"
  puts "  Difference:   $#{diff_vol.round(2)}"
  puts "  ---"
  puts "  Live Reserve: $#{live_reserve.round(2)}"
  puts "  DB Reserve:   $#{db_reserve.round(2)}"
  puts "  Difference:   $#{diff_res.round(2)}"
  puts "-" * 40
  
  total_diff_volume += diff_vol
  total_diff_reserve += diff_res
  count += 1
  
  sleep 1.2 # respect rate limits
end

if count > 0
  puts "=" * 80
  puts "Average Volume Discrepancy per pool: $#{(total_diff_volume / count).round(2)}"
  puts "Average Reserve Discrepancy per pool: $#{(total_diff_reserve / count).round(2)}"
end