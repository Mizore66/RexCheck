class DashboardController < ApplicationController
  def index
    @pools = Pool.includes(:latest_scan)
                 .joins(:latest_scan)
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
