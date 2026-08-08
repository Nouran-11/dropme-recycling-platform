INSERT INTO events (machine_id, material_type, item_count, event_timestamp, status)
SELECT 'kiosk-' || (g % 5),
       (ARRAY['PET', 'ALU', 'GLASS', 'HDPE', 'OTHER'])[1 + (g % 5)]::material_type,
       1 + (g % 10),
       now(),
       'received'
FROM generate_series(1, 200) g;
