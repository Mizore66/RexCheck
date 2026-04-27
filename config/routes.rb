Rails.application.routes.draw do
  root "dashboard#index"

  namespace :api do
    namespace :v1 do
      namespace :mcp do
        get "pool_status", to: "pool_status#show"
      end
    end
  end

  get "up" => "rails/health#show", as: :rails_health_check
end
