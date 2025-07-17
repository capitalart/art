import os

ROOT_DIR = os.getcwd()
OUTPUT_FILE = os.path.join(ROOT_DIR, "QA_MASTER.md")
HEADER_LINE = "\n" + "=" * 80 + "\n"

def find_qa_reports(base_dir):
    """Recursively find all QA_REPORT.md files."""
    qa_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "QA_REPORT.md":
                qa_files.append(os.path.join(root, file))
    return sorted(qa_files)

def create_index(entries):
    """Generate markdown index for all QA_REPORTs."""
    index = ["## 📑 Index of QA Reports\n"]
    for entry in entries:
        rel_path = os.path.relpath(entry, ROOT_DIR)
        anchor = rel_path.replace('/', '-').replace('_', '-').replace(' ', '-').lower()
        index.append(f"- [{rel_path}](#{anchor})")
    return "\n".join(index)

def combine_reports(qa_paths, output_file):
    """Combine all QA reports into a master report."""
    with open(output_file, "w", encoding="utf-8") as master:
        master.write("# ✅ QA Master Report\n")
        master.write("This file automatically aggregates all QA_REPORT.md files.\n")
        master.write(HEADER_LINE)
        
        # Write index
        master.write(create_index(qa_paths))
        master.write(HEADER_LINE)

        # Write each report section
        for path in qa_paths:
            rel_path = os.path.relpath(path, ROOT_DIR)
            anchor = rel_path.replace('/', '-').replace('_', '-').replace(' ', '-').lower()
            master.write(f"\n\n## 📂 `{rel_path}`\n")
            master.write(f"<a name=\"{anchor}\"></a>\n\n")

            with open(path, "r", encoding="utf-8") as qa_file:
                content = qa_file.read().strip()
                if content:
                    master.write(content)
                else:
                    master.write("_⚠️ This QA report is empty._")
            master.write(HEADER_LINE)

    print(f"✅ Combined {len(qa_paths)} QA reports into {output_file}")

if __name__ == "__main__":
    qa_files = find_qa_reports(ROOT_DIR)
    if qa_files:
        combine_reports(qa_files, OUTPUT_FILE)
    else:
        print("⚠️ No QA_REPORT.md files found.")
