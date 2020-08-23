def write_code_files(code_files):
    for file_name, code in code_files.items():
        with open(file_name, "w") as f:
            f.write(code)
            if not code.endswith("\n"):
                f.write("\n")
