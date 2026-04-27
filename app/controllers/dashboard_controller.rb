class DashboardController < ApplicationController
  def index
    @pools = Pool.includes(:pool_scans)
                 .joins(:pool_scans)
                 .select("pools.*, pool_scans.health_score, pool_scans.scanned_at")
                 .where("pool_scans.id = (SELECT ps.id FROM pool_scans ps WHERE ps.pool_id = pools.id ORDER BY ps.scanned_at DESC LIMIT 1)")
                 .order("pool_scans.scanned_at DESC")
                 .limit(60)

    @stats = {
      total_pools: Pool.count,
      danger_count: PoolScan.where("scanned_at > ?", 24.hours.ago).danger.select(:pool_id).distinct.count,
      warning_count: PoolScan.where("scanned_at > ?", 24.hours.ago).warning.select(:pool_id).distinct.count,
      safe_count: PoolScan.where("scanned_at > ?", 24.hours.ago).safe.select(:pool_id).distinct.count
    }
  end
end
