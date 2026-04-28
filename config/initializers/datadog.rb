# config/initializers/datadog.rb
# ==============================================================================
# Datadog APM & Custom Metrics for RexCheck Rails Intelligence Layer
# ==============================================================================
#
# Configuration:
#   DD_AGENT_HOST     - Datadog agent hostname (default: localhost)
#   DD_ENV            - Environment tag (default: development)
#   DD_SERVICE        - Service name (default: rexcheck-api)
#   DD_TRACE_ENABLED  - Enable/disable tracing (default: true)
#
# Custom Metrics (Section 2 of DexGuard Plan):
#   dexguard.api.cache_miss    - counter when Lazy Analysis is triggered
#   dexguard.api.health_score  - distribution of health scores returned
# ==============================================================================

if ENV.fetch("DD_TRACE_ENABLED", "false") == "true"
  begin
    require "datadog/statsd"
    require "ddtrace"

    Datadog.configure do |c|
      c.service = ENV.fetch("DD_SERVICE", "rexcheck-api")
      c.env = ENV.fetch("DD_ENV", "development")

      # Auto-instrument Rails, Redis, and PostgreSQL
      c.tracing.instrument :rails
      c.tracing.instrument :redis
      c.tracing.instrument :pg

      # Distributed tracing across Redis boundary
      c.tracing.distributed_tracing = true
    end

    # Global StatsD client for custom metrics
    DATADOG_STATSD = Datadog::Statsd.new(
      ENV.fetch("DD_AGENT_HOST", "localhost"),
      ENV.fetch("DD_DOGSTATSD_PORT", "8125").to_i,
      namespace: "dexguard",
      tags: [
        "env:#{ENV.fetch('DD_ENV', 'development')}",
        "service:#{ENV.fetch('DD_SERVICE', 'rexcheck-api')}",
      ]
    )

    Rails.logger.info "[Datadog] APM and StatsD initialized"

  rescue LoadError => e
    Rails.logger.warn "[Datadog] ddtrace gem not available: #{e.message}. Metrics disabled."
    DATADOG_STATSD = nil
  end
else
  DATADOG_STATSD = nil
end

# Convenience module for emitting metrics throughout the app
module DexguardMetrics
  module_function

  def cache_miss(pool_address:, network:)
    return unless defined?(DATADOG_STATSD) && DATADOG_STATSD

    DATADOG_STATSD.increment(
      "api.cache_miss",
      tags: ["network:#{network}", "pool_address:#{pool_address}"]
    )
  end

  def health_score(score:, network:)
    return unless defined?(DATADOG_STATSD) && DATADOG_STATSD

    DATADOG_STATSD.distribution(
      "api.health_score",
      score,
      tags: ["network:#{network}"]
    )
  end
end
