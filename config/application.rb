require_relative "boot"

require "rails/all"

Bundler.require(*Rails.groups)

module Rexcheck
  class Application < Rails::Application
    config.load_defaults 8.0

    config.autoload_lib(ignore: %w[assets tasks])

    config.generators do |g|
      g.orm :active_record, primary_key_type: :uuid
    end

    config.active_record.schema_format = :sql

    config.active_job.queue_adapter = :solid_queue
  end
end
