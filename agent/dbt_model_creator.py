# import os


# import os
# import re


# def clean_sql(sql):

#     # remove create table if LLM generates it
#     sql = re.sub(r"CREATE\s+OR\s+REPLACE\s+TABLE.*?AS", "", sql, flags=re.IGNORECASE)
#     sql = re.sub(r"CREATE\s+TABLE.*?AS", "", sql, flags=re.IGNORECASE)

#     return sql.strip()


# def save_models(models):

#     directory = "dbt_project/models/mart"

#     os.makedirs(directory, exist_ok=True)

#     for model in models:

#         name = model["name"]
#         sql = clean_sql(model["sql"])

#         path = os.path.join(directory, f"{name}.sql")

#         with open(path, "w", encoding="utf-8") as f:
#             f.write(sql)

#         print(f"Model saved: {name}")




import os


def create_models(models):

    created = []

    for model in models:

        layer = model["layer"]
        name = model["name"]
        sql = model["sql"]

        if layer == "staging":
            folder = "dbt_project/models/staging"
        elif layer == "mart":
            folder = "dbt_project/models/mart"
        else:
            folder = "dbt_project/models/generated"

        os.makedirs(folder, exist_ok=True)

        file_path = os.path.join(folder, f"{name}.sql")

        with open(file_path, "w") as f:
            f.write(sql)

        created.append(file_path)

        print(f"Created {file_path}")

    return created