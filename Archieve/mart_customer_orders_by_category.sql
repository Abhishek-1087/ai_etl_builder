SELECT 
    c.customer_id,
    oi.order_id,
    oi.product_id,
    COUNT(oi.quantity) AS total_items
FROM {{ ref('customer') }} c
JOIN {{ ref('order_detail') }} o 
    ON c.customer_id = o.customer_id
JOIN {{ ref('order_item') }} oi 
    ON oi.order_id = o.order_id
GROUP BY 
    c.customer_id,
    oi.product_id,
    oi.order_id