"""Print aggregate source-run progress without document text or credentials."""
import subprocess

APP_UUID = "svv47uqopqo1dstuws1sqysq"
SQL = """
SELECT r.run_id, r.status, r.cursor, r.max_scan, r.sample_size,
       (SELECT count(*) FROM jobs j WHERE j.run_id=r.run_id) AS jobs,
       (SELECT count(*) FROM labels l WHERE l.run_id=r.run_id) AS labels
FROM run_controls r WHERE r.run_id LIKE '20261002-%'
ORDER BY r.run_id;
"""


def main():
    names = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True).splitlines()
    postgres = [name for name in names if name.startswith(f"postgres-{APP_UUID}-")]
    if len(postgres) != 1:
        raise SystemExit(f"expected one PostgreSQL container; found {len(postgres)}")
    print("run_id|status|scanned|max_scan|quota|jobs|labels", flush=True)
    subprocess.run(["docker", "exec", postgres[0], "psql", "-U", "quality", "-d", "quality",
                    "-At", "-c", SQL], check=True)


if __name__ == "__main__":
    main()
