class PoolScan < ApplicationRecord
  belongs_to :pool

  validates :scanned_at, presence: true
  validates :health_score, numericality: { in: 0..100 }, allow_nil: true

  scope :recent, -> { order(scanned_at: :desc) }
  scope :danger, -> { where("health_score < ?", 50) }
  scope :warning, -> { where(health_score: 50..79) }
  scope :safe, -> { where(health_score: 80..100) }

  after_create_commit :update_pool_latest_scan
  after_create_commit -> {
    # Broadcast new row to the Live Pool Scanning table
    broadcast_prepend_to "pools_grid",
                         target: "pools_container",
                         partial: "dashboard/pool_row",
                         locals: { pool: pool, scan: self }

    # Broadcast updated stats
    stats = {
      total_pools: Pool.count,
      danger_count: PoolScan.where("scanned_at > ?", 24.hours.ago).danger.select(:pool_id).distinct.count,
      warning_count: PoolScan.where("scanned_at > ?", 24.hours.ago).warning.select(:pool_id).distinct.count,
      safe_count: PoolScan.where("scanned_at > ?", 24.hours.ago).safe.select(:pool_id).distinct.count
    }
    broadcast_replace_to "dashboard_stats",
                         target: "dashboard_stats_container",
                         partial: "dashboard/stats",
                         locals: { stats: stats }

    # Broadcast telemetry log entry
    status_label = status
    color_class = case status_label
                  when "SAFE" then "text-emerald-400"
                  when "WARNING" then "text-amber-400"
                  when "DANGER" then "text-rose-400"
                  else "text-slate-500"
                  end
    timestamp = Time.current.strftime("%H:%M:%S")
    Turbo::StreamsChannel.broadcast_append_to(
      "telemetry_log",
      target: "telemetry_log",
      html: "<p><span class=\"text-slate-600\">[#{timestamp}]</span> <span class=\"#{color_class}\">#{status_label}</span> → #{pool.network_id.upcase} #{pool.pool_address.truncate(16)} score:<span class=\"text-white tabular-nums\">#{health_score}</span></p>"
    )
  }

  def status
    case health_score
    when 80..100 then "SAFE"
    when 50..79  then "WARNING"
    else "DANGER"
    end
  end

  def recommendation
    case status
    when "SAFE"    then "TRADE_WITH_CAUTION"
    when "WARNING" then "MONITOR_CLOSELY"
    when "DANGER"  then "DO_NOT_TRADE"
    end
  end

  private

  def update_pool_latest_scan
    pool.update_column(:latest_scan_id, id)
  end
end
