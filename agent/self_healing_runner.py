import subprocess
import re
import os
from agent.auto_heal_agent import fix_sql


MAX_RETRIES = 3

def parse_dbt_failures(log_output):
    """
    Parse dbt output for both runtime errors and compilation errors.
    Returns list of {"model": name, "error": message}
    """
    failures = []
    lines    = log_output.split("\n")

    for i, line in enumerate(lines):

        # Compilation error format:
        # "Model 'model.dbt_project.mart_xxx' ..."
        compile_match = re.search(
            r"Model 'model\.\w+\.(\w+)'", line
        )
        if compile_match:
            model_name = compile_match.group(1)
            # Collect the next few lines as the error message
            error_lines = []
            for j in range(i, min(i + 8, len(lines))):
                stripped = lines[j].strip()
                if stripped:
                    error_lines.append(stripped)
            failures.append({
                "model": model_name,
                "error": "\n".join(error_lines)
            })
            continue

        # Runtime failure format:
        # "Failure in model mart_xxx" or "ERROR in model mart_xxx"
        runtime_match = re.search(
            r"(?:Failure|Error)\s+in\s+model\s+(\w+)", line, re.IGNORECASE
        )
        if runtime_match:
            model_name  = runtime_match.group(1)
            error_lines = []
            for j in range(i + 1, min(i + 10, len(lines))):
                stripped = lines[j].strip()
                if stripped:
                    error_lines.append(stripped)
                else:
                    break
            failures.append({
                "model": model_name,
                "error": "\n".join(error_lines)
            })
            continue

        # dbt node error format:
        # "model.dbt_project.mart_xxx  ERROR"
        node_match = re.search(r"model\.\w+\.(\w+)\s+ERROR", line)
        if node_match:
            model_name = node_match.group(1)
            if not any(f["model"] == model_name for f in failures):
                failures.append({
                    "model": model_name,
                    "error": line.strip()
                })

    # Deduplicate by model name, keeping first occurrence
    seen     = set()
    deduped  = []
    for f in failures:
        if f["model"] not in seen:
            seen.add(f["model"])
            deduped.append(f)

    return deduped


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
