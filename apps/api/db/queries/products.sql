-- name: GetProductBySlug :one
SELECT p.*
FROM products p
WHERE p.slug = $1 AND p.status = 'ACTIVE';

-- name: ListProductVariants :many
SELECT pv.*, s.name AS shade_name, s.hex, s.undertone, s.depth
FROM product_variants pv
LEFT JOIN shades s ON s.id = pv.shade_id
WHERE pv.product_id = $1 AND pv.is_active = TRUE
ORDER BY s.sort_order NULLS LAST, pv.created_at;
