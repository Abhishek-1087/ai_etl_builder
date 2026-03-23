{{ config(materialized='table') }}

SELECT
    c.segment,
    COUNT(DISTINCT c.customer_id)          AS total_customers,
    ROUND(100.0 * COUNT(DISTINCT c.customer_id) / SUM(COUNT(DISTINCT c.customer_id)) OVER (), 2) AS pct_share,
    SUM(CASE WHEN c.is_active = 1 THEN 1 ELSE 0 END) AS active_customers,
    SUM(CASE WHEN c.is_active = 0 THEN 1 ELSE 0 END) AS inactive_customers,
    
    COUNT(DISTINCT o.order_id) AS total_orders_count,
    COUNT(DISTINCT i.order_id) AS total_invoice_count,
    SUM(i.subtotal_inr)  AS total_invoice_spend_inr,
    AVG(i.subtotal_inr)  AS avg_invoice_value_inr
FROM {{ ref('stg_customer') }} c
LEFT JOIN {{ ref('stg_orders') }} o
    ON c.customer_id = o.customer_id
LEFT JOIN {{ ref('stg_invoice') }} i
    ON c.customer_id = i.customer_id
GROUP BY
    c.segment
ORDER BY
    total_customers DESC