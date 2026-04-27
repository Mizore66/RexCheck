module Api
  module V1
    module Mcp
      class PoolStatusController < ActionController::API
        # GET /api/v1/mcp/pool_status?address=0x...&network=eth
        def show
          address = params[:address]
          network = params[:network]

          unless address.present? && network.present?
            return render json: {
              error: "Missing required parameters: address and network"
            }, status: :bad_request
          end

          pool = Pool.find_by(pool_address: address, network_id: network)

          unless pool
            return render json: {
              error: "Pool not found",
              pool_address: address,
              network: network
            }, status: :not_found
          end

          latest_scan = pool.latest_scan

          unless latest_scan
            return render json: {
              pool_address: pool.pool_address,
              status: "UNKNOWN",
              health_score: nil,
              recommendation: "NO_DATA_AVAILABLE",
              flags: []
            }
          end

          render json: {
            pool_address: pool.pool_address,
            status: latest_scan.status,
            health_score: latest_scan.health_score,
            recommendation: latest_scan.recommendation,
            flags: latest_scan.flags
          }
        end
      end
    end
  end
end
