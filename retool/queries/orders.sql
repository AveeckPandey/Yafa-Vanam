SELECT
  o.order_number,
  o.customer_email,
  o.total_amount,
  o.currency,
  o.order_status,
  o.payment_status,
  o.fulfillment_status,
  o.created_at
FROM orders o
ORDER BY o.created_at DESC;
