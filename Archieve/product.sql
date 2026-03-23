SELECT
    TRIM(LOWER(REPLACE(COALESCE(PRICE, '0'), ' ', ''))) AS price,
    TRIM(LOWER(REPLACE(COALESCE(PRODUCT_NAME, 'UNKNOWN'), ' ', ''))) AS product_name,
    TRIM(LOWER(REPLACE(COALESCE(CATEGORY, 'UNKNOWN'), ' ', ''))) AS category,
FROM
    {{ source('raw', 'PRODUCT') }}