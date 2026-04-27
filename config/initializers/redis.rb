require "connection_pool"

REDIS_POOL = ConnectionPool.new(size: ENV.fetch("RAILS_MAX_THREADS", 5).to_i, timeout: 5) do
  Redis.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0"))
end
