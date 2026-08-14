-- name: GetOrderByNumber :one
SELECT * FROM orders WHERE order_number = $1;

-- name: ListOrderItems :many
SELECT * FROM order_items WHERE order_id = $1 ORDER BY created_at;
