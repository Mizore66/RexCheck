module Api
  module V1
    module Mcp
      class TokenAnalysisController < ActionController::API
        # GET /api/v1/mcp/token_analysis?symbol=ETH
        # GET /api/v1/mcp/token_analysis?symbol=ETH&network=eth  (optional filter)
        def show
          symbol = params[:symbol]&.strip
          network = params[:network]&.strip

          unless symbol.present?
            return render json: {
              error: "Missing required parameter: symbol (e.g. ETH, SOL, USDC)"
            }, status: :bad_request
          end

          pools = Pool.by_token_symbol(symbol)
          pools = pools.by_network(network) if network.present?
          pools = pools.includes(:pool_scans)

          if pools.empty?
            return render json: {
              symbol: symbol.upcase,
              error: "No pools found for token #{symbol.upcase}",
              hint: "Available tokens: #{available_token_symbols.join(', ')}"
            }, status: :not_found
          end

          pool_results = pools.map do |pool|
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
          end.compact

          if pool_results.empty?
            return render json: {
              symbol: symbol.upcase,
              error: "Pools found but no scan data available yet"
            }, status: :not_found
          end

          scores = pool_results.map { |p| p[:health_score] }
          avg_score = (scores.sum.to_f / scores.size).round
          all_flags = pool_results.flat_map { |p| p[:flags] }.uniq.sort

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

          render json: {
            symbol: symbol.upcase,
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
        end

        private

        def available_token_symbols
          Pool.where.not(base_token_symbol: nil)
              .pluck(:base_token_symbol, :quote_token_symbol)
              .flatten
              .uniq
              .compact
              .sort
        end
      end
    end
  end
end
