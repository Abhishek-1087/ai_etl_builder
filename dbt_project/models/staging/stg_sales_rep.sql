
{{ config(materialized='view') }}

SELECT
  {{ replace_null('REP_ID', 'TEXT') }} AS REP_ID,
  {{ replace_null('FIRST_NAME', 'TEXT') }} AS FIRST_NAME,
  {{ replace_null('LAST_NAME', 'TEXT') }} AS LAST_NAME,
  {{ replace_null('EMAIL', 'TEXT') }} AS EMAIL,
  {{ replace_null('REGION', 'TEXT') }} AS REGION,
  {{ replace_null('HIRE_DATE', 'DATE') }} AS HIRE_DATE,
  {{ replace_null('QUOTA_INR', 'NUMBER') }} AS QUOTA_INR
FROM {{ source('raw','SALES_REP') }}
