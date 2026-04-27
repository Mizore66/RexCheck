puts "POOLS: #{Pool.count}"
puts "SCANS: #{PoolScan.count}"
puts "REDIS: #{REDIS_POOL.with { |r| r.llen('rexcheck:raw_pools') }}"
Pool.last(3).each do |p|
  s = p.pool_scans.last
  puts "#{p.network_id} #{p.pool_address[0..15]}.. Score:#{s&.health_score} Flags:#{s&.flags}"
end
