{{ config(materialized='table') }}

SELECT
    c.city,
    COUNT(DISTINCT c.customer_id)          AS active_customers,
    COUNT(DISTINCT o.order_id) AS total_orders_count,
    COUNT(DISTINCT i.order_id) AS total_invoice_count,
    SUM(i.subtotal_inr)  AS total_invoice_spend_inr,
    AVG(i.subtotal_inr)  AS avg_invoice_value_inr
FROM {{ ref('stg_customer') }} c
LEFT JOIN {{ ref('stg_orders') }} o
    ON c.customer_id = o.customer_id
LEFT JOIN {{ ref('stg_invoice') }} i
    ON c.customer_id = i.customer_id
WHERE c.is_active = 1
GROUP BY
    c.city
ORDER BY
    active_customers DESC