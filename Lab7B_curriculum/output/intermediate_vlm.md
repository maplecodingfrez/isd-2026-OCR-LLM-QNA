\documentclass[12pt,a4paper]{article}
usepackage{amsmath,amsfonts,graphicx,latexsym,color}
usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;&lt;
usepackage{tikz-cd} % &lt;&lt;&lt;&lt;&lt;&lt;
usetikzlibrary {positioning}

% หัวเรื่อง
\begin{document}

% 3.1.4.2 แผนการศึกษาที่เข้าโครงการสหกิจศึกษา

มคอ. 2

ปีที่ 1 ภาคการศึกษาที่ 1

<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)</td></tr><tr><td>06026200</td><td>แคลคูลัส 1<br/>CALCULUS 1</td><td>3 (3-0-6)</td></tr><tr><td>06026202</td><td>พีชคณิตเชิงเส้น<br/>LINEAR ALGEBRA</td><td>3 (3-0-6)</td></tr><tr><td>06066101</td><td>พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ<br/>BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY</td><td>3 (3-0-6)</td></tr><tr><td>06066303</td><td>การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์<br/>PROBLEM SOLVING AND COMPUTER PROGRAMMING</td><td>3 (2-2-5)</td></tr><tr><td>90641001</td><td>โรงเรียนสร้างเสน่ห์<br/>CHARM SCHOOL</td><td>2 (1-2-3)</td></tr><tr><td>90641003</td><td>กีฬาและนันทนาการ<br/>SPORTS AND RECREATIONAL ACTIVITIES</td><td>1 (0-3-2)</td></tr><tr><td>90644007</td><td>ภาษาอังกฤษพื้นฐาน 1<br/>FOUNDATION ENGLISH 1</td><td>3 (3-0-6)</td></tr><tr><td colspan="2">รวม</td><td>18</td></tr></table>

วท.บ (วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ) สาขาวิชาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ
คณะเทคโนโลยีสารสนเทศ สจล.

---

\documentclass[12pt,a4paper]{article}
usepackage{amsmath,amsfonts,graphicx,latexsym,color}
usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;
usepackage{tikz-cd} % &lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
usepackage{tikz-cd}
\usetikzlibrary {positioning,shapes,arrows,decorations.pathreplacing}

%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&

---

\documentclass[12pt,a4paper]{article}
usepackage{amsmath,amsfonts,graphicx}
usepackage{tikz}%&lt;&lt;&lt;&lt;
usepackage{color}
%&lt;&lt;&lt;&lt; ตั้งค่าสี
\usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usepackage{tikz}%&lt;&lt;&lt;&lt;
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt},
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\begin{document}
    
    \pagestyle{article}
    \usepackage[utf8]{inputenc}
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
    myanglemark/.append style={
        angle radius = 3mm,
        inner sep = -0.5cm,
        outer sep = 0.8cm,
        text width = 4em,
        align = center
      },
}

\end{document}
    
\begin{table}[t] 
    \caption{ปีที่ 2 ภาคการศึกษาที่ 1 มคอ. 2} 
    \label{tab:1} 
    \usepackage[utf8]{inputenc} 
    \usepackage{amsmath,amsfonts,graphicx}
    \usetikzlibrary {positioning}

\tikzset{
    &gt;={Latex[width=1pt,length=2pt],
   

---

\documentclass[12pt,a4paper]{article}
\usepackage{amsmath,amsfonts,graphicx,latexsym,color}
\usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;
\tikzset{
    % TikZ code for the table header
    \tableheader[above right] = {รหัสวิชา}{ชื่อวิชา}{}{(บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)}{หน่วยกิต}
}

\begin{document}

<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)</td></tr><tr><td>06026204</td><td>เครือข่ายและความมั่นคงทางไซเบอร์เบื้องต้น<br/>INTRODUCTION TO NETWORKS AND CYBERSECURITY</td><td>3 (3-0-6)</td></tr><tr><td>06026207</td><td>ระบบฐานข้อมูลแบบโนเอสคิวแอล<br/>NOSQL DATABASE SYSTEMS</td><td>3 (2-2-5)</td></tr><tr><td>06026208</td><td>พื้นฐานวิทยาการข้อมูล<br/>FUNDAMENTALS OF DATA SCIENCE</td><td>3 (3-0-6)</td></tr><tr><td>06026209</td><td>การแสดงข้อมูลด้วยแผนภาพ<br/>DATA VISUALIZATION</td><td>3 (2-2-5)</td></tr><tr><td>06026210</td><td>การหาค่าที่เหมาะที่สุด<br/>OPTIMIZATION</td><td>3 (3-0-6)</td></tr><tr><td>06066102</td><td>ระบบสารสนเทศเพื่อการจัดการ<br/>MANAGEMENT INFORMATION SYSTEMS</td><td>3 (3-0-6)</td></tr><tr><td>06066301</td><td>โครงสร้างข้อมูลและอัลกอริทึม<br/>DATA STRUCTURES AND ALGORITHMS</td><td>3 (2-2-5)</td></tr><tr><td colspan="2">รวม</td><td>21</td></tr></table>

วท.บ (วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ) สาขาวิชาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ
คณะเทคโนโลยีสารสนเทศ สจล.

\end{document}

---

\documentclass[120mm]{a4paper}
\usepackage{amsmath,amsfonts,graphicx,latexsym,color}
\usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;
% &lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;
\usepackage{tikz-cd}
%&lt;&lt;&lt>&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt

---

\documentclass[12pt,a4paper]{article}
usepackage{amsmath,amsfonts,graphicx}

\usepackage{tikz}%&lt;&lt;&lt;&lt;&lt;&lt;
\usetikzlibrary {positioning}

% ตั้งค่าสีสำหรับ TikZ
\begin{document}
    \begin{tikzpicture}[scale=.8]
        % ตารางเรียงรายวิชาและหน่วยกิต
        \draw (10,25)rectangle(63.75,40);
        \foreach\x[count=\i] in {06026213,BIG DATA SYSTEMS,3 (2-2-5),06026214,PROJECT IN DATA SCIENCE AND BUSINESS ANALYTICS 1,3 (0-9-0),06026xxx,วิชาเลือกกลุ่มวิทยาการข้อมูล 3,ELECTIVE IN DATA SCIENCE 3,หรือ,3 (3-0-6),วิชาเลือกกลุ่มการวิเคราะห์เชิงสถิติ 3,ELECTIVE IN STATISTICAL ANALYTICS 3,3 (2-2-5),ELECTIVE IN DATA ENGINEERING 3,06026xxx,วิชาเลือกกลุ่มวิทยาการข้อมูล 4,ELECTIVE IN DATA SCIENCE 4,หรือ,3 (3-0-6),วิชาเลือกกลุ่มการวิเคราะห์เชิงสถิติ 4,ELECTIVE IN STATISTICAL ANALYTICS 4,3 (2-2-5),ELECTIVE IN DATA ENGINEERING 4,06066100,การบริหารโครงการเทคโนโลยีสารสนเทศ INFORMATION TECHNOLOGY PROJECT MANAGEMENT,3 (3-0-6),90643021,กลุ่มวิชาที่กำหนดโดยคณะ* ผู้ประกอบการสมัยใหม่ MODERN ENTREPRENEURS,3 (3-0-6)}{%
            \draw (\i-1,25)rectangle(64.75,40);
        }
    \end{tikzpicture}
% ตารางเรียงรายวิชาและหน่วยกิต
<table><tr><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>หน่วยกิต (บรรยาย-ปฏิบัติ-ศึกษาด้วยตนเอง)</td></tr><tr><td>06026213</td><td>ระบบข้อมูลมหัต BIG DATA SYSTEMS</td><td>3 (2-2-5)</td></tr><tr><td>06026214</td><td>โครงงานวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ 1 PROJECT IN DATA SCIENCE AND BUSINESS ANALYTICS 1</td><td>3 (0-9-0)</td></tr><tr><td rowspan="4">06026xxx</td><td>วิชาเลือกกลุ่มวิทยาการข้อมูล 3 ELECTIVE IN DATA SCIENCE 3</td><td>3 (3-0-6)</td></tr><tr><td>วิชาเลือกกลุ่มการวิเคราะห์เชิงสถิติ 3 ELECTIVE IN STATISTICAL ANALYTICS 3</td><td>หรือ 3 (2-2-5)</td></tr><tr><td>วิชาเลือกกลุ่มวิศวกรรมข้อมูล 3 ELECTIVE IN DATA ENGINEERING 3</td><td></td></tr><tr><td>06026xxx</td><td>วิชาเลือกกลุ่มวิทยาการข้อมูล 4 ELECTIVE IN DATA SCIENCE 4</td><td>3 (3-0-6)</td></tr><tr><td rowspan="2"></td><td>วิชาเลือกกลุ่มการวิเคราะห์เชิงสถิติ 4 ELECTIVE IN STATISTICAL ANALYTICS 4</td><td>หรือ 3 (2-2-5)</td></tr><tr><td>วิชาเลือกกลุ่มวิศวกรรมข้อมูล 4 ELECTIVE IN DATA ENGINEERING 4</td><td></td></tr><tr><td rowspan="1">06066100</td><td>การบริหารโครงการเทคโนโลยีสารสนเทศ INFORMATION TECHNOLOGY PROJECT MANAGEMENT</td><td>3 (3-0-6)</td></tr><tr><td colspan="2"></td><td></td></tr><tr><td rowspan="1">90643021</td><td>กลุ่มวิชาที่กำหนดโดยคณะ* ผู้ประกอบการสมัยใหม่ MODERN ENTREPRENEURS</td><td>3 (3-0-6)</td></tr><tr><td colspan="2"></td><td></td></tr><tr><td colspan="1">รวม</td><td></td><td>18</td></tr></table}
วท.บ (วิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ) สาขาวิชาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ
คณะเทคโนโลยีสารสนเทศ สจล.
มคอ. 2

---

Extract all text from the image.

Instructions:
- Only return the clean Markdown.
- Do not include any explanation or extra text.
- You must include all information on the page.

Formatting Rules:
- Tables: Render tables using <table>...</table> in clean HTML format.
- Equations: Render equations using LaTeX syntax with inline ($...$) and block ($$...$$).
- Images/Charts/Diagrams: Wrap any clearly defined visual areas (e.g. charts, diagrams, pictures) in:

<figure>
Describe the image’s main elements (people, objects, text), note any contextual clues (place, event, culture), mention visible text and its meaning, provide deeper analysis when relevant (especially for financial charts, graphs, or documents), comment on style or architecture if relevant, then give a concise overall summary. Describe in Thai.
</figure>


- Page Numbers: Wrap page numbers in <page_number>...</page_number> (e.g., <page_number>14</page_number>).
- Checkboxes: Use ☐ for unchecked and ☑ for checked boxes.
