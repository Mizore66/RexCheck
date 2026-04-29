class PoolIngestionJob < ApplicationJob
  queue_as :default

  REDIS_QUEUE_KEY = "rexcheck:raw_pools"

  def perform
    REDIS_POOL.with do |redis|
      # Process up to 200 raw pool payloads per job run to keep up with ingestion
      processed_count = 0
      200.times do
        raw = redis.lpop(REDIS_QUEUE_KEY)
        break unless raw

        payload = JSON.parse(raw, symbolize_names: true)
        process_pool(payload)
        processed_count += 1
      rescue JSON::ParserError => e
        Rails.logger.error("[PoolIngestionJob] Invalid JSON: #{e.message}")
        next
      end

      # If we hit the limit, re-enqueue immediately to process the rest
      if processed_count == 200 && redis.llen(REDIS_QUEUE_KEY) > 0
        PoolIngestionJob.perform_later
      end
    end
  end

  private

  def process_pool(payload)
    attrs = payload[:attributes] || payload
    pool_address = attrs[:address] || attrs[:pool_address]
    network_id = extract_network(payload)

    return unless pool_address.present? && network_id.present?

    pool_name = attrs[:name] || payload[:pool_name] || "Unknown Pool"

    pool = Pool.find_or_create_by!(pool_address: pool_address) do |p|
      p.network_id = network_id
      p.pool_name = pool_name
      p.base_token_address = dig_token_address(attrs, :base_token)
      p.quote_token_address = dig_token_address(attrs, :quote_token)
    end

    if pool.pool_name.blank? || pool.pool_name == "Unknown Pool"
      pool.update!(pool_name: pool_name) if pool_name != "Unknown Pool"
    end

    volume_usd = attrs.dig(:volume_usd, :h24).to_f || attrs[:volume_usd].to_f
    reserve_in_usd = attrs[:reserve_in_usd].to_f

    # Throttling and Change Detection
    last_scan = pool.latest_scan
    if last_scan.present?
      # If data is identical and last scan was recent (< 2 mins), skip
      # We allow small differences to trigger a new scan for accuracy
      if (last_scan.volume_usd.to_f == volume_usd) &&
         (last_scan.reserve_in_usd.to_f == reserve_in_usd) &&
         (last_scan.scanned_at > 2.minutes.ago)
        return
      end
    end

    pool_created_at = attrs[:pool_created_at] || attrs[:created_at]

    result = RiskCalculator.new({
      volume_usd: volume_usd,
      reserve_in_usd: reserve_in_usd,
      pool_created_at: pool_created_at
    }).call

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
