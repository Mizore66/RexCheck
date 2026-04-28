class Pool < ApplicationRecord
  has_many :pool_scans, dependent: :destroy
  belongs_to :latest_scan, class_name: "PoolScan", optional: true

  validates :network_id, presence: true
  validates :pool_address, presence: true, uniqueness: true

  scope :by_network, ->(network) { where(network_id: network) }
  scope :by_address, ->(address) { where(pool_address: address) }
  scope :by_token_symbol, ->(symbol) {
    where("UPPER(base_token_symbol) = ? OR UPPER(quote_token_symbol) = ?", symbol.upcase, symbol.upcase)
  }

  def status
    latest_scan&.status || "UNKNOWN"
  end

  def health_score
    latest_scan&.health_score || 0
  end

  def pair_label
    if base_token_symbol.present? && quote_token_symbol.present?
      "#{base_token_symbol}/#{quote_token_symbol}"
    else
      pool_address.truncate(16)
    end
  end
end
