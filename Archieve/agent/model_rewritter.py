def rewrite_model(file_path, new_sql):

    with open(file_path, "w") as f:
        f.write(new_sql)

    print(f"Model updated: {file_path}")