# import subprocess


# def run_dbt():

#     print("Running dbt models...\n")

#     result = subprocess.run(
#         ["dbt", "run"],
#         cwd="dbt_project",
#         capture_output=True,
#         text=True
#     )

#     print(result.stdout)

#     if result.returncode != 0:
#         print(result.stderr)

# import subprocess


# def run_dbt():

#     result = subprocess.run(
#         ["dbt", "run"],
#         capture_output=True,
#         text=True
#     )

#     if result.returncode != 0:

#         return {
#             "success": False,
#             "error": result.stderr
#         }

#     return {
#         "success": True,
#         "output": result.stdout
#     }




import subprocess


def run_dbt():

    print("\nStarting DBT run...\n")

    process = subprocess.Popen(
        ["dbt", "run"],
        cwd="dbt_project",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # stream logs live
    for line in process.stdout:
        print(line, end="")

    process.wait()

    if process.returncode == 0:
        print("\nDBT run completed successfully\n")
        return True
    else:
        print("\nDBT run failed\n")
        return False