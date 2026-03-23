{{ config(materialized='table') }}

SELECT
    o.rep_id,
    COUNT(DISTINCT o.order_id) AS total_orders,
    AVG(o.discount_pct)         AS avg_discount_pct,
    SUM(CASE WHEN o.status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
    SUM(CASE WHEN o.status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
    c.city,
    c.state,
    c.segment,
    CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
    sr.region,
    CONCAT(sr.first_name, ' ', sr.last_name) AS rep_name,
    SUM(oi.quantity) AS total_units_sold,
    SUM(oi.line_total) AS total_line_revenue_inr
FROM {{ ref('stg_orders') }} o
LEFT JOIN {{ ref('stg_customer') }} c
    ON o.customer_id = c.customer_id
LEFT JOIN {{ ref('stg_sales_rep') }} sr
    ON o.rep_id = sr.rep_id
LEFT JOIN {{ ref('stg_order_item') }} oi
    ON o.order_id = oi.order_id
GROUP BY
    o.rep_id,
    c.city,
    c.state,
    c.segment,
    CONCAT(c.first_name, ' ', c.last_name),
    sr.region,
    CONCAT(sr.first_name, ' ', sr.last_name)
ORDER BY
    total_orders DESC