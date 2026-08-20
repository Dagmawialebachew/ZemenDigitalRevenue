INSERT INTO settings (key, value, description)
VALUES
    ('commerce.currency', '"ETB"'::jsonb, 'Default commerce currency'),
    ('localization.default_language', '"am"'::jsonb, 'Default customer language'),
    ('referrals.default_commission_percent', '10'::jsonb, 'Default full-price referral commission percent'),
    ('referrals.discount_commission_enabled', 'false'::jsonb, 'Must remain false: discounted sales do not earn commission'),
    ('payments.manual_verification_enabled', 'true'::jsonb, 'Manual payment proof verification is enabled')
ON CONFLICT (key) DO NOTHING;
