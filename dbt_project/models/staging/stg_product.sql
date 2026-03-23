
{{ config(materialized='view') }}

SELECT
  {{ replace_null('PRODUCT_ID', 'TEXT') }} AS PRODUCT_ID,
  {{ replace_null('PRODUCT_NAME', 'TEXT') }} AS PRODUCT_NAME,
  {{ replace_null('CATEGORY', 'TEXT') }} AS CATEGORY,
  {{ replace_null('SUB_CATEGORY', 'TEXT') }} AS SUB_CATEGORY,
  {{ replace_null('UNIT_PRICE', 'NUMBER') }} AS UNIT_PRICE,
  {{ replace_null('UNIT_COST', 'NUMBER') }} AS UNIT_COST,
  {{ replace_null('SKU', 'TEXT') }} AS SKU,
  {{ replace_null('IS_ACTIVE', 'NUMBER') }} AS IS_ACTIVE
FROM {{ source('raw','PRODUCT') }}
