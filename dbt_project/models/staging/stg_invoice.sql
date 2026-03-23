
{{ config(materialized='view') }}

SELECT
  {{ replace_null('INVOICE_ID', 'TEXT') }} AS INVOICE_ID,
  {{ replace_null('ORDER_ID', 'TEXT') }} AS ORDER_ID,
  {{ replace_null('CUSTOMER_ID', 'TEXT') }} AS CUSTOMER_ID,
  {{ replace_null('INVOICE_DATE', 'DATE') }} AS INVOICE_DATE,
  {{ replace_null('DUE_DATE', 'DATE') }} AS DUE_DATE,
  {{ replace_null('SUBTOTAL_INR', 'NUMBER') }} AS SUBTOTAL_INR,
  {{ replace_null('TAX_PCT', 'NUMBER') }} AS TAX_PCT,
  {{ replace_null('TAX_AMOUNT_INR', 'NUMBER') }} AS TAX_AMOUNT_INR,
  {{ replace_null('TOTAL_INR', 'NUMBER') }} AS TOTAL_INR,
  {{ replace_null('IS_PAID', 'NUMBER') }} AS IS_PAID,
  {{ replace_null('PAYMENT_DATE', 'DATE') }} AS PAYMENT_DATE
FROM {{ source('raw','INVOICE') }}
