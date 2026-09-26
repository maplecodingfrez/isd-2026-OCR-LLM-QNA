import md_plan_slots as mps

HEAD = ("ปีที่ 2 ภาคการศึกษาที่ 2\n\n<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต</td></tr>"
        "<tr><td>06016405</td><td>พื้นฐานความมั่นคงปลอดภัยไซเบอร์</td><td>3(3-0-6)</td></tr>"
        "<tr><td>06016410</td><td>วิศวกรรมซอฟต์แวร์</td><td>3(3-0-6)</td></tr>"
        "<tr><td>06016412</td><td>โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ</td><td>3(2-2-5)</td></tr>"
        "<tr><td>06066302</td><td>การเขียนโปรแกรมเว็บพื้นฐาน</td><td>3(2-2-5)</td></tr>"
        "<tr><td rowspan=\"3\">06016414, 06016415</td><td>กลุ่มวิชาด้านการพัฒนาซอฟต์แวร์ "
        "ระบบฐานข้อมูลแบบโนเอสคิวแอล การเขียนโปรแกรมเชิงฟังก์ชัน</td><td rowspan=\"3\">3(2-2-5)</td></tr>"
        "<tr><td>กลุ่มวิชาด้านโครงสร้างพื้นฐานเทคโนโลยีสารสนเทศ โครงสร้างพื้นฐานเครือข่ายการสื่อสาร</td></tr>")
TAIL = ("<tr><td rowspan=\"2\">06016424, 06016425</td><td>กลุ่มวิชาด้านสื่อประสม การออกแบบส่วนต่อประสานกับมนุษย์ "
        "พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์</td><td rowspan=\"2\">3(3-0-6)</td></tr>"
        "<tr><td colspan=\"2\">รวม</td><td>18</td></tr></table>")
NAMES = {(2, 2): {"06016419": "โครงสร้างพื้นฐานเครือข่ายการสื่อสาร",
                  "06016420": "ระบบโครงสร้างพื้นฐานและการบริการ"}}


def _group_codes(md):
    slots, _ = mps.derive_slots(md, NAMES)
    group = next(s for s in slots if s["kind"] == "choose_group")
    return [g["codes"] for g in group["groups"]]


# Break caught (IT no_coop OCR rerun 2026-09-26): the second member's name sits on the next row, not in the
# "กลุ่มวิชาด้าน…" cell (no rowspan) — 06016420 was left out of the group and counted as a normal course (+3).
def test_nocode_group_takes_member_names_from_following_rows():
    md = HEAD + "<tr><td>ระบบโครงสร้างพื้นฐานและการบริการ INFRASTRUCTURE SYSTEMS AND SERVICES</td></tr>" + TAIL
    assert ["06016419", "06016420"] in _group_codes(md)


# Break caught: extending the search swallowing a row that has its own code (it belongs to the next group/course).
def test_nocode_group_stops_at_the_next_coded_row():
    md = HEAD + TAIL.replace("การออกแบบส่วนต่อประสานกับมนุษย์", "การออกแบบส่วนต่อประสานกับมนุษย์ ระบบโครงสร้างพื้นฐานและการบริการ")
    assert ["06016419"] in _group_codes(md)
