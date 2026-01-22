CREATE INDEX idx_sku_name ON music_products(sku, name);

CREATE INDEX idx_sku_name_items ON music_order_items(sku, name);

CREATE INDEX idx_orders_id ON music_orders(order_id);