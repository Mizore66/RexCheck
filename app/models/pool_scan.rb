class PoolScan < ApplicationRecord
  belongs_to :pool

  validates :scanned_at, presence: true
  validates :health_score, numericality: { in: 0..100 }, allow_nil: true

  scope :recent, -> { order(scanned_at: :desc) }
  scope :danger, -> { where("health_score < ?", 50) }
  scope :warning, -> { where(health_score: 50..79) }
  scope :safe, -> { where(health_score: 80..100) }

  def status
    case health_score
    when 80..100 then "SAFE"
    when 50..79  then "WARNING"
    else "DANGER"
    end
  end

  def recommendation
    case status
    when "SAFE"    then "TRADE_WITH_CAUTION"
    when "WARNING" then "MONITOR_CLOSELY"
    when "DANGER"  then "DO_NOT_TRADE"
    end
  end
end
