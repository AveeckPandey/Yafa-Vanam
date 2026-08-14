# YAFA VANAM Retool Admin

Retool is the planned internal operations surface, not the public storefront.

Use direct PostgreSQL access primarily for read-heavy dashboards and controlled inventory/admin views. Sensitive writes such as refunds, payment changes, order cancellation, replacements, lifecycle sends, and merchandising overrides should call authenticated Go admin endpoints so validation and audit logic remain centralized.

Planned sections: Overview, Customers/CRM, Orders, Payments, Returns, Refunds, Products, Variants/SKUs, Shades, Inventory, Merchandising, Analytics, Reviews, Lifecycle Marketing, and Settings.
