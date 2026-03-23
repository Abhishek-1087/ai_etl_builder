import subprocess
import re
import os
from agent.auto_heal_agent import fix_sql


MAX_RETRIES = 3


def parse_dbt_failures(log_output):
    """
    Parse dbt run/compile output and extract failed models with their errors.
    Handles both runtime errors and compilation errors.
    """

    failures = []
    lines = log_output.split("\n")

    current_model = None
    error_lines = []

    for i, line in enumerate(lines):

        # Runtime failure: "Failure in model mart_xxx"
        fail_match = re.search(
            r"(Failure|Error)\s+in\s+model\s+(\w+)", line, re.IGNORECASE
        )
        if fail_match:
            if current_model and error_lines:
                failures.append({
                    "model": current_model,
                    "error": "\n".join(error_lines).strip()
                })
            current_model = fail_match.group(2)
            error_lines = []
            continue

        # Compilation error: "Model 'model.dbt_project.mart_xxx'"
        compile_match = re.search(
            r"Model '(?:model\.\w+\.)?(\w+)'", line
        )
        if compile_match and any(
            kw in log_output[max(0, log_output.find(line)-200):log_output.find(line)+200]
            for kw in ("Compilation Error", "depends on", "was not found", "Error")
        ):
            if current_model and error_lines:
                failures.append({
                    "model": current_model,
                    "error": "\n".join(error_lines).strip()
                })
            current_model = compile_match.group(1)
            error_lines = []
            continue

        # Also catch: "model.dbt_project.mart_xxx ... ERROR"
        model_error_match = re.search(r"model\.\w+\.(\w+).*ERROR", line)
        if model_error_match:
            current_model = model_error_match.group(1)
            error_lines = []
            continue

        if current_model and line.strip():
            error_lines.append(line.strip())

    # Capture last failure
    if current_model and error_lines:
        failures.append({
            "model": current_model,
            "error": "\n".join(error_lines).strip()
        })

    return failures


def find_model_file(model_name):
    """Search dbt_project/models for the SQL file of a given model."""

    for root, dirs, files in os.walk("dbt_project/models"):
        for fname in files:
            if fname == f"{model_name}.sql":
                return os.path.join(root, fname)

    return None


def run_dbt_with_healing():
    """
    Run dbt. On failure, extract broken models, ask LLM to fix them,
    overwrite the files, and retry - up to MAX_RETRIES times.
    Returns (success: bool, run_log: str)
    """

    full_log = []

    for attempt in range(1, MAX_RETRIES + 1):

        print(f"\nDBT run attempt {attempt}/{MAX_RETRIES}...\n")

        process = subprocess.Popen(
            ["dbt", "run"],
            cwd="dbt_project",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        output_lines = []
        for line in process.stdout:
            print(line, end="")
            output_lines.append(line)

        process.wait()
        run_output = "".join(output_lines)
        full_log.append(run_output)

        if process.returncode == 0:
            print("\nDBT run completed successfully\n")
            return True, "\n".join(full_log)

        # --- SELF-HEALING ---
        print(f"\nDBT failed on attempt {attempt}. Attempting self-heal...\n")

        failures = parse_dbt_failures(run_output)

        if not failures:
            # Could not parse specific failures - fall back to full log scan
            print("Could not identify specific failed models. Aborting heal.")
            break

        healed_any = False

        for failure in failures:
            model_name = failure["model"]
            error_msg = failure["error"]

            model_file = find_model_file(model_name)

            if not model_file:
                print(f"  Could not locate file for model: {model_name}")
                continue

            with open(model_file, "r") as f:
                broken_sql = f.read()

            print(f"  Healing model: {model_name}")
            print(f"  Error: {error_msg[:200]}")

            fixed = fix_sql(error_msg, broken_sql)

            with open(model_file, "w") as f:
                f.write(fixed)

            print(f"  Rewritten: {model_file}")
            healed_any = True

        if not healed_any:
            print("No models could be healed. Stopping retries.")
            break

    print("\nDBT run failed after all retries.\n")
    return False, "\n".join(full_log)
