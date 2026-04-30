# frozen_string_literal: true

# Re-load the DexGuard XGBoost singleton after code reload in development and
# whenever autoloaded services change, so +lib/ml_models/xgboost_model.json+
# edits are picked up without a full process restart.
Rails.application.config.to_prepare do
  DexguardMlPredictor.reset_singleton! if defined?(DexguardMlPredictor)
end
