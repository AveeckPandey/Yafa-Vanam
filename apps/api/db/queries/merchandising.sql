-- name: TopVariantsByNetSales30D :many
WITH paid AS (
    SELECT oi.variant_id, SUM(oi.quantity)::bigint AS paid_units
    FROM order_items oi
    JOIN orders o ON o.id = oi.order_id
    WHERE o.payment_status IN ('CAPTURED', 'PARTIALLY_REFUNDED', 'REFUNDED')
      AND oi.created_at >= NOW() - INTERVAL '30 days'
    GROUP BY oi.variant_id
),
refunded AS (
    SELECT oi.variant_id, SUM(ri.quantity)::bigint AS refunded_units
    FROM refund_items ri
    JOIN refunds r ON r.id = ri.refund_id
    JOIN order_items oi ON oi.id = ri.order_item_id
    WHERE r.status = 'PROCESSED'
      AND r.created_at >= NOW() - INTERVAL '30 days'
    GROUP BY oi.variant_id
)
SELECT
    paid.variant_id,
    paid.paid_units,
    COALESCE(refunded.refunded_units, 0)::bigint AS refunded_units,
    (paid.paid_units - COALESCE(refunded.refunded_units, 0))::bigint AS net_units
FROM paid
LEFT JOIN refunded USING (variant_id)
ORDER BY net_units DESC;
