class CreatePoolScans < ActiveRecord::Migration[8.0]
  def change
    create_table :pool_scans, id: :uuid do |t|
      t.references :pool, null: false, foreign_key: true, type: :uuid
      t.decimal :volume_usd, precision: 18, scale: 2
      t.decimal :reserve_in_usd, precision: 18, scale: 2
      t.integer :health_score, default: 0
      t.jsonb :flags, default: []
      t.datetime :scanned_at, null: false

      t.timestamps
    end

    add_index :pool_scans, :scanned_at
  end
end
