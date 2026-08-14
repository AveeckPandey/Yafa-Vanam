SELECT
  u.id,
  u.email,
  u.name,
  u.phone_e164,
  cp.total_orders,
  cp.total_spent,
  cp.average_order_value,
  cp.segment,
  cp.last_visit_at,
  cp.last_order_at,
  cp.hubspot_contact_id
FROM users u
LEFT JOIN customer_profiles cp ON cp.user_id = u.id
ORDER BY cp.total_spent DESC NULLS LAST;
