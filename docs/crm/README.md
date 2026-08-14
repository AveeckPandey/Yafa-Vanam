# CRM

HubSpot Free is the initial CRM surface. PostgreSQL remains the master customer/business database.

The Go backend will sync appropriate customer properties such as order count, lifetime value, last order, segment, and selected preferences to HubSpot. HubSpot IDs are stored on `customer_profiles` for reconciliation.
