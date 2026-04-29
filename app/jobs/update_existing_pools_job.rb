require 'net/http'
require 'json'

class UpdateExistingPoolsJob < ApplicationJob
  queue_as :default

  # To respect GeckoTerminal rate limits (30 req/min), we process a small batch each turn.
  BATCH_SIZE = 10

  def perform
    # Priority: Refresh the latest 5 pools to ensure "nearly 0" discrepancy for new tokens
    latest_pools = Pool.order(created_at: :desc).limit(5)
    
    # Background: Rotate through older pools to keep them updated
    batch_oldest = BATCH_SIZE - latest_pools.count
    oldest_pools = Pool
      .left_outer_joins(:latest_scan)
      .where.not(id: latest_pools.pluck(:id))
      .order(Arel.sql("pool_scans.scanned_at ASC NULLS FIRST"))
      .limit(batch_oldest > 0 ? batch_oldest : 0)

    pools_to_update = latest_pools + oldest_pools

    pools_to_update.each do |pool|
      fetch_and_update_pool(pool)
      # Give it a tiny sleep to be super safe within the same job about limits
      sleep 1
    end
  end

  private

  def fetch_and_update_pool(pool)
    network = pool.network_id || 'eth' # fallback but should be populated
    url = URI("https://api.geckoterminal.com/api/v2/networks/#{network}/pools/#{pool.pool_address}")
    
    response = Net::HTTP.get_response(url)
    if response.is_a?(Net::HTTPSuccess)
      data = JSON.parse(response.body, symbolize_names: true)
      attrs = data.dig(:data, :attributes)
      return unless attrs

      volume_usd = attrs.dig(:volume_usd, :h24)&.to_f || 0.0
      reserve_in_usd = attrs[:reserve_in_usd]&.to_f || 0.0
      pool_created_at = attrs[:pool_created_at] || pool.created_at

      # Recalculate health score dynamically
      result = RiskCalculator.new({
        volume_usd: volume_usd,
        reserve_in_usd: reserve_in_usd,
        pool_created_at: pool_created_at
      }).call

      # Create new scan
      pool.pool_scans.create!(
        volume_usd: volume_usd,
        reserve_in_usd: reserve_in_usd,
        health_score: result.health_score,
        flags: result.flags,
        scanned_at: Time.current
      )
      
      Rails.logger.info("[UpdateExistingPoolsJob] Updated #{pool.pool_address} - Score: #{result.health_score}")
    else
      Rails.logger.warn("[UpdateExistingPoolsJob] Failed to fetch #{url}: #{response.code}")
    end
  rescue StandardError => e
    Rails.logger.error("[UpdateExistingPoolsJob] Error processing pool #{pool.pool_address}: #{e.message}")
  end
end
