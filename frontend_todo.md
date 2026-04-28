- [x] Step 1: Create a partial `_pool_card.html.erb` for the individual pool UI.
- [x] Step 2: Use Turbo Streams to establish an ActionCable connection in `dashboard/index.html.erb` and update the grid to render the new partial.
- [x] Step 3: Implement `after_create_commit` on the `PoolScan` model to broadcast `prepend_to` a Turbo stream `pools_stream`.
- [x] Step 4: Fix the N+1 query bottleneck in `DashboardController#index` by tracking the `latest_scan_id` on the `Pool` table.
- [x] Step 5: Create a migration to add `latest_scan_id` to `pools`.
- [x] Step 6: Update `PoolScan` to correctly set `latest_scan_id` on the parent `Pool` when created.
- [x] Step 7: Update `DashboardController` to use `includes(:latest_scan)` instead of a heavy correlated subquery.
- [x] Step 8: Update Stats row partial to broadcast updates to the dashboard numbers.
```
