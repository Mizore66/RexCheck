# frozen_string_literal: true

require "json"

# Loads lib/ml_models/xgboost_model.json at boot and runs binary:logistic inference.
# Falls back to a no-op predictor when the xgb gem or model files are unavailable.
class DexguardMlPredictor
  class Error < StandardError; end

  @mutex = Mutex.new

  class << self
    # Thread-safe singleton. Recreated after each reload in development (to_prepare).
    def instance
      @mutex.synchronize { @singleton ||= build_predictor }
    end

    def reset_singleton!
      @mutex.synchronize { @singleton = nil }
    end

    private

    def build_predictor
      new
    rescue Error, LoadError => e
      Rails.logger.warn("[DexguardMlPredictor] ML disabled (#{e.class}: #{e.message})")
      NullPredictor.new
    end
  end

  attr_reader :threshold, :feature_names

  def initialize
    require "xgboost"

    @model_path = Rails.root.join("lib/ml_models/xgboost_model.json")
    @schema_path = Rails.root.join("lib/ml_models/feature_schema.json")

    raise Error, "Missing #{@model_path}" unless @model_path.file?
    raise Error, "Missing #{@schema_path}" unless @schema_path.file?

    schema = JSON.parse(File.read(@schema_path))
    @feature_names = Array(schema["feature_names"]).map(&:to_s)
    @threshold = schema["decision_threshold"].to_f

    @booster = XGBoost::Booster.new(model_file: @model_path.to_s)
    n = @booster.num_features
    unless n == @feature_names.size
      raise Error, "Model expects #{n} features but schema lists #{@feature_names.size}"
    end
  end

  def available?
    true
  end

  # @param feature_row [Array<Float>] Same order as +feature_names+ / feature_schema.json
  # @return [Float] calibrated P(class SAFE)
  def predict_safe_probability(feature_row)
    row = Array(feature_row).map(&:to_f)
    unless row.size == @feature_names.size
      raise ArgumentError, "expected #{@feature_names.size} features, got #{row.size}"
    end

    dmat = XGBoost::DMatrix.new([row])
    raw = @booster.predict(dmat)
    val = Array(raw).flatten.first
    val.to_f.clamp(0.0, 1.0)
  end

  # Used when inference is unavailable — keeps RiskCalculator on the heuristic branch.
  class NullPredictor
    def available?
      false
    end

    def threshold
      0.5
    end

    def feature_names
      DexguardFeatureBuilder::ORDER
    end

    def predict_safe_probability(_feature_row)
      0.5
    end
  end
end
