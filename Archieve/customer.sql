SELECT 
  {{ replace_null('CUSTOMER_ID', 'NUMBER') }} AS CUSTOMER_ID,
  {{ replace_null('FIRST_NAME', 'TEXT') }} AS FIRST_NAME,
  {{ replace_null('LAST_NAME', 'TEXT') }} AS LAST_NAME,
  {{ replace_null('CITY', 'TEXT') }} AS CITY,
  {{ replace_null('EMAIL', 'TEXT') }} AS EMAIL,
  {{ replace_null('SIGNUP_DATE', 'DATE') }} AS SIGNUP_DATE
FROM {{ source('raw', 'CUSTOMER') }}