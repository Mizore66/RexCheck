class Pool < ApplicationRecord
  has_many :pool_scans, dependent: :destroy
  belongs_to :latest_scan, class_name: "PoolScan", optional: true

  validates :network_id, presence: true
  validates :pool_address, presence: true, uniqueness: true

  scope :by_network, ->(network) { where(network_id: network) }
  scope :by_address, ->(address) { where(pool_address: address) }

  def status
    latest_scan&.status || "UNKNOWN"
  end

  def health_score
    latest_scan&.health_score || 0
  end
end
