SELECT
  p.name AS product,
  s.name AS shade,
  pv.sku,
  vm.trending_score,
  vm.sales_growth_7d,
  vm.views_7d,
  vm.shade_selections_7d,
  vm.add_to_cart_7d,
  vm.units_sold_7d
FROM variant_metrics vm
JOIN product_variants pv ON pv.id = vm.variant_id
JOIN products p ON p.id = pv.product_id
LEFT JOIN shades s ON s.id = pv.shade_id
ORDER BY vm.trending_score DESC;
