Rails.application.routes.draw do
  root "dashboard#index"

  get "analyze", to: "analyze#index"

  namespace :api do
    namespace :v1 do
      namespace :mcp do
        get "pool_status",     to: "pool_status#show"
        get "token_analysis",  to: "token_analysis#show"
        get "list_tokens",     to: "token_analysis#list_tokens"
      end
    end
  end

  get "up" => "rails/health#show", as: :rails_health_check
end
