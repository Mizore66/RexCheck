# Test 5: Heuristic Accuracy (spec/services/risk_calculator_spec.rb equivalent)
# Run with: docker-compose run web bundle exec rails runner testcases/test_risk_calculator.rb

puts "=== Test 5: RiskCalculator Heuristic Accuracy ==="
puts ""

# Test case: $1M 24h volume and $500 liquidity reserve
# Expected: score < 50, status DANGER, flags include wash_trading_suspected AND critical_low_liquidity
result = RiskCalculator.new({
  volume_usd: 1_000_000,       # $1M volume
  reserve_in_usd: 500,         # $500 liquidity (very low)
  pool_created_at: 48.hours.ago # Not unseasoned
}).call

passed = true

# Check score is < 50
if result.health_score < 50
  puts "  PASS: health_score (#{result.health_score}) < 50"
else
  puts "  FAIL: health_score (#{result.health_score}) should be < 50"
  passed = false
end

# Check status is DANGER
if result.status == "DANGER"
  puts "  PASS: status is DANGER"
else
  puts "  FAIL: status is '#{result.status}', expected 'DANGER'"
  passed = false
end

# Check flags contain wash_trading_suspected
if result.flags.include?("wash_trading_suspected")
  puts "  PASS: flags include 'wash_trading_suspected'"
else
  puts "  FAIL: flags #{result.flags} should include 'wash_trading_suspected'"
  passed = false
end

# Check flags contain critical_low_liquidity
if result.flags.include?("critical_low_liquidity")
  puts "  PASS: flags include 'critical_low_liquidity'"
else
  puts "  FAIL: flags #{result.flags} should include 'critical_low_liquidity'"
  passed = false
end

# Check recommendation
if result.recommendation == "DO_NOT_TRADE"
  puts "  PASS: recommendation is 'DO_NOT_TRADE'"
else
  puts "  FAIL: recommendation is '#{result.recommendation}', expected 'DO_NOT_TRADE'"
  passed = false
end

puts ""
puts passed ? "ALL ASSERTIONS PASSED" : "SOME ASSERTIONS FAILED"
exit(passed ? 0 : 1)
