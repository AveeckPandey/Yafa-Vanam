SELECT
  COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) AS orders_today,
  COALESCE(SUM(total_amount) FILTER (WHERE payment_status = 'CAPTURED' AND created_at >= CURRENT_DATE), 0) AS revenue_today,
  COALESCE(AVG(total_amount) FILTER (WHERE payment_status = 'CAPTURED'), 0) AS average_order_value
FROM orders;
