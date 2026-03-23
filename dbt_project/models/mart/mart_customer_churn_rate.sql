{{ config(materialized='table') }}

SELECT
    c.segment,
    COUNT(DISTINCT c.customer_id)                  AS total_customers,
    SUM(CASE WHEN c.is_active = 1
        THEN 1 ELSE 0 END)                          AS active_customers,
    SUM(CASE WHEN c.is_active = 0
        THEN 1 ELSE 0 END)                          AS churned_customers,
    ROUND(100.0 * SUM(CASE WHEN c.is_active = 0
        THEN 1 ELSE 0 END)
        / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2) AS churn_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN c.is_active = 1
        THEN 1 ELSE 0 END)
        / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2) AS retention_rate_pct
FROM {{ ref('stg_customer') }} c
LEFT JOIN {{ ref('stg_orders') }} o
    ON c.customer_id = o.customer_id
LEFT JOIN {{ ref('stg_invoice') }} i
    ON c.customer_id = i.customer_id
GROUP BY
    c.segment
ORDER BY
    churn_rate_pct DESC