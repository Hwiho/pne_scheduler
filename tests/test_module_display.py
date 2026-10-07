from pne_scheduler.ir.cell_profile import CellProfile
from pne_scheduler.ir.project import ModuleNode
from pne_scheduler.report.summary import module_headline


CELL = CellProfile(80, 4.2, 2.5)


def test_basic_box_summary_reports_the_values_used_by_its_step():
    node = ModuleNode("charge", "primitive", {"kind": "cc_charge", "c_rate": 0.5})
    first = module_headline(node, CELL)
    assert "40 mA" in first and "4.200 V" in first
    node.params["c_rate"] = 1.5
    assert "120 mA" in module_headline(node, CELL)
    assert first != module_headline(node, CELL)


def test_rest_summary_reports_time_and_repetition_without_duplicate_title():
    text = module_headline(ModuleNode("rest", "primitive", {
        "kind": "rest", "duration_s": 300, "repeat_count": 3,
    }), CELL)
    assert "5분" in text and "3회 반복" in text
    assert "휴지 (Rest)" not in text


def test_group_summary_retains_distinct_basic_step_conditions():
    children = [
        ModuleNode("charge", "primitive", {"kind": "cc_charge", "c_rate": 1}).to_dict(),
        ModuleNode("rest", "primitive", {"kind": "rest", "duration_s": 60}).to_dict(),
    ]
    text = module_headline(ModuleNode("group", "sequence", {
        "children": children, "repeat_count": 2,
    }), CELL)
    assert "80 mA" in text and "1분" in text and "전체 2회" in text
