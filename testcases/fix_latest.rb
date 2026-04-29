# Fix latest 5 pools discrepancy
pools = Pool.order("created_at DESC").limit(5)

puts "Fixing latest 5 pools..."
pools.each do |pool|
  network = pool.network_id
  address = pool.pool_address

  url = URI("https://api.geckoterminal.com/api/v2/networks/#{network}/pools/#{address}")
  req = Net::HTTP::Get.new(url)
  req["Accept"] = "application/json;version=20230302"
  
  res = Net::HTTP.start(url.hostname, url.port, use_ssl: true) { |http|
    http.request(req)
  }
  
  if res.code == "200"
    data = JSON.parse(res.body)["data"]
    attrs = data["attributes"]
    
    volume_usd = attrs.dig("volume_usd", "h24").to_f
    reserve_in_usd = attrs["reserve_in_usd"].to_f
    
    result = RiskCalculator.new({
      volume_usd: volume_usd,
      reserve_in_usd: reserve_in_usd,
      pool_created_at: attrs["pool_created_at"]
    }).call
    
    pool.pool_scans.create!(
      volume_usd: volume_usd,
      reserve_in_usd: reserve_in_usd,
      health_score: result.health_score,
      flags: result.flags,
      scanned_at: Time.current
    )
    puts "✓ Updated #{pool.pool_name.strip} (#{network}/#{address})"
  else
    puts "✗ Failed #{pool.pool_name.strip}: #{res.code}"
  end
  sleep 1.5
end
