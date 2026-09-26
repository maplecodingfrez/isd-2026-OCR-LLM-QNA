import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Lab9_evaluation"))
import run_gold_v2  # noqa: E402


def test_frozen_files_pass():
    assert all(run_gold_v2.frozen_ok(p) for p in run_gold_v2.PLANS)


# Break caught: running an edited (unfrozen) question file and reporting it as the locked set.
def test_edited_file_is_refused(tmp_path):
    for f in run_gold_v2.V2.glob("ait_*"):
        shutil.copy(f, tmp_path / f.name)
    q = tmp_path / "ait_gold_questions_v2.json"
    q.write_bytes(q.read_bytes().replace("หน่วยกิต".encode(), "หน่วยกิตต".encode(), 1))
    assert not run_gold_v2.frozen_ok("ait", tmp_path)


# Break caught: v2 results overwriting the v1 eval_result.json.
def test_command_writes_v2_result_next_to_the_plan_db():
    cmd = run_gold_v2.eval_command("it_coop")
    assert cmd[cmd.index("-o") + 1].endswith("eval_result_v2.json")
    assert cmd[cmd.index("-d") + 1].replace("\\", "/").endswith("IT/coop/lab8b_output/curriculum.db")
    assert cmd[cmd.index("-q") + 1].endswith("it_coop_gold_questions_v2.json")
