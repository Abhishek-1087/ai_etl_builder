
{{ config(materialized='view') }}

SELECT
  {{ replace_null('ORDER_ID', 'TEXT') }} AS ORDER_ID,
  {{ replace_null('CUSTOMER_ID', 'TEXT') }} AS CUSTOMER_ID,
  {{ replace_null('REP_ID', 'TEXT') }} AS REP_ID,
  {{ replace_null('ORDER_DATE', 'DATE') }} AS ORDER_DATE,
  {{ replace_null('SHIP_DATE', 'DATE') }} AS SHIP_DATE,
  {{ replace_null('DELIVERY_DATE', 'DATE') }} AS DELIVERY_DATE,
  {{ replace_null('STATUS', 'TEXT') }} AS STATUS,
  {{ replace_null('CHANNEL', 'TEXT') }} AS CHANNEL,
  {{ replace_null('PAYMENT_METHOD', 'TEXT') }} AS PAYMENT_METHOD,
  {{ replace_null('DISCOUNT_PCT', 'NUMBER') }} AS DISCOUNT_PCT,
  {{ replace_null('NOTES', 'TEXT') }} AS NOTES
FROM {{ source('raw','ORDERS') }}
