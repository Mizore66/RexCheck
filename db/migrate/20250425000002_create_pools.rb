class CreatePools < ActiveRecord::Migration[8.0]
  def change
    create_table :pools, id: :uuid do |t|
      t.string :network_id, null: false
      t.string :pool_address, null: false
      t.string :base_token_address
      t.string :quote_token_address

      t.timestamps
    end

    add_index :pools, :network_id
    add_index :pools, :pool_address, unique: true
  end
end
