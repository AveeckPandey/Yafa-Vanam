SELECT
  pv.sku,
  p.name AS product,
  s.name AS shade,
  pv.size,
  pv.stock_quantity,
  pv.reserved_quantity,
  pv.low_stock_threshold,
  (pv.stock_quantity - pv.reserved_quantity) AS available_stock
FROM product_variants pv
JOIN products p ON p.id = pv.product_id
LEFT JOIN shades s ON s.id = pv.shade_id
ORDER BY available_stock ASC;
