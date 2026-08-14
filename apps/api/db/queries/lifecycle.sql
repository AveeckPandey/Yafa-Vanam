-- name: GetLifecycleCandidate :one
SELECT
    u.id,
    u.email,
    u.phone_e164,
    cp.visits_14d,
    cp.last_order_at,
    cp.segment
FROM users u
JOIN customer_profiles cp ON cp.user_id = u.id
WHERE u.id = $1;

-- name: HasWhatsAppMarketingConsent :one
SELECT EXISTS (
    SELECT 1
    FROM communication_consents
    WHERE user_id = $1
      AND channel = 'WHATSAPP'
      AND purpose = 'MARKETING'
      AND status = 'GRANTED'
      AND revoked_at IS NULL
)::boolean;
