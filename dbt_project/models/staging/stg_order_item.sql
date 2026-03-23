
{{ config(materialized='view') }}

SELECT
  {{ replace_null('ORDER_ITEM_ID', 'TEXT') }} AS ORDER_ITEM_ID,
  {{ replace_null('ORDER_ID', 'TEXT') }} AS ORDER_ID,
  {{ replace_null('PRODUCT_ID', 'TEXT') }} AS PRODUCT_ID,
  {{ replace_null('QUANTITY', 'NUMBER') }} AS QUANTITY,
  {{ replace_null('UNIT_PRICE', 'NUMBER') }} AS UNIT_PRICE,
  {{ replace_null('DISCOUNT_PCT', 'NUMBER') }} AS DISCOUNT_PCT,
  {{ replace_null('LINE_TOTAL', 'NUMBER') }} AS LINE_TOTAL
FROM {{ source('raw','ORDER_ITEM') }}
