-- Ensure carts table allows guest carts with neither user_id nor anonymous_key,
-- and guarantee all check constraints on carts are dropped regardless of their
-- generated names.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'carts'::regclass AND contype = 'c'
    ) LOOP
        EXECUTE 'ALTER TABLE carts DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
    END LOOP;
END $$;

-- Ensure cart_items variant_id allows catalogue string IDs without UUID foreign key checks
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'cart_items'::regclass AND contype = 'f'
          AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'cart_items'::regclass AND attname = 'variant_id')]
    ) LOOP
        EXECUTE 'ALTER TABLE cart_items DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
    END LOOP;
END $$;

ALTER TABLE cart_items
    ALTER COLUMN variant_id TYPE TEXT USING variant_id::text;

-- Ensure order_items variant_id and product_id allow catalogue string IDs
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'order_items'::regclass AND contype = 'f'
          AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'order_items'::regclass AND attname = 'variant_id')]
    ) LOOP
        EXECUTE 'ALTER TABLE order_items DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
    END LOOP;
    FOR r IN (
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'order_items'::regclass AND contype = 'f'
          AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'order_items'::regclass AND attname = 'product_id')]
    ) LOOP
        EXECUTE 'ALTER TABLE order_items DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
    END LOOP;
END $$;

ALTER TABLE order_items
    ALTER COLUMN product_id TYPE TEXT USING product_id::text,
    ALTER COLUMN variant_id TYPE TEXT USING variant_id::text;
