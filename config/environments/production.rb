require "active_support/core_ext/integer/time"

Rails.application.configure do
  config.enable_reloading = false
  config.eager_load = true
  config.consider_all_requests_local = false
  config.action_controller.perform_caching = true

  config.public_file_server.enabled = ENV["RAILS_SERVE_STATIC_FILES"].present? || ENV["RENDER"].present?
  config.public_file_server.headers = { "Cache-Control" => "public, max-age=#{1.year.to_i}" }

  config.assets.compile = false

  config.active_storage.service = :amazon

  config.force_ssl = true
  config.assume_ssl = true

  config.logger = ActiveSupport::Logger.new($stdout)
    .tap  { |logger| logger.formatter = ::Logger::Formatter.new }
    .then { |logger| ActiveSupport::TaggedLogging.new(logger) }

  config.log_tags = [:request_id]
  config.log_level = ENV.fetch("RAILS_LOG_LEVEL", "info")

  config.action_mailer.perform_caching = false

  config.active_support.report_deprecations = false

  config.active_record.dump_schema_after_migration = false

  config.cache_store = :redis_cache_store, { url: ENV.fetch("REDIS_URL", "redis://localhost:6379/1") }
end
