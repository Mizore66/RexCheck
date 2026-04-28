class AnalyzeController < ApplicationController
  def index
    symbol = params[:symbol]&.strip&.upcase

    if symbol.present?
      pools = Pool.by_token_symbol(symbol).includes(:pool_scans)

      pool_results = pools.filter_map do |pool|
        scan = pool.latest_scan
        next unless scan

        {
          pool_address: pool.pool_address,
          network: pool.network_id,
          pair: pool.pair_label,
          health_score: scan.health_score,
          status: scan.status,
          recommendation: scan.recommendation,
          flags: scan.flags,
          volume_usd: scan.volume_usd,
          reserve_in_usd: scan.reserve_in_usd,
          scanned_at: scan.scanned_at
        }
      end

      if pool_results.any?
        scores = pool_results.map { |p| p[:health_score] }
        avg_score = (scores.sum.to_f / scores.size).round
        all_flags = pool_results.flat_map { |p| p[:flags] }.tally.sort_by { |_, count| -count }.map(&:first)

        overall_status = case avg_score
                         when 80..100 then "SAFE"
                         when 50..79  then "WARNING"
                         else "DANGER"
                         end

        recommendation = case overall_status
                         when "SAFE"    then "TRADE_WITH_CAUTION"
                         when "WARNING" then "MONITOR_CLOSELY"
                         when "DANGER"  then "DO_NOT_TRADE"
                         end

        @result = {
          symbol: symbol,
          pool_count: pool_results.size,
          avg_health_score: avg_score,
          min_health_score: scores.min,
          max_health_score: scores.max,
          overall_status: overall_status,
          recommendation: recommendation,
          flags: all_flags,
          networks: pool_results.map { |p| p[:network] }.uniq.sort,
          pools: pool_results.sort_by { |p| -p[:health_score] }
        }
      else
        @not_found = symbol
      end
    end

    @available_tokens = Pool.where.not(base_token_symbol: nil)
                            .pluck(:base_token_symbol, :quote_token_symbol)
                            .flatten.uniq.compact.sort
  end
end
