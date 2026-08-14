SELECT
  p.name AS product,
  s.name AS shade,
  pv.sku,
  vm.net_units_sold_30d,
  vm.revenue_30d,
  vm.bestseller_product_rank,
  vm.bestseller_category_rank
FROM variant_metrics vm
JOIN product_variants pv ON pv.id = vm.variant_id
JOIN products p ON p.id = pv.product_id
LEFT JOIN shades s ON s.id = pv.shade_id
ORDER BY vm.net_units_sold_30d DESC;
