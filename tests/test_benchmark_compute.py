from em_workbench.benchmark_compute import run_benchmarks


def test_benchmark_script_emits_machine_and_workload_records() -> None:
    report = run_benchmarks(backends=["scalar"], warm_runs=1, include_refined=False)

    assert report["machine"]["cpu"]["logical_processors"] >= 1
    names = {record["name"] for record in report["records"]}
    assert "field-preview-25" in names
    assert "field-preview-400" in names
    assert "trajectory-preview-100" in names
    assert "trajectory-preview-400" in names
