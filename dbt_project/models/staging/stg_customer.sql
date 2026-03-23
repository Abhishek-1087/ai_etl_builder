
{{ config(materialized='view') }}

SELECT
  {{ replace_null('CUSTOMER_ID', 'TEXT') }} AS CUSTOMER_ID,
  {{ replace_null('FIRST_NAME', 'TEXT') }} AS FIRST_NAME,
  {{ replace_null('LAST_NAME', 'TEXT') }} AS LAST_NAME,
  {{ replace_null('EMAIL', 'TEXT') }} AS EMAIL,
  {{ replace_null('PHONE', 'TEXT') }} AS PHONE,
  {{ replace_null('CITY', 'TEXT') }} AS CITY,
  {{ replace_null('STATE', 'TEXT') }} AS STATE,
  {{ replace_null('COUNTRY', 'TEXT') }} AS COUNTRY,
  {{ replace_null('SEGMENT', 'TEXT') }} AS SEGMENT,
  {{ replace_null('SIGNUP_DATE', 'DATE') }} AS SIGNUP_DATE,
  {{ replace_null('IS_ACTIVE', 'NUMBER') }} AS IS_ACTIVE
FROM {{ source('raw','CUSTOMER') }}
