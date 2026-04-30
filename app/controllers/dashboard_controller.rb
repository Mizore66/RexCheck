class DashboardController < ApplicationController
  def index
    @pools = Pool.includes(:latest_scan)
                 .joins(:latest_scan)
                 .order("pool_scans.scanned_at DESC")
                 .limit(60)

    @popular_pools = Pool.includes(:latest_scan)
                         .joins(:latest_scan)
                         .order("pool_scans.reserve_in_usd DESC, pool_scans.volume_usd DESC")
                         .limit(24)

    @network_tabs = Pool.joins(:latest_scan)
                        .distinct
                        .pluck(:network_id)
                        .compact
                        .sort

    @popular_pools_by_network = @network_tabs.index_with do |network|
      Pool.includes(:latest_scan)
          .joins(:latest_scan)
          .where(network_id: network)
          .order("pool_scans.reserve_in_usd DESC, pool_scans.volume_usd DESC")
          .limit(12)
    end

    @stats = {
      total_pools: Pool.count,
      danger_count: PoolScan.where("scanned_at > ?", 24.hours.ago).danger.select(:pool_id).distinct.count,
      warning_count: PoolScan.where("scanned_at > ?", 24.hours.ago).warning.select(:pool_id).distinct.count,
      safe_count: PoolScan.where("scanned_at > ?", 24.hours.ago).safe.select(:pool_id).distinct.count
    }
  end
end
