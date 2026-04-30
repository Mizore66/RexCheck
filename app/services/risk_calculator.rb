# frozen_string_literal: true

# Produces :health_score (0–100), :flags, :status, and :recommendation for a pool.
#
# When the DexGuard XGBoost model is available (+lib/ml_models/xgboost_model.json+
# and +xgb+ gem), the numeric score reflects +P(SAFE) * 100+ from inference.
#
# Fallback: heuristic rules match the legacy dexguard specification when ML is disabled
# (set ENV +DEXGUARD_USE_HEURISTIC_SCORE=true+), or when the predictor cannot load.

class RiskCalculator
  CRITICAL_LOW_LIQUIDITY_THRESHOLD = 10_000
  WASH_TRADING_RATIO = 10
  UNSEASONED_POOL_AGE_SECONDS = 3600 # 1 hour

  Result = Struct.new(
    :health_score,
    :flags,
    :status,
    :recommendation,
    :ml_safe_probability,
    keyword_init: true
  )

  def initialize(pool_data)
    @pool_data =
      case pool_data
      when Hash
        pool_data.deep_symbolize_keys
      else
        {}
      end
  end

  def call
    if heuristic_forced?
      call_heuristic
    elsif dexguard_ml.available?
      call_ml_model
    else
      call_heuristic
    end
  end

  private

  def dexguard_ml
    DexguardMlPredictor.instance
  end

  def heuristic_forced?
    ActiveModel::Type::Boolean.new.cast(ENV["DEXGUARD_USE_HEURISTIC_SCORE"])
  end

  def gecko_attributes_hash
    if @pool_data[:attributes].is_a?(Hash)
      @pool_data[:attributes]
    elsif @pool_data[:reserve_in_usd] || @pool_data[:volume_usd].is_a?(Numeric)
      legacy_flat_to_nested(@pool_data)
    else
      {}
    end
  end

  def legacy_flat_to_nested(p)
    vol = float_of(p[:volume_usd])
    vol_h1 = float_of(p[:volume_h1])
    vol_h1 = vol / 24.0 if vol_h1.zero? && vol.positive?

    {
      reserve_in_usd: float_of(p[:reserve_in_usd]),
      pool_created_at: p[:pool_created_at],
      volume_usd: { h24: vol, h1: vol_h1 },
      base_token_price_usd: p[:base_token_price_usd],
      quote_token_price_usd: p[:quote_token_price_usd]
    }
  end

  # --- ML scoring ---------------------------------------------------------

  def call_ml_model
    attrs = gecko_attributes_hash.deep_symbolize_keys

    feats = DexguardFeatureBuilder.feature_vector(
      attrs,
      token_mint_at: @pool_data[:token_mint_at],
      ohlcv_first_hour: @pool_data[:ohlcv_first_hour]
    )

    prob = dexguard_ml.predict_safe_probability(feats)
    score = (prob * 100.0).round.clamp(0, 100)
    st = status_from_score(score)

    Result.new(
      health_score: score,
      flags: interpretability_flags_for(attrs),
      status: st,
      recommendation: recommendation_from_status(st),
      ml_safe_probability: prob.round(6)
    )
  end

  # Human-readable hints (not subtracted points — UX transparency only).

  def interpretability_flags_for(attrs)
    flags = []

    reserve = float_of(attrs[:reserve_in_usd])
    vol_usd = attrs[:volume_usd].is_a?(Hash) ? attrs[:volume_usd] : {}
    vol_24 = float_of(vol_usd[:h24])

    if reserve < CRITICAL_LOW_LIQUIDITY_THRESHOLD
      flags << "critical_low_liquidity"
    end

    if reserve.positive? && vol_24 > (reserve * WASH_TRADING_RATIO)
      flags << "wash_trading_suspected"
    end

    if attrs[:pool_created_at].present?
      parsed = parse_pool_time(attrs[:pool_created_at])
      if parsed && (Time.current - parsed) < UNSEASONED_POOL_AGE_SECONDS
        flags << "unseasoned_pool"
      end
    end

    flags
  rescue StandardError => e
    Rails.logger.debug { "[RiskCalculator] flag hints skipped: #{e.message}" }
    []
  end

  def parse_pool_time(value)
    return nil if value.blank?

    Time.zone.parse(value.to_s)
  rescue ArgumentError
    Time.parse(value.to_s)
  rescue ArgumentError
    nil
  end

  # --- Heuristic fallback (legacy) ---------------------------------------

  def call_heuristic
    attrs = legacy_flat_attrs_for_heuristic
    reserve = attrs[:reserve]
    volume = attrs[:volume_24]

    score = 100
    flags = []

    if reserve < CRITICAL_LOW_LIQUIDITY_THRESHOLD
      score -= 50
      flags << "critical_low_liquidity"
    end

    if reserve > 0 && volume > (reserve * WASH_TRADING_RATIO)
      score -= 30
      flags << "wash_trading_suspected"
    end

    if attrs[:created_raw].present?
      begin
        parsed = Time.zone ? Time.zone.parse(attrs[:created_raw].to_s) : Time.parse(attrs[:created_raw].to_s)
        if Time.current - parsed < UNSEASONED_POOL_AGE_SECONDS
          score -= 10
          flags << "unseasoned_pool"
        end
      rescue ArgumentError
        # ignore
      end
    end

    score = score.clamp(0, 100)
    st = status_from_score(score)

    Result.new(
      health_score: score,
      flags: flags,
      status: st,
      recommendation: recommendation_from_status(st),
      ml_safe_probability: nil
    )
  end

  def legacy_flat_attrs_for_heuristic
    attrs = gecko_attributes_hash.deep_symbolize_keys

    reserve = float_of(attrs[:reserve_in_usd])
    volume = if attrs.dig(:volume_usd, :h24)
               float_of(attrs.dig(:volume_usd, :h24))
             else
               float_of(@pool_data[:volume_usd])
             end

    created = attrs[:pool_created_at] || @pool_data[:pool_created_at]

    { reserve:, volume_24: volume, created_raw: created }
  end

  def float_of(val)
    Float(val)
  rescue ArgumentError, TypeError
    0.0
  end

  # --- Labels -------------------------------------------------------------

  def status_from_score(score)
    case score
    when 80..100 then "SAFE"
    when 50..79  then "WARNING"
    else "DANGER"
    end
  end

  def recommendation_from_status(status)
    case status
    when "SAFE" then "TRADE_WITH_CAUTION"
    when "WARNING" then "MONITOR_CLOSELY"
    when "DANGER" then "DO_NOT_TRADE"
    end
  end
end
