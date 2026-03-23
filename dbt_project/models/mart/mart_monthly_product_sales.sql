{{ config(materialized='table') }}

SELECT
    DATE_TRUNC('month', o.order_date) AS sales_month,
    p.product_name,
    p.category,
    p.unit_price AS unit_price,
    ROUND((p.unit_price - p.unit_cost) / NULLIF(p.unit_price, 0) * 100, 2) AS margin_pct,
    oi.product_id,
    SUM(oi.quantity) AS total_qty_sold,
    SUM(oi.line_total) AS total_revenue_inr,
    COUNT(DISTINCT oi.order_id) AS total_orders
FROM {{ ref('stg_order_item') }} oi
LEFT JOIN {{ ref('stg_product') }} p
    ON oi.product_id = p.product_id
LEFT JOIN {{ ref('stg_orders') }} o
    ON oi.order_id = o.order_id
GROUP BY
    DATE_TRUNC('month', o.order_date),
    p.product_name,
    p.category,
    p.unit_price,
    p.unit_cost,
    oi.product_id
ORDER BY
    sales_month ASC