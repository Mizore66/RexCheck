module App
  module Services
    class RiskCalculator
      CRITICAL_LOW_LIQUIDITY_THRESHOLD = 10_000
      WASH_TRADING_RATIO = 10
      UNSEASONED_POOL_AGE_SECONDS = 3600 # 1 hour

      Result = Struct.new(:health_score, :flags, :status, :recommendation, keyword_init: true)

      def initialize(pool_data)
        @volume_usd = pool_data[:volume_usd].to_f
        @reserve_in_usd = pool_data[:reserve_in_usd].to_f
        @pool_created_at = pool_data[:pool_created_at]
      end

      def call
        score = 100
        flags = []

        # 1. Liquidity Depth Check
        if @reserve_in_usd < CRITICAL_LOW_LIQUIDITY_THRESHOLD
          score -= 50
          flags << "critical_low_liquidity"
        end

        # 2. Volume/Liquidity Ratio Check (Wash Trading Detection)
        if @reserve_in_usd > 0 && @volume_usd > (@reserve_in_usd * WASH_TRADING_RATIO)
          score -= 30
          flags << "wash_trading_suspected"
        end

        # 3. Age Check
        if @pool_created_at.present?
          pool_age_seconds = Time.current - Time.parse(@pool_created_at.to_s)
          if pool_age_seconds < UNSEASONED_POOL_AGE_SECONDS
            score -= 10
            flags << "unseasoned_pool"
          end
        end

        # Clamp score to 0-100
        score = score.clamp(0, 100)

        # Status Assignment
        status = case score
                 when 80..100 then "SAFE"
                 when 50..79  then "WARNING"
                 else "DANGER"
                 end

        recommendation = case status
                         when "SAFE"    then "TRADE_WITH_CAUTION"
                         when "WARNING" then "MONITOR_CLOSELY"
                         when "DANGER"  then "DO_NOT_TRADE"
                         end

        Result.new(
          health_score: score,
          flags: flags,
          status: status,
          recommendation: recommendation
        )
      end
    end
  end
end
