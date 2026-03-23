{{ config(materialized='table') }}

SELECT
    DATE_TRUNC('month', i.invoice_date) AS invoice_month,
    COUNT(i.invoice_id) AS total_invoices,
    SUM(i.subtotal_inr)  AS total_billed_inr,
    AVG(i.subtotal_inr)  AS avg_invoice_value_inr,
    SUM(i.tax_amount_inr) AS total_tax_collected_inr,
    SUM(CASE WHEN i.is_paid = 1 THEN 1 ELSE 0 END) AS paid_invoices,
    SUM(CASE WHEN i.is_paid = 0 THEN 1 ELSE 0 END) AS unpaid_invoices,
    SUM(CASE WHEN i.is_paid = 0 THEN i.subtotal_inr ELSE 0 END) AS total_outstanding_inr,
    SUM(CASE WHEN i.is_paid = 0 AND DATEDIFF('day', i.due_date, CURRENT_DATE()) > 0 THEN 1 ELSE 0 END) AS overdue_invoices,
    CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
    c.email,
    c.city,
    c.segment,
    RANK() OVER (ORDER BY SUM(i.subtotal_inr) DESC) AS revenue_rank
FROM {{ ref('stg_invoice') }} i
LEFT JOIN {{ ref('stg_customer') }} c
    ON i.customer_id = c.customer_id
LEFT JOIN {{ ref('stg_orders') }} o
    ON i.order_id = o.order_id
WHERE i.invoice_date IS NOT NULL
GROUP BY
    DATE_TRUNC('month', i.invoice_date),
    CONCAT(c.first_name, ' ', c.last_name),
    c.email,
    c.city,
    c.segment
ORDER BY
    invoice_month ASC