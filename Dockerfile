# ==============================================================================
# rexcheck Rails Application Dockerfile
# Optimized for AWS ECS Fargate deployment
# ==============================================================================

# Stage 1: Build
FROM ruby:3.3-slim AS builder

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    node-gyp \
    libyaml-dev \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install --no-install-recommends -y nodejs && \
    npm install -g yarn && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Ruby dependencies
COPY Gemfile Gemfile.lock ./
RUN bundle config set --local deployment true && \
    bundle config set --local without 'development test' && \
    bundle install --jobs 4 --retry 3 && \
    rm -rf /usr/local/bundle/cache/*.gem

# Install Node dependencies & build assets
COPY package.json yarn.lock* ./
RUN npm install --production=false

COPY . .
RUN npm run build && \
    npm run build:css

# Precompile assets
RUN SECRET_KEY_BASE=placeholder_for_precompile \
    RAILS_ENV=production \
    bundle exec rails assets:precompile

# Remove node_modules to slim the image
RUN rm -rf node_modules tmp/cache

# Stage 2: Production Runtime
FROM ruby:3.3-slim AS runtime

RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system --gid 1000 rails && \
    useradd --system --uid 1000 --gid rails --create-home rails

WORKDIR /app

# Copy built artifacts
COPY --from=builder /usr/local/bundle /usr/local/bundle
COPY --from=builder /app /app

# Set ownership
RUN chown -R rails:rails /app

USER rails

# Runtime configuration
ENV RAILS_ENV=production \
    RAILS_LOG_TO_STDOUT=1 \
    RAILS_SERVE_STATIC_FILES=1 \
    RUBY_YJIT_ENABLE=1 \
    PORT=3000

EXPOSE 3000

# Health check for ECS
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:3000/up || exit 1

ENTRYPOINT ["bundle", "exec"]
CMD ["puma", "-C", "config/puma.rb"]
