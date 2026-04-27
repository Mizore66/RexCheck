class PoolIngestionJob < ApplicationJob
  queue_as :default

  REDIS_QUEUE_KEY = "rexcheck:raw_pools"

  def perform
    REDIS_POOL.with do |redis|
      # Process up to 50 raw pool payloads per job run
      50.times do
        raw = redis.lpop(REDIS_QUEUE_KEY)
        break unless raw

        payload = JSON.parse(raw, symbolize_names: true)
        process_pool(payload)
      rescue JSON::ParserError => e
        Rails.logger.error("[PoolIngestionJob] Invalid JSON: #{e.message}")
        next
      end
    end
  end

  private

  def process_pool(payload)
    attrs = payload[:attributes] || payload
    pool_address = attrs[:address] || attrs[:pool_address]
    network_id = extract_network(payload)

    return unless pool_address.present? && network_id.present?

    pool = Pool.find_or_create_by!(pool_address: pool_address) do |p|
      p.network_id = network_id
      p.base_token_address = dig_token_address(attrs, :base_token)
      p.quote_token_address = dig_token_address(attrs, :quote_token)
    end

    volume_usd = attrs.dig(:volume_usd, :h24).to_f || attrs[:volume_usd].to_f
    reserve_in_usd = attrs[:reserve_in_usd].to_f

    pool_created_at = attrs[:pool_created_at] || attrs[:created_at]

    result = App::Services::RiskCalculator.new(
      volume_usd: volume_usd,
      reserve_in_usd: reserve_in_usd,
      pool_created_at: pool_created_at
    ).call

    pool.pool_scans.create!(
      volume_usd: volume_usd,
      reserve_in_usd: reserve_in_usd,
      health_score: result.health_score,
      flags: result.flags,
      scanned_at: Time.current
    )

    Rails.logger.info(
      "[PoolIngestionJob] Processed #{pool_address} on #{network_id} — " \
      "Score: #{result.health_score} (#{result.status})"
    )
  rescue ActiveRecord::RecordInvalid => e
    Rails.logger.error("[PoolIngestionJob] DB error for #{pool_address}: #{e.message}")
  end

  def extract_network(payload)
    # GeckoTerminal API returns network in relationships or as a top-level field
    payload.dig(:relationships, :network, :data, :id) ||
      payload[:network_id] ||
      payload[:network]
  end

  def dig_token_address(attrs, token_key)
    attrs.dig(token_key, :address) ||
      attrs[:"#{token_key}_address"]
  end
end
