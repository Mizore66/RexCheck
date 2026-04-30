# frozen_string_literal: true

# Builds the canonical 5-feature vector used by DexGuard XGBoost (matches
# scripts/feature_extractor.py FeatureExtractor::FEATURE_NAMES /
# lib/ml_models/feature_schema.json).
class DexguardFeatureBuilder
  ORDER = [
    "liquidity_depth_usd",
    "volume_to_liquidity_ratio",
    "pooled_token_ratio",
    "contract_age_minutes",
    "price_volatility_1hr"
  ].freeze

  class << self
    # @param attrs [Hash] GeckoTerminal pool attributes (nested :volume_usd, etc.)
    # @param token_mint_at [Time, nil] optional mint time for comparison to pool_created_at
    # @param ohlcv_first_hour [Array<Array>, nil] minute OHLCV rows when fetched
    def feature_vector(attrs, token_mint_at: nil, ohlcv_first_hour: nil)
      attrs = deep_symbolize(attrs)

      reserve_usd = float_val(attrs[:reserve_in_usd])
      vol_usd = attrs[:volume_usd].is_a?(Hash) ? attrs[:volume_usd] : {}

      vol_1h = float_val(vol_usd[:h1])
      vol_1h = fallback_hourly_volume(vol_usd) if vol_1h <= 0

      volume_to_liq_ratio = reserve_usd.positive? ? (vol_1h / reserve_usd) : 0.0

      base_px = float_val(attrs[:base_token_price_usd])
      quote_px = float_val(attrs[:quote_token_price_usd])
      pooled_ratio = quote_px.positive? ? (base_px / quote_px) : 1.0

      pool_created_at = parse_time(attrs[:pool_created_at])
      mint_ref = token_mint_at || parse_time(attrs[:token_minted_at])
      contract_age_minutes =
        if pool_created_at && mint_ref
          ((pool_created_at - mint_ref) / 60.0).clamp(0.0, 1_000_000.0).to_f
        else
          0.0
        end

      price_vol = price_volatility_1hr(ohlcv_first_hour)

      [reserve_usd, volume_to_liq_ratio, pooled_ratio, contract_age_minutes, price_vol].map(&:to_f)
    end

    private

    def deep_symbolize(obj)
      case obj
      when Hash
        obj.each_with_object({}) { |(k, v), h| h[k.to_sym] = deep_symbolize(v) }
      when Array
        obj.map { |e| deep_symbolize(e) }
      else
        obj
      end
    end

    def float_val(x)
      Float(x)
    rescue ArgumentError, TypeError
      0.0
    end

    # When h1 is missing GeckoTerminal exposes h24 — approximate hourly rate.
    def fallback_hourly_volume(vol_usd)
      h24 = float_val(vol_usd[:h24])
      h24.positive? ? (h24 / 24.0) : 0.0
    end

    def parse_time(value)
      return nil if value.blank?

      (Time.zone || Time).parse(value.to_s).in_time_zone
    rescue ArgumentError
      nil
    end

    def price_volatility_1hr(ohlcv)
      return 0.0 if ohlcv.blank?

      closes = ohlcv.filter_map do |row|
        next unless row.is_a?(Array) && row.size > 4 && row[4]

        float_val(row[4])
      end

      mean = closes.sum / closes.size
      return 0.0 if mean <= 0

      variance = closes.sum { |c| (c - mean)**2 } / closes.size
      Math.sqrt(variance) / mean
    end
  end
end
