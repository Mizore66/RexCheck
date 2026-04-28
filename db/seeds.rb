# db/seeds.rb
# Seed data for local development/demo purposes
# Run with: rails db:seed

puts "Seeding rexcheck development data..."

# Sample networks and pools
demo_pools = [
  {
    network_id: "eth",
    pool_address: "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    base_token_address: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    volume: 2_500_000,
    reserve: 150_000_000,
    age_hours: 720,
  },
  {
    network_id: "eth",
    pool_address: "0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801",
    base_token_address: "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
    quote_token_address: "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    volume: 850_000,
    reserve: 45_000_000,
    age_hours: 2160,
  },
  {
    network_id: "solana",
    pool_address: "7qbRF6YsyGuLUVs6Y1q64bdVrfe4ZcUUz1JRdoVNUJnm",
    base_token_address: "So11111111111111111111111111111111111111112",
    quote_token_address: "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    volume: 12_000_000,
    reserve: 80_000_000,
    age_hours: 48,
  },
  {
    network_id: "base",
    pool_address: "0xcDAC0d6c6C59727a65F871236188350531885C43",
    base_token_address: "0x4200000000000000000000000000000000000006",
    quote_token_address: "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    volume: 3_200,
    reserve: 5_000,
    age_hours: 0.5,
  },
  {
    network_id: "arbitrum",
    pool_address: "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
    base_token_address: "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
    quote_token_address: "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8",
    volume: 15_000_000,
    reserve: 200_000,
    age_hours: 168,
  },
  {
    network_id: "polygon_pos",
    pool_address: "0x45dDa9cb7c25131DF268515131f647d726f50608",
    base_token_address: "0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270",
    quote_token_address: "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
    volume: 500_000,
    reserve: 12_000_000,
    age_hours: 4320,
  },
  {
    network_id: "bsc",
    pool_address: "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
    base_token_address: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    quote_token_address: "0xe9e7cea3dedca5984780bafc599bd69add087d56",
    volume: 95_000,
    reserve: 3_500,
    age_hours: 0.25,
  },
  {
    network_id: "avalanche",
    pool_address: "0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE",
    base_token_address: "0xb31f66aa3c1e785363f0875a1b74e27b85fd66c7",
    quote_token_address: "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
    volume: 1_200_000,
    reserve: 25_000_000,
    age_hours: 2880,
  },
  {
    network_id: "optimism",
    pool_address: "0x68F5C0A2DE713a54991E01858Fd27a3832401849",
    base_token_address: "0x4200000000000000000000000000000000000006",
    quote_token_address: "0x7f5c764cbc14f9669b88837ca1490cca17c31607",
    volume: 750_000,
    reserve: 18_000_000,
    age_hours: 720,
  },
]

demo_pools.each do |data|
  pool = Pool.find_or_create_by!(pool_address: data[:pool_address]) do |p|
    p.network_id = data[:network_id]
    p.base_token_address = data[:base_token_address]
    p.quote_token_address = data[:quote_token_address]
  end

  # Calculate time for the pool
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

  puts "  ✓ #{data[:network_id].upcase} #{data[:pool_address][0..15]}... → Score: #{result.health_score} (#{result.status})"
end

puts "\nSeeded #{demo_pools.size} pools with scans. Done!"
