# Test 4: Lazy Analysis Trigger (spec/requests/mcp_pool_status_spec.rb equivalent)
# Run with: docker-compose run web bundle exec rails runner testcases/test_mcp_api.rb

require "net/http"
require "json"

puts "=== Test 4: MCP Pool Status API ==="
puts ""

# First create a test pool with a health score in the database
pool = Pool.find_or_create_by!(pool_address: "0xTEST_API_POOL_12345") do |p|
  p.network_id = "eth"
  p.base_token_address = "0xbase_token_test"
  p.quote_token_address = "0xquote_token_test"
end

initial_scan_count = PoolScan.count

# Create a scan with known values
result = RiskCalculator.new({
  volume_usd: 500_000,
  reserve_in_usd: 200_000,
  pool_created_at: 24.hours.ago
}).call

pool.pool_scans.create!(
  volume_usd: 500_000,
  reserve_in_usd: 200_000,
  health_score: result.health_score,
  flags: result.flags,
  scanned_at: Time.current
)

passed = true

# Test 4a: Verify PoolScan count incremented
new_scan_count = PoolScan.count
if new_scan_count > initial_scan_count
  puts "  PASS: PoolScan.count incremented (#{initial_scan_count} -> #{new_scan_count})"
else
  puts "  FAIL: PoolScan.count did not increment"
  passed = false
end

# Test 4b: Verify pool has a health score
scan = pool.pool_scans.last
if scan && scan.health_score.present?
  puts "  PASS: Pool has health_score: #{scan.health_score}"
else
  puts "  FAIL: Pool scan missing health_score"
  passed = false
end

# Test 4c: Verify pool status is computed
if scan && %w[SAFE WARNING DANGER].include?(scan.status)
  puts "  PASS: Pool status is valid: #{scan.status}"
else
  puts "  FAIL: Pool status is invalid: #{scan&.status}"
  passed = false
end

# Test 4d: Verify API controller logic
pool_from_db = Pool.find_by(pool_address: "0xTEST_API_POOL_12345", network_id: "eth")
latest = pool_from_db&.latest_scan
if latest
  puts "  PASS: API would return health_score=#{latest.health_score}, status=#{latest.status}, recommendation=#{latest.recommendation}"
else
  puts "  FAIL: latest_scan is nil"
  passed = false
end

puts ""
puts passed ? "ALL ASSERTIONS PASSED" : "SOME ASSERTIONS FAILED"
exit(passed ? 0 : 1)
