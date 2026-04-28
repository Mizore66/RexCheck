puts "=== PIPELINE TEST ==="
puts "Redis queue length BEFORE: #{REDIS_POOL.with { |r| r.llen('rexcheck:raw_pools') }}"
puts "Pool count BEFORE: #{Pool.count}"
puts "PoolScan count BEFORE: #{PoolScan.count}"
puts ""

errors = []
25.times do |i|
  begin
    PoolIngestionJob.perform_now
  rescue => e
    errors << "Run #{i}: #{e.class} - #{e.message}"
  end
end

puts "=== RESULTS ==="
puts "Redis queue length AFTER: #{REDIS_POOL.with { |r| r.llen('rexcheck:raw_pools') }}"
puts "Pool count AFTER: #{Pool.count}"
puts "PoolScan count AFTER: #{PoolScan.count}"

if errors.any?
  puts "\n=== ERRORS (#{errors.size}) ==="
  errors.first(5).each { |e| puts "  #{e}" }
end

puts "\n=== SAMPLE POOLS ==="
Pool.last(3).each do |p|
  scan = p.pool_scans.last
  puts "  #{p.network_id} | #{p.pool_address[0..20]}... | Score: #{scan&.health_score} | Flags: #{scan&.flags}"
end
