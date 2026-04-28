# db/seeds.rb
# Seed data for local development/demo purposes
# Run with: rails db:seed

puts "Seeding rexcheck development data..."

demo_pools = [
  # ETH/USDC — Uniswap v3 mainnet, healthy, high liquidity
  {
    network_id: "eth",
    pool_address: "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    base_token_address: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    base_token_symbol: "USDC",
    quote_token_symbol: "WETH",
    volume: 2_500_000,
    reserve: 150_000_000,
    age_hours: 720,
  },
  # UNI/ETH — Uniswap governance token, moderate volume
  {
    network_id: "eth",
    pool_address: "0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801",
    base_token_address: "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    base_token_symbol: "UNI",
    quote_token_symbol: "WETH",
    volume: 850_000,
    reserve: 45_000_000,
    age_hours: 2160,
  },
  # SOL/USDC — Solana mainnet, high volume healthy pool
  {
    network_id: "solana",
    pool_address: "7qbRF6YsyGuLUVs6Y1q64bdVrfe4ZcUUz1JRdoVNUJnm",
    base_token_address: "So11111111111111111111111111111111111111112",
    quote_token_address: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    base_token_symbol: "SOL",
    quote_token_symbol: "USDC",
    volume: 12_000_000,
    reserve: 80_000_000,
    age_hours: 48,
  },
  # WETH/USDC — Base network, danger: critically low liquidity + new pool
  {
    network_id: "base",
    pool_address: "0xcDAC0d6c6C59727a65F871236188350531885C43",
    base_token_address: "0x4200000000000000000000000000000000000006",
    quote_token_address: "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    base_token_symbol: "WETH",
    quote_token_symbol: "USDC",
    volume: 3_200,
    reserve: 5_000,
    age_hours: 0.5,
  },
  # WBTC/USDC — Arbitrum, wash trading suspected (volume >> reserve)
  {
    network_id: "arbitrum",
    pool_address: "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
    base_token_address: "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
    quote_token_address: "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
    base_token_symbol: "WBTC",
    quote_token_symbol: "USDC",
    volume: 15_000_000,
    reserve: 200_000,
    age_hours: 168,
  },
  # MATIC/USDC — Polygon PoS, healthy large pool
  {
    network_id: "polygon_pos",
    pool_address: "0x45dDa9cb7c25131DF268515131f647d726f50608",
    base_token_address: "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270",
    quote_token_address: "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
    base_token_symbol: "MATIC",
    quote_token_symbol: "USDC",
    volume: 500_000,
    reserve: 12_000_000,
    age_hours: 4320,
  },
  # BNB/BUSD — BSC, danger: low liquidity + brand new + wash trading
  {
    network_id: "bsc",
    pool_address: "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    base_token_address: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    quote_token_address: "0xe9e7cea3dedca5984780bafc599bd69add087d56",
    base_token_symbol: "BNB",
    quote_token_symbol: "BUSD",
    volume: 95_000,
    reserve: 3_500,
    age_hours: 0.25,
  },
  # AVAX/USDC — Avalanche, healthy established pool
  {
    network_id: "avalanche",
    pool_address: "0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE",
    base_token_address: "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7",
    quote_token_address: "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
    base_token_symbol: "AVAX",
    quote_token_symbol: "USDC",
    volume: 1_200_000,
    reserve: 25_000_000,
    age_hours: 2880,
  },
  # WETH/USDC — Optimism, healthy
  {
    network_id: "optimism",
    pool_address: "0x68F5C0A2DE713a54991E01858Fd27a3832401849",
    base_token_address: "0x4200000000000000000000000000000000000006",
    quote_token_address: "0x7f5c764cbc14f9669b88837ca1490cca17c31607",
    base_token_symbol: "WETH",
    quote_token_symbol: "USDC",
    volume: 750_000,
    reserve: 18_000_000,
    age_hours: 720,
  },
  # ETH/WBTC — Ethereum mainnet, Bitcoin-Ether pair
  {
    network_id: "eth",
    pool_address: "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed",
    base_token_address: "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    base_token_symbol: "WBTC",
    quote_token_symbol: "WETH",
    volume: 8_000_000,
    reserve: 320_000_000,
    age_hours: 8760,
  },
  # LINK/ETH — Chainlink on Ethereum
  {
    network_id: "eth",
    pool_address: "0xa6cc3c2531fdaa6ae1a3ca84c2855806728693e8",
    base_token_address: "0x514910771af9ca656af840dff83e8264ecf986ca",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    base_token_symbol: "LINK",
    quote_token_symbol: "WETH",
    volume: 420_000,
    reserve: 8_500_000,
    age_hours: 3600,
  },
  # SOL/WBTC — Solana cross-asset, warning zone
  {
    network_id: "solana",
    pool_address: "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",
    base_token_address: "So11111111111111111111111111111111111111112",
    quote_token_address: "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",
    base_token_symbol: "SOL",
    quote_token_symbol: "WBTC",
    volume: 980_000,
    reserve: 6_200_000,
    age_hours: 240,
  },
]

demo_pools.each do |data|
  pool = Pool.find_or_create_by!(pool_address: data[:pool_address]) do |p|
    p.network_id = data[:network_id]
    p.base_token_address = data[:base_token_address]
    p.quote_token_address = data[:quote_token_address]
    p.base_token_symbol = data[:base_token_symbol]
    p.quote_token_symbol = data[:quote_token_symbol]
  end

  # Also update symbols if pool already existed without them
  pool.update!(
    base_token_symbol: data[:base_token_symbol],
    quote_token_symbol: data[:quote_token_symbol]
  )

  pool_created_at = data[:age_hours].hours.ago

  result = RiskCalculator.new(
    volume_usd: data[:volume],
    reserve_in_usd: data[:reserve],
    pool_created_at: pool_created_at
  ).call

  pool.pool_scans.create!(
    volume_usd: data[:volume],
    reserve_in_usd: data[:reserve],
    health_score: result.health_score,
    flags: result.flags,
    scanned_at: Time.current
  )

  pair = "#{data[:base_token_symbol]}/#{data[:quote_token_symbol]}"
  puts "  ✓ #{data[:network_id].upcase.ljust(12)} #{pair.ljust(12)} #{data[:pool_address][0..15]}... → Score: #{result.health_score} (#{result.status})"
end

puts "\nSeeded #{demo_pools.size} pools with scans. Done!"

# Backfill latest_scan_id for any pools that were seeded before the FK column existed
puts "Backfilling latest_scan_id..."
backfilled = 0
Pool.where(latest_scan_id: nil).find_each do |pool|
  scan = pool.pool_scans.order(scanned_at: :desc).first
  if scan
    pool.update_column(:latest_scan_id, scan.id)
    backfilled += 1
  end
end
puts "  ✓ Backfilled #{backfilled} pool(s)" if backfilled > 0
