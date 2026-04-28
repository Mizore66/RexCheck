class AddTokenSymbolsToPools < ActiveRecord::Migration[8.0]
  def change
    add_column :pools, :base_token_symbol, :string
    add_column :pools, :quote_token_symbol, :string

    add_index :pools, :base_token_symbol
    add_index :pools, :quote_token_symbol
  end
end
