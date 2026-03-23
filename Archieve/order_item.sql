SELECT 
  {{ replace_null('ORDER_ID', 'NUMBER') }} AS ORDER_ID,
  {{ replace_null('PRODUCT_ID', 'NUMBER') }} AS PRODUCT_ID,
  {{ replace_null('ORDER_ITEM_ID', 'NUMBER') }} AS ORDER_ITEM_ID,
  {{ replace_null('QUANTITY', 'NUMBER') }} AS QUANTITY,
  {{ replace_null('UNIT_PRICE', 'NUMBER') }} AS UNIT_PRICE
FROM 
  {{ source('raw', 'ORDER_ITEM') }}