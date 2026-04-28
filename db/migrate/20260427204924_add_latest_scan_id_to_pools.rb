class AddLatestScanIdToPools < ActiveRecord::Migration[8.1]
  def change
    add_column :pools, :latest_scan_id, :uuid
  end
end
