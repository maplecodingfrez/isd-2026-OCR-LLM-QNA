# 📖 พจนานุกรมตัวย่อรายวิชาและคำเรียกภาษาพูด (Curriculum Course Acronyms Dictionary)

> **เอกสารรวบรวมและวิเคราะห์ตัวย่อรายวิชาทั้งหมดจากฐานข้อมูล `data_input` และ มคอ.2 ใน `Lab7B_Lab8B_ocr_system`**  
> ครอบคลุมหลักสูตรระดับปริญญาตรี คณะเทคโนโลยีสารสนเทศ สจล. ครบทั้ง 4 สาขาวิชา: **IT, DSBA, BIT, AIT**

---

## 📌 1. บทวิเคราะห์และไขข้อข้องใจ: ทำไมพิมพ์ `isd` แล้วระบบเดิมไม่เจอ?

1. **ในเล่มหลักสูตรบันทึกเป็นชื่อเต็มทางการ:**
   - **สาขา IT และ DSBA:** รหัสวิชา `06066304` ชื่อไทยคือ `การวิเคราะห์และออกแบบระบบสารสนเทศ` และชื่ออังกฤษคือ `INFORMATION SYSTEM ANALYSIS AND DESIGN`
   - **สาขา BIT:** รหัสวิชา `06036121` ชื่อไทยคือ `การวิเคราะห์และออกแบบระบบสารสนเทศทางธุรกิจ` และชื่ออังกฤษคือ `BUSINESS INFORMATION SYSTEM ANALYSIS AND DESIGN`
   - ในเล่มไม่มีการเขียนตัวย่อ `ISD` ไว้ตรง ๆ แต่คำว่า **ISD** มาจากตัวอักษรย่อ **I**nformation **S**ystem Analysis and **D**esign (หรือ Information System Design)
2. **ระบบแมปตัวย่อ (`ACRONYM_MAP`) เดิมใส่ไว้แค่ `SAD`:**
   - ในไฟล์ `course_names.py` ดั้งเดิมมีเพียงตัวย่อ `SAD` (Systems Analysis and Design) ที่ชี้ไปยังวิชานี้
   - ยังไม่ได้ใส่คำว่า **`ISD`** หรือ **`ISAD`** ลงไป ทำให้คำค้นหานี้หลุดการดักจับของระบบแปลงตัวย่อ
3. **ระบบตัดคำและกฎป้องกันความผิดพลาด (Guardrails):**
   - คำว่า `isd` ยาว 3 ตัวอักษร ซึ่งสั้นเกินกว่าเกณฑ์ตัวค้นหาบางส่วน (ระบบต้องการ >= 5 ตัวอักษรเพื่อป้องกันการเดามั่ว)
   - ผลลัพธ์จึงถูกส่งไปให้โมเดล AI ค้นหาใน SQLite และเมื่อหาไม่เจอก็ตอบปฏิเสธตามกฎความปลอดภัยว่า *'ไม่พบข้อมูลนี้ในเล่มหลักสูตร'*

---

## 📋 2. ตารางพจนานุกรมตัวย่อแยกตามหมวดและสาขาวิชา

### 🏛️ หมวดวิชาแกนร่วมของคณะ (Core / Shared Courses - รหัส 0606) (10 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `06066000` | คณิตศาสตร์ไม่ต่อเนื่อง | DISCRETE MATHEMATICS | `3(3-0-6)` | `DM`, `Discrete` | ดิสครีต, ดิสครีตแมธ | IT, DSBA, AIT | Set theory, Logic, Graph theory |
| `06066001` | ความน่าจะเป็นและสถิติ | PROBABILITY AND STATISTICS | `3(3-0-6)` | `Prob Stat`, `Stat`, `PAS`, `PS` | สถิติ, พรอบสแตท, พรอบ | IT, DSBA, AIT | วิชาสถิติร่วมของคณะไอที |
| `06066100` | การบริหารโครงการเทคโนโลยีสารสนเทศ | INFORMATION TECHNOLOGY PROJECT MANAGEMENT | `3(3-0-6)` | `ITPM`, `PM` | ไอทีพีเอ็ม, โปรเจกต์แมเนจเมนต์ | IT, DSBA | การบริหารโครงการสารสนเทศ |
| `06066101` | พื้นฐานทางธุรกิจสำหรับเทคโนโลยีสารสนเทศ | BUSINESS FUNDAMENTALS FOR INFORMATION TECHNOLOGY | `3(3-0-6)` | `BFIT` | บีฟิต, บิสซิเนสฟันด์ | IT, DSBA | มีใน ACRONYM_MAP แล้ว วิชาบังคับก่อนของ MIS |
| `06066102` | ระบบสารสนเทศเพื่อการจัดการ | MANAGEMENT INFORMATION SYSTEMS | `3(3-0-6)` | `MIS` | เอ็มไอเอส, ระบบสารสนเทศจัดการ | IT, DSBA | มีใน ACRONYM_MAP แล้ว |
| `06066300` | แนวคิดระบบฐานข้อมูล | DATABASE SYSTEM CONCEPTS | `3(2-2-5)` | `DB`, `Database`, `DBSC` | ดีบี, ฐานข้อมูล, แนวคิดฐานข้อมูล | IT, DSBA, AIT | วิชาแกนหลักฐานข้อมูล ปลดล็อก Data Warehouse / NoSQL |
| `06066301` | โครงสร้างข้อมูลและอัลกอริทึม | DATA STRUCTURES AND ALGORITHMS | `3(2-2-5)` | `DSA`, `DS`, `Data Struc` | ดาต้าสตัค, อัลกอ, โครงสร้างข้อมูล | IT, DSBA, AIT | วิชาแกนสำคัญของสายคอมพิวเตอร์ |
| `06066302` | การเขียนโปรแกรมเว็บพื้นฐาน | FUNDAMENTAL WEB PROGRAMMING | `3(2-2-5)` | `FWP`, `Web 1`, `Web Prog` | เว็บ 1, เว็บพื้นฐาน, เขียนเว็บ | IT, DSBA | HTML, CSS, JavaScript, Frontend |
| `06066303` | การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์ | PROBLEM SOLVING AND COMPUTER PROGRAMMING | `3(2-2-5)` | `PSP`, `CP`, `Prog 1`, `Com Pro` | คอมโปร, โปรแกรมมิ่ง 1, การเขียนโปรแกรม | IT, DSBA, AIT | วิชาการเขียนโปรแกรมตัวแรกของเด็กไอที ปี 1 เทอม 1 |
| `06066304` | การวิเคราะห์และออกแบบระบบสารสนเทศ | INFORMATION SYSTEM ANALYSIS AND DESIGN | `3(3-0-6)` | `ISD`, `ISAD`, `SAD` | ไอเอสดี, ไอเอสเอดี, เอสเอดี, ซิสเต็มดีไซน์ | IT, DSBA | 🎯 วิชา ISD ที่ผู้ใช้ถามถึง! รหัส 06066304 ใน IT/DSBA |

### 🏛️ สาขาวิชาเทคโนโลยีสารสนเทศ (IT - รหัส 0601) (29 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `06016401` | คณิตศาสตร์สำหรับเทคโนโลยีสารสนเทศ | MATHEMATICS FOR INFORMATION TECHNOLOGY | `3(3-0-6)` | `MIT`, `Math IT`, `MFIT` | แมธ ไอที, คณิต ไอที | IT (Coop / Non-Coop) | วิชาคณิตศาสตร์ปี 1 เทอม 1 ของ IT |
| `06016402` | พื้นฐานทางด้านเทคโนโลยีสารสนเทศ | INFORMATION TECHNOLOGY FUNDAMENTALS | `3(2-2-5)` | `ITF`, `IT Fund` | ไอทีฟันด์, พื้นฐานไอที | IT (Coop / Non-Coop) | วิชาไอทีพื้นฐาน ปี 1 เทอม 1 |
| `06016403` | เทคโนโลยีสื่อประสม | MULTIMEDIA TECHNOLOGY | `3(2-2-5)` | `MMT`, `MT`, `Multi` | มัลติ, มัลติมีเดีย | IT (Coop / Non-Coop) | วิชากลุ่มสื่อประสม |
| `06016404` | เทคโนโลยีกลุ่มเมฆ | CLOUD COMPUTING | `3(2-2-5)` | `CC`, `Cloud` | คลาวด์, คลาวด์คอม | IT (Coop / Non-Coop) | มักเรียกสั้น ๆ ว่า Cloud |
| `06016405` | พื้นฐานความมั่นคงปลอดภัยไซเบอร์ | CYBERSECURITY FUNDAMENTALS | `3(3-0-6)` | `CF`, `Cyber`, `Sec` | ไซเบอร์, ซีเคียว | IT (Coop / Non-Coop) | วิชาความปลอดภัยไซเบอร์ |
| `06016406` | โครงงาน 1 | PROJECT 1 | `3(0-9-0)` | `Proj 1`, `PJ 1`, `P1` | โปรเจกต์ 1, โครงงาน 1, ซีเนียร์โปรเจกต์ 1 | IT (Coop / Non-Coop) | วิชาบังคับก่อนของ Project 2 |
| `06016407` | โครงงาน 2 | PROJECT 2 | `3(0-9-0)` | `Proj 2`, `PJ 2`, `P2` | โปรเจกต์ 2, โครงงาน 2, จบการศึกษา | IT (Coop / Non-Coop) | ต้องผ่าน Project 1 ก่อน |
| `06016408` | การสร้างโปรแกรมเชิงวัตถุ | OBJECT-ORIENTED PROGRAMMING | `3(2-2-5)` | `OOP` | โอโอพี, อ็อบเจกต์ | IT (Coop / Non-Coop) | มีใน ACRONYM_MAP แล้ว ตัวต่อสำคัญของ Server Web |
| `06016409` | การประมวลผลทางกายภาพ | PHYSICAL COMPUTING | `3(2-2-5)` | `PC`, `Phy Comp` | ฟิสิคัลคอม, ฟิสิคอล | IT (Coop / Non-Coop) | เกี่ยวกับฮาร์ดแวร์/เซนเซอร์/Arduino |
| `06016410` | วิศวกรรมซอฟต์แวร์ | SOFTWARE ENGINEERING | `3(3-0-6)` | `SE` | ซอฟต์แวร์เอน, เอสอี | IT (Coop / Non-Coop) | มีใน ACRONYM_MAP แล้ว |
| `06016411` | ระบบคอมพิวเตอร์เบื้องต้น | INTRODUCTION TO COMPUTER SYSTEMS | `3(2-2-5)` | `ICS`, `Intro Com`, `CS` | คอมซิส, อินโทรคอม | IT (Coop / Non-Coop) | ปี 1 เทอม 1 |
| `06016412` | โครงสร้างระบบคอมพิวเตอร์และระบบปฏิบัติการ | COMPUTER ORGANIZATION AND OPERATING SYSTEM | `3(2-2-5)` | `OS`, `Com Org`, `COOS`, `CO` | โอเอส, คอมออร์ก, ระบบปฏิบัติการ | IT (Coop / Non-Coop) | มี OS ใน ACRONYM_MAP แล้ว |
| `06016413` | ระบบเครือข่ายเบื้องต้น | INTRODUCTION TO NETWORK SYSTEMS | `3(3-0-6)` | `INS`, `Net 1`, `Intro Net`, `Network` | เน็ตเวิร์ก, เน็ต 1, อินโทรเน็ต | IT (Coop / Non-Coop) | วิชาบังคับก่อนของ CNI |
| `06016414` | ระบบฐานข้อมูลแบบโนเอสคิวแอล | NOSQL DATABASE SYSTEMS | `3(2-2-5)` | `NoSQL`, `NDS` | โนเอสคิวแอล, โนซีเควล | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Software |
| `06016415` | การเขียนโปรแกรมเชิงฟังก์ชัน | FUNCTIONAL PROGRAMMING | `3(2-2-5)` | `FP` | ฟังก์ชันนอล, เอฟพี | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Software |
| `06016416` | วิศวกรรมความต้องการ | REQUIREMENT ENGINEERING | `3(3-0-6)` | `RE` | รีไควร์เมนต์, อาร์อี | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Software |
| `06016417` | เครื่องมือและสภาพแวดล้อมสำหรับการพัฒนาซอฟต์แวร์ | SOFTWARE DEVELOPMENT TOOLS AND ENVIRONMENTS | `3(2-2-5)` | `DevTools`, `SDTE` | เดฟทูล, เครื่องมือเดฟ | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Software |
| `06016418` | การพัฒนาเว็บฝั่งเซิร์ฟเวอร์ | SERVER-SIDE WEB DEVELOPMENT | `3(2-2-5)` | `SSWD`, `Web 2`, `Backend` | เว็บ 2, เว็บเซิร์ฟเวอร์, แบ็กเอนด์ | IT (Coop / Non-Coop) | ต้องผ่าน 06016408 (OOP) ก่อน |
| `06016419` | โครงสร้างพื้นฐานเครือข่ายการสื่อสาร | COMMUNICATION NETWORK INFRASTRUCTURE | `3(2-2-5)` | `CNI`, `Net Infra` | เน็ตอินฟรา, เน็ต 2 | IT (Coop / Non-Coop) | ต้องผ่าน 06016413 (Net 1) ก่อน |
| `06016420` | ระบบโครงสร้างพื้นฐานและการบริการ | INFRASTRUCTURE SYSTEMS AND SERVICES | `3(2-2-5)` | `ISS` | ไอเอสเอส, อินฟราเซอร์วิส | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Network |
| `06016421` | ความมั่นคงปลอดภัยโครงสร้างพื้นฐานทางเทคโนโลยีสารสนเทศ | INFORMATION TECHNOLOGY INFRASTRUCTURE SECURITY | `3(3-0-6)` | `ITIS`, `Infra Sec` | อินฟราเซค, ซีเคียวอินฟรา | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Network |
| `06016422` | อินเทอร์เน็ตของสรรพสิ่ง | INTERNET OF THINGS | `3(2-2-5)` | `IoT` | ไอโอที, ไอโอทีเบื้องต้น | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Network |
| `06016423` | การออโตเมชั่นและโครงสร้างพื้นฐานที่สามารถโปรแกรมได้ | INFRASTRUCTURE PROGRAMMABILITY AND AUTOMATION | `3(2-2-5)` | `IPA`, `Net Auto` | เน็ตออโต้, ออโตเมชั่น | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Network |
| `06016424` | การออกแบบส่วนต่อประสานกับมนุษย์ | HUMAN INTERFACE DESIGN | `3(3-0-6)` | `HID`, `HCI`, `UI/UX`, `UX/UI` | ยูไอ, ยูเอ็กซ์, เอชซีไอ | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Multimedia/Interactive |
| `06016425` | พื้นฐานการออกแบบทัศนศิลป์สำหรับสื่อปฏิสัมพันธ์ | VISUAL DESIGN FUNDAMENTALS FOR INTERACTIVE MEDIA | `3(2-2-5)` | `VD`, `Visual Design` | วิชวลดีไซน์ | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Multimedia/Interactive |
| `06016426` | คอมพิวเตอร์กราฟิกส์และแอนิเมชัน | COMPUTER GRAPHICS AND ANIMATION | `3(2-2-5)` | `CG`, `CGA`, `Graphics` | คอมกราฟิก, ซีจี, แอนิเมชัน | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Multimedia/Interactive |
| `06016427` | การออกแบบและพัฒนาเกมเบื้องต้น | INTRODUCTION TO GAME DESIGN AND DEVELOPMENT | `3(2-2-5)` | `GD`, `Game Dev`, `Intro Game` | วิชาเกม, เกมดีไซน์, พัฒนาเกม | IT (Coop / Non-Coop) | วิชาเลือกกลุ่ม Multimedia/Interactive |
| `06016481` | สหกิจศึกษา | COOPERATIVE EDUCATION | `6(0-36-0)` | `Coop`, `CE` | สหกิจ, โคออป, ฝึกงานสหกิจ | IT (Coop) | แผนสหกิจศึกษา ปี 3 เทอม 2 |
| `06016482` | สหกิจศึกษาต่างประเทศ | OVERSEA COOPERATIVE EDUCATION | `6(0-36-0)` | `Overseas Coop`, `OCE` | สหกิจนอก, สหกิจต่างประเทศ | IT (Coop) | แผนสหกิจศึกษาต่างประเทศ |

### 🏛️ สาขาวิชาวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ (DSBA - รหัส 0602) (25 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `06026200` | แคลคูลัส 1 | CALCULUS 1 | `3(3-0-6)` | `Cal 1`, `CAL 1` | แคล 1, แคลคูลัส 1 | DSBA (Coop / Non-Coop) | วิชาบังคับก่อนของ แคลคูลัส 2 |
| `06026201` | แคลคูลัส 2 | CALCULUS 2 | `3(3-0-6)` | `Cal 2`, `CAL 2` | แคล 2, แคลคูลัส 2 | DSBA (Coop / Non-Coop) | ต้องผ่านแคลคูลัส 1 ก่อน |
| `06026202` | พีชคณิตเชิงเส้น | LINEAR ALGEBRA | `3(3-0-6)` | `LA`, `Linear` | ลิเนียร์, ลิเนียร์แอลจีบรา | DSBA (Coop / Non-Coop) | พื้นฐานสำคัญของ Machine Learning / Data Science |
| `06026203` | การโปรแกรมคอมพิวเตอร์ | COMPUTER PROGRAMMING | `3(2-2-5)` | `CP`, `Prog` | คอมโปร, โปรแกรมมิ่ง | DSBA (Coop / Non-Coop) | การเขียนโปรแกรมพื้นฐานภาษาไพทอน/อาร์ |
| `06026204` | เครือข่ายและความมั่นคงทางไซเบอร์เบื้องต้น | INTRODUCTION TO NETWORKS AND CYBERSECURITY | `3(3-0-6)` | `INC`, `Net Sec` | เน็ตเวิร์กไซเบอร์, เน็ตเซค | DSBA (Coop / Non-Coop) | วิชาเครือข่ายและความปลอดภัยของ DSBA |
| `06026205` | การตลาดเบื้องต้น | INTRODUCTION TO MARKETING | `3(3-0-6)` | `IM`, `MKT`, `Marketing` | มาร์เก็ตติ้ง, การตลาด | DSBA (Coop / Non-Coop) | วิชาพื้นฐานธุรกิจสำหรับ DSBA |
| `06026206` | การวิเคราะห์ข้อมูลและการโปรแกรม | DATA ANALYTICS AND PROGRAMMING | `3(2-2-5)` | `DAP`, `Data Analytics` | ดาต้าแอนาไลติกส์, ดาต้าโปรแกรม | DSBA (Coop / Non-Coop) | วิชาเฉพาะด้านการวิเคราะห์ข้อมูล |
| `06026207` | ระบบฐานข้อมูลแบบโนเอสคิวแอล | NOSQL DATABASE SYSTEMS | `3(2-2-5)` | `NoSQL` | โนเอสคิวแอล, โนซีเควล | DSBA (Coop / Non-Coop) | วิชาฐานข้อมูล NoSQL |
| `06026208` | พื้นฐานวิทยาการข้อมูล | FUNDAMENTALS OF DATA SCIENCE | `3(3-0-6)` | `FDS`, `Data Science`, `DS` | ดาต้าไซน์, พื้นฐานดาต้าไซน์ | DSBA (Coop / Non-Coop) | วิชาแกนหลักของสาขา DSBA |
| `06026209` | การแสดงข้อมูลด้วยแผนภาพ | DATA VISUALIZATION | `3(2-2-5)` | `DV`, `Data Viz`, `Viz` | ดาต้าวิด, ดาต้าวิชวลไลเซชัน, วิชวลไลซ์ | DSBA (Coop / Non-Coop) | เช่น Tableau / Power BI |
| `06026210` | การหาค่าที่เหมาะสมที่สุด | OPTIMIZATION | `3(3-0-6)` | `Opt`, `Optimization` | ออปติไมซ์, ออปติไมเซชัน | DSBA (Coop / Non-Coop) | การหาค่าเหมาะที่สุดเชิงคณิตศาสตร์ |
| `06026211` | การเรียนรู้ของเครื่องเชิงประยุกต์ | APPLIED MACHINE LEARNING | `3(2-2-5)` | `AML`, `ML` | แมชชีนเลิร์นนิง, เอเอ็มแอล, เอ็มแอล | DSBA (Coop / Non-Coop) | มีใน ACRONYM_MAP แล้ว |
| `06026212` | การสร้างคลังข้อมูล | DATA WAREHOUSING | `3(2-2-5)` | `DW`, `Data Warehouse` | คลังข้อมูล, ดาต้าแวร์เฮ้าส์ | DSBA (Coop / Non-Coop) | ต้องผ่าน 06066300 (แนวคิดระบบฐานข้อมูล) ก่อน |
| `06026213` | ระบบข้อมูลมหัต | BIG DATA SYSTEMS | `3(2-2-5)` | `BDS`, `Big Data` | บิ๊กดาต้า, ข้อมูลมหัต | DSBA (Coop / Non-Coop) | Hadoop, Spark, Distributed computing |
| `06026214` | โครงงานวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ 1 | PROJECT IN DATA SCIENCE AND BUSINESS ANALYTICS 1 | `3(0-9-0)` | `Proj DSBA 1`, `P-DSBA 1` | โปรเจกต์ 1 DSBA | DSBA (Coop / Non-Coop) | วิชาโครงงานจบการศึกษา |
| `06026215` | โครงงานวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ 2 | PROJECT IN DATA SCIENCE AND BUSINESS ANALYTICS 2 | `3(0-9-0)` | `Proj DSBA 2`, `P-DSBA 2` | โปรเจกต์ 2 DSBA | DSBA (Coop / Non-Coop) | วิชาโครงงานจบการศึกษา |
| `06026250` | วิทยาการข้อมูลสำหรับธุรกิจ | DATA SCIENCE FOR BUSINESS | `3(2-2-5)` | `DSB`, `DS for Biz` | ดาต้าไซน์ธุรกิจ | DSBA (Coop) | วิชาเลือก DSBA |
| `06026251` | บัญชีการเงิน | FINANCIAL ACCOUNTING | `3(3-0-6)` | `FA`, `Fin Acc` | บัญชีการเงิน, การบัญชี | DSBA (Coop) | วิชาเลือกสาย Business |
| `06026252` | การวิเคราะห์ด้านการเงิน | FINANCIAL ANALYTICS | `3(2-2-5)` | `FA`, `Fin Analytics` | การวิเคราะห์การเงิน | DSBA (Coop) | วิชาเลือกสาย Business |
| `06026253` | การวิเคราะห์ด้านการตลาด | MARKETING ANALYTICS | `3(2-2-5)` | `MA`, `Mkt Analytics` | มาร์เก็ตติ้งแอนาไลติกส์ | DSBA (Coop) | วิชาเลือกสาย Business |
| `06026254` | เทคโนโลยีสุขภาพสนเทศศาสตร์เบื้องต้น | INTRODUCTION TO HEALTH ANALYTICS | `3(2-2-5)` | `IHA`, `Health Analytics` | เฮลธ์แอนาไลติกส์ | DSBA (Coop) | วิชาเลือกสาย Health Data |
| `06026255` | การได้มาและการจัดการข้อมูลทางด้านคลินิก | CLINICAL DATA ACQUISITION AND MANAGEMENT | `3(2-2-5)` | `CDAM` | คลินิคอลดาต้า | DSBA (Coop) | วิชาเลือกสาย Health Data |
| `06026256` | การจัดการการปฏิบัติการ | OPERATIONS MANAGEMENT | `3(3-0-6)` | `OM`, `Op Man` | โอเปอเรชัน, การจัดการผลิต | DSBA (Coop) | วิชาเลือกสาย Business |
| `06026259` | สหกิจศึกษาทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ | COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS | `6(0-35-0)` | `Coop`, `CE-DSBA` | สหกิจ DSBA | DSBA (Coop) | สหกิจแผน DSBA |
| `06026260` | สหกิจศึกษาต่างประเทศทางวิทยาการข้อมูลและการวิเคราะห์เชิงธุรกิจ | OVERSEA COOPERATIVE EDUCATION IN DATA SCIENCE AND BUSINESS ANALYTICS | `6(0-35-0)` | `Overseas Coop`, `OCE-DSBA` | สหกิจนอก DSBA | DSBA (Coop) | สหกิจต่างประเทศ DSBA |

### 🏛️ สาขาวิชาเทคโนโลยีสารสนเทศทางธุรกิจ (BIT - รหัส 0603) (30 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `06036100` | พื้นฐานทางด้านเทคโนโลยีสารสนเทศ | INFORMATION TECHNOLOGY FUNDAMENTALS | `3(2-2-5)` | `ITF`, `IT Fund` | ไอทีฟันด์, พื้นฐานไอที | BIT (Coop / Non-Coop) | วิชาปี 1 เทอม 1 BIT |
| `06036101` | คณิตศาสตร์สำหรับธุรกิจ | MATHEMATICS FOR BUSINESS | `3(3-0-6)` | `MB`, `Math Biz` | แมธธุรกิจ, คณิตธุรกิจ | BIT (Coop / Non-Coop) | วิชาคณิตศาสตร์สำหรับสายธุรกิจ |
| `06036102` | การวิเคราะห์เชิงสถิติสำหรับธุรกิจ | STATISTICAL ANALYSIS FOR BUSINESS | `3(3-0-6)` | `SAB`, `Stat Biz` | สถิติธุรกิจ, สแตทธุรกิจ | BIT (Coop / Non-Coop) | วิชาสถิติของ BIT |
| `06036103` | บูรณาการเทคนิคเชิงสถิติสำหรับธุรกิจ | INTEGRATION OF STATISTICAL TECHNIQUES FOR BUSINESS | `3(3-0-6)` | `ISTB` | สถิติประยุกต์ธุรกิจ | BIT (Coop / Non-Coop) | ต่อจาก 06036102 |
| `06036104` | องค์กรและการจัดการ | MANAGEMENT AND ORGANIZATIONS | `3(3-0-6)` | `MO`, `M&O` | การจัดการองค์กร | BIT (Coop / Non-Coop) | วิชาหลักการจัดการ |
| `06036105` | บัญชีการเงินสำหรับผู้มิใช่นักบัญชี | FINANCIAL ACCOUNTING FOR NON-ACCOUNTANTS | `3(3-0-6)` | `FANA`, `Fin Acc` | บัญชีการเงิน, บัญชี | BIT (Coop / Non-Coop) | การทำบัญชีธุรกิจ |
| `06036106` | การจัดการข้อมูลธุรกิจและเทคโนโลยีเกิดใหม่ | MANAGING BUSINESS INFORMATION AND EMERGING TECHNOLOGIES | `3(3-0-6)` | `MBIET` | ข้อมูลธุรกิจ, เทคโนโลยีเกิดใหม่ | BIT (Coop / Non-Coop) | วิชาเฉพาะ BIT |
| `06036107` | การบริหารโครงการเทคโนโลยีสารสนเทศ | INFORMATION TECHNOLOGY PROJECT MANAGEMENT | `3(3-0-6)` | `ITPM`, `PM` | โปรเจกต์แมเนจเมนต์, ไอทีพีเอ็ม | BIT (Coop / Non-Coop) | การคุมโครงการซอฟต์แวร์ |
| `06036108` | เศรษฐศาสตร์เทคโนโลยีสารสนเทศ | ECONOMICS OF INFORMATION TECHNOLOGY | `3(3-0-6)` | `EIT`, `Econ IT` | เศรษฐศาสตร์ไอที, อีคอนไอที | BIT (Coop / Non-Coop) | เศรษฐศาสตร์ธุรกิจไอที |
| `06036109` | กระบวนการและโมเดลทางธุรกิจ | BUSINESS PROCESSES AND BUSINESS MODEL | `3(3-0-6)` | `BPM`, `BPBM` | โมเดลธุรกิจ, กระบวนการธุรกิจ | BIT (Coop / Non-Coop) | Business Model Canvas / BPMN |
| `06036110` | การวางแผนทรัพยากรองค์กร | ENTERPRISE RESOURCE PLANNING | `3(3-0-6)` | `ERP` | อีอาร์พี, ระบบอีอาร์พี | BIT (Coop / Non-Coop) | เช่น ระบบ SAP |
| `06036111` | เทคโนโลยีดิจิทัลสำหรับธุรกิจ | DIGITAL TECHNOLOGY FOR BUSINESS | `3(3-0-6)` | `DTB`, `Digital Biz` | ดิจิทัลธุรกิจ | BIT (Coop / Non-Coop) | วิชาพื้นฐาน BIT |
| `06036112` | แนวคิดระบบฐานข้อมูล | DATABASE SYSTEM CONCEPTS | `3(2-2-5)` | `DB`, `Database` | ดีบี, ฐานข้อมูล | BIT (Coop / Non-Coop) | วิชาฐานข้อมูลของ BIT |
| `06036113` | การออกแบบส่วนต่อประสานกับมนุษย์ | HUMAN INTERFACE DESIGN | `3(3-0-6)` | `HID`, `HCI`, `UI/UX` | ยูไอ, ยูเอ็กซ์ | BIT (Coop / Non-Coop) | การออกแบบ UX/UI |
| `06036114` | การพัฒนาเว็บแอปพลิเคชันโดยใช้เฟรมเวิร์ก | WEB APPLICATION DEVELOPMENT USING FRAMEWORKS | `3(2-2-5)` | `WAD`, `Web Framework` | เว็บเฟรมเวิร์ก | BIT (Coop / Non-Coop) | Django, Laravel, React ฯลฯ |
| `06036115` | ความมั่นคงของระบบสารสนเทศ | INFORMATION SYSTEM SECURITY | `3(3-0-6)` | `ISS`, `InfoSec`, `Sec` | อินโฟเซค, ความปลอดภัยสารสนเทศ | BIT (Coop / Non-Coop) | ความมั่นคงปลอดภัยสารสนเทศ |
| `06036116` | การตลาดเชิงดิจิทัล | DIGITAL MARKETING | `3(2-2-5)` | `DM`, `Dig Mkt` | ดิจิทัลมาร์เก็ตติ้ง, การตลาดดิจิทัล | BIT (Coop / Non-Coop) | SEO, Ads, Social Media Marketing |
| `06036117` | อัจฉริยะทางธุรกิจและข้อมูลขนาดใหญ่ | BUSINESS INTELLIGENCE AND BIG DATA | `3(3-0-6)` | `BI`, `Big Data`, `BIBD` | บีไอ, บิ๊กดาต้าธุรกิจ, ธุรกิจอัจฉริยะ | BIT (Coop / Non-Coop) | Power BI, Data Warehouse ในมุมมองธุรกิจ |
| `06036118` | การแก้ปัญหาทางด้านเทคโนโลยีสารสนเทศ | PROBLEM SOLVING IN INFORMATION TECHNOLOGY | `3(2-2-5)` | `PSIT` | พีเอสไอที, พรอบเบลมโซลวิง | BIT (Coop / Non-Coop) | วิชาแก้ปัญหาปี 1 |
| `06036119` | พื้นฐานการเขียนโปรแกรม | PROGRAMMING FUNDAMENTALS | `3(2-2-5)` | `PF`, `Prog Fund` | โปรแกรมมิ่ง, พื้นฐานการเขียนโปรแกรม | BIT (Coop / Non-Coop) | วิชาเขียนโค้ดของ BIT |
| `06036120` | หลักการโครงสร้างข้อมูลและอัลกอริทึม | DATA STRUCTURES AND ALGORITHMS PRINCIPLES | `3(3-0-6)` | `DSA`, `DS`, `Data Struc` | ดาต้าสตัค, อัลกอริทึม | BIT (Coop / Non-Coop) | โครงสร้างข้อมูลและอัลกอริทึม |
| `06036121` | การวิเคราะห์และออกแบบระบบสารสนเทศทางธุรกิจ | BUSINESS INFORMATION SYSTEM ANALYSIS AND DESIGN | `3(3-0-6)` | `ISD`, `ISAD`, `BISAD`, `SAD` | ไอเอสดี, ซิสเต็มดีไซน์, เอสเอดี | BIT (Coop / Non-Coop) | 🎯 วิชา ISD ของสาขา BIT! |
| `06036122` | การสื่อสารด้วยภาพสำหรับธุรกิจ | VISUAL COMMUNICATION FOR BUSINESS | `3(2-2-5)` | `VCB`, `Visual Comm` | วิชวลคอมมิวนิเคชัน | BIT (Coop / Non-Coop) | การนำเสนอข้อมูลธุรกิจด้วยภาพ |
| `06036123` | เทคโนโลยีกลุ่มเมฆ | CLOUD TECHNOLOGY | `3(3-0-6)` | `Cloud`, `CT` | คลาวด์, คลาวด์เทคโนโลยี | BIT (Coop / Non-Coop) | Cloud computing สำหรับธุรกิจ |
| `06036124` | เครือข่ายคอมพิวเตอร์และความมั่นคงทางไซเบอร์เบื้องต้น | INTRODUCTION TO COMPUTER NETWORK AND CYBERSECURITY | `3(3-0-6)` | `ICNC`, `Net Sec` | เน็ตเวิร์กไซเบอร์, เน็ตเซค | BIT (Coop / Non-Coop) | ระบบเครือข่ายและความมั่นคงของ BIT |
| `06036125` | สถาปัตยกรรมคอมพิวเตอร์และระบบปฏิบัติการ | COMPUTER ARCHITECTURE AND OPERATING SYSTEM | `3(2-2-5)` | `CAOS`, `OS`, `Com Arch` | โอเอส, คอมอาร์ก, ระบบปฏิบัติการ | BIT (Coop / Non-Coop) | สถาปัตยกรรมและระบบปฏิบัติการ |
| `06036145` | โครงงานทางด้านเทคโนโลยีสารสนเทศเชิงธุรกิจ 1 | PROJECT IN BUSINESS INFORMATION TECHNOLOGY 1 | `3(0-9-0)` | `PBIT 1`, `Proj BIT 1` | โปรเจกต์ 1 BIT | BIT (Non-Coop) | โครงงานจบการศึกษา |
| `06036146` | โครงงานทางด้านเทคโนโลยีสารสนเทศเชิงธุรกิจ 2 | PROJECT IN BUSINESS INFORMATION TECHNOLOGY 2 | `3(0-9-0)` | `PBIT 2`, `Proj BIT 2` | โปรเจกต์ 2 BIT | BIT (Non-Coop) | โครงงานจบการศึกษา |
| `06036147` | สหกิจศึกษา | COOPERATIVE EDUCATION | `6(0-35-0)` | `Coop`, `CE` | สหกิจ BIT | BIT (Coop) | สหกิจศึกษา BIT |
| `06036148` | สหกิจศึกษาต่างประเทศ | OVERSEA COOPERATIVE EDUCATION | `6(0-35-0)` | `Overseas Coop`, `OCE` | สหกิจนอก BIT | BIT (Coop) | สหกิจศึกษาต่างประเทศ BIT |

### 🏛️ สาขาวิชาปัญญาประดิษฐ์ประยุกต์ (AIT - รหัส 0604) (21 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `06046400` | แคลคูลัส 1 | CALCULUS 1 | `3(3-0-6)` | `Cal 1`, `CAL 1` | แคล 1, แคลคูลัส 1 | AIT | วิชาบังคับก่อนของ แคลคูลัส 2 AIT |
| `06046401` | แคลคูลัส 2 | CALCULUS 2 | `3(3-0-6)` | `Cal 2`, `CAL 2` | แคล 2, แคลคูลัส 2 | AIT | ต้องผ่านแคลคูลัส 1 ก่อน |
| `06046402` | พีชคณิตเชิงเส้น | LINEAR ALGEBRA | `3(3-0-6)` | `LA`, `Linear` | ลิเนียร์, ลิเนียร์แอลจีบรา | AIT | คณิตศาสตร์รากฐานของ AI/Deep Learning |
| `06046403` | การโปรแกรมคอมพิวเตอร์ | COMPUTER PROGRAMMING | `3(2-2-5)` | `CP`, `Prog` | คอมโปร, โปรแกรมมิ่ง | AIT | การเขียนโปรแกรมของสาขา AIT |
| `06046404` | พื้นฐานของระบบสมองกลฝังตัว | FUNDAMENTAL OF EMBEDDED SYSTEM | `3(3-0-6)` | `FES`, `Embedded` | สมองกลฝังตัว, เอ็มเบดเด็ด | AIT | Microcontroller, Edge AI, Embedded |
| `06046405` | การเรียนรู้ของเครื่องเชิงความน่าจะเป็น | PROBABILISTIC MACHINE LEARNING | `3(3-0-6)` | `PML`, `ML` | แมชชีนเลิร์นนิง, พีเอ็มแอล | AIT | 🎯 วิชา Machine Learning ของสาขา AIT! |
| `06046406` | พื้นฐานการเรียนรู้เชิงลึก | FUNDAMENTALS OF DEEP LEARNING | `3(3-0-6)` | `FDL`, `DL`, `Deep Learning` | ดีพเลิร์นนิง, ดีพ | AIT | Neural Networks, CNN, RNN, Transformers |
| `06046407` | พื้นฐานวิทยาการข้อมูล | FUNDAMENTALS OF DATA SCIENCE | `3(3-0-6)` | `FDS`, `Data Science`, `DS` | ดาต้าไซน์, วิทยาการข้อมูล | AIT | วิชาแกนด้าน Data |
| `06046408` | การแสดงข้อมูลด้วยแผนภาพ | DATA VISUALIZATION | `3(2-2-5)` | `DV`, `Data Viz` | ดาต้าวิด, ดาต้าวิชวลไลเซชัน | AIT | การพลอตและการสร้าง Dashboard |
| `06046409` | คอมพิวเตอร์ทัศนเบื้องต้น | INTRODUCTION TO COMPUTER VISION | `3(3-0-6)` | `ICV`, `CV`, `Computer Vision` | คอมพิวเตอร์วิชั่น, ซีวี, วิชั่น | AIT | การประมวลผลภาพ, OpenCV, YOLO |
| `06046410` | การประมวลผลภาษาธรรมชาติเบื้องต้น | INTRODUCTION TO NATURAL LANGUAGE PROCESSING | `3(3-0-6)` | `INLP`, `NLP` | เอ็นแอลพี, ภาษาธรรมชาติ | AIT | Text Processing, Tokenization, LLMs |
| `06046411` | การวิเคราะห์และเพิ่มประสิทธิภาพเครือข่าย | NETWORK ANALYSIS AND OPTIMIZATION | `3(3-0-6)` | `NAO`, `Net Opt` | เน็ตเวิร์กออปติไมเซชัน | AIT | การวิเคราะห์เครือข่าย |
| `06046412` | การเพิ่มประสิทธิภาพโครงข่ายประสาทเทียม | NEURAL NETWORK OPTIMIZATION | `3(3-0-6)` | `NNO`, `Neural Net` | นิวรัลเน็ต | AIT | Gradient descent, backpropagation, tuning |
| `06046413` | ปัญญาประดิษฐ์และอินเทอร์เน็ตประสานสรรพสิ่ง | ARTIFICIAL INTELLIGENCE AND INTERNET OF THING | `3(3-0-6)` | `AIoT`, `AI-IoT`, `AI` | เอไอไอโอที, เอไอ | AIT | Edge AI บนอุปกรณ์ IoT |
| `06046414` | การประมวลผลภาษาธรรมชาติด้วยการเรียนรู้อย่างเชิงลึก | NATURAL LANGUAGE PROCESSING WITH DEEP LEARNING | `3(3-0-6)` | `NLP-DL`, `NLP`, `DL` | เอ็นแอลพีดีพ, ดีพเอ็นแอลพี | AIT | Transformers, BERT, GPT models |
| `06046415` | การประมวลผลสัญญาณ | SIGNAL PROCESSING | `3(3-0-6)` | `SP`, `Signal` | ซิกนัล, ประมวลผลสัญญาณ | AIT | Audio / Sensor signal processing |
| `06046440` | วิชาสัมมนาปัญญาประดิษฐ์ | SEMINAR IN ARTIFICIAL INTELLIGENCE | `3(2-2-5)` | `SAI`, `Seminar AI` | สัมมนาเอไอ, สัมมนา | AIT | การนำเสนองานวิจัย AI |
| `06046441` | โครงงานเทคโนโลยีปัญญาประดิษฐ์ 1 | PROJECT IN ARTIFICIAL INTELLIGENCE TECHNOLOGY 1 | `3(0-9-0)` | `PAIT 1`, `Proj AI 1` | โปรเจกต์ 1 AIT | AIT | วิชาโครงงาน AI จบการศึกษา |
| `06046442` | โครงงานเทคโนโลยีปัญญาประดิษฐ์ 2 | PROJECT IN ARTIFICIAL INTELLIGENCE TECHNOLOGY 2 | `3(0-9-0)` | `PAIT 2`, `Proj AI 2` | โปรเจกต์ 2 AIT | AIT | วิชาโครงงาน AI จบการศึกษา |
| `06046443` | สหกิจศึกษาทางเทคโนโลยีปัญญาประดิษฐ์ | COOPERATIVE EDUCATION IN ARTIFICIAL INTELLIGENCE TECHNOLOGY | `6(0-45-0)` | `Coop`, `CE-AIT` | สหกิจ AIT | AIT | สหกิจศึกษา AIT |
| `06046444` | สหกิจศึกษาต่างประเทศทางเทคโนโลยีปัญญาประดิษฐ์ | OVERSEA COOPERATIVE EDUCATION IN ARTIFICIAL INTELLIGENCE TECHNOLOGY | `6(0-45-0)` | `Overseas Coop`, `OCE-AIT` | สหกิจนอก AIT | AIT | สหกิจศึกษาต่างประเทศ AIT |

### 🏛️ หมวดวิชาศึกษาทั่วไป (General Education - GE รหัส 9064 และ 9664) (23 รายวิชา)

| รหัสวิชา | ชื่อภาษาไทย | ชื่อภาษาอังกฤษ | หน่วยกิต | ตัวย่อภาษาอังกฤษที่นิยม | คำย่อ / แสลงภาษาไทย | สาขาวิชา | หมายเหตุ / จุดสังเกต |
|:---:|---|---|:---:|---|---|:---:|---|
| `90641001` | โรงเรียนสร้างเสน่ห์ | CHARM SCHOOL | `2(1-2-3)` | `Charm`, `CS` | ชาร์ม, ชาร์มสคูล, โรงเรียนสร้างเสน่ห์ | IT, DSBA | วิชา GE หมวดพัฒนาตนเอง |
| `90641002` | ความฉลาดทางดิจิทัล | DIGITAL INTELLIGENCE QUOTIENT | `3(3-0-6)` | `DIQ` | ดีไอคิว, ความฉลาดดิจิทัล | IT, DSBA | มีใน ACRONYM_MAP แล้ว |
| `90641003` | กีฬาและนันทนาการ | SPORTS AND RECREATIONAL ACTIVITIES | `1(0-3-2)` | `Sport` | กีฬา, นันทนาการ | IT, DSBA | วิชาพละ 1 หน่วยกิต |
| `90641004` | โครงงานกลุ่ม 1 | TEAM-PROJECT 1 | `1(0-2-1)` | `TP 1`, `Team Proj 1` | ทีมโปรเจกต์ 1 | AIT | วิชา GE ของ AIT |
| `90641005` | โครงงานกลุ่ม 2 | TEAM-PROJECT 2 | `1(0-2-1)` | `TP 2`, `Team Proj 2` | ทีมโปรเจกต์ 2 | AIT | วิชา GE ของ AIT |
| `90641006` | โครงงานกลุ่ม 3 | TEAM-PROJECT 3 | `1(0-2-1)` | `TP 3`, `Team Proj 3` | ทีมโปรเจกต์ 3 | AIT | วิชา GE ของ AIT |
| `90641007` | พลเมืองดิจิทัล | DIGITAL CITIZEN | `3(3-0-6)` | `DC` | ดิจิทัลซิติเซน | AIT | วิชา GE ของ AIT |
| `90641009` | ทักษะการสื่อสารภาษาอังกฤษระหว่างวัฒนธรรม 1 | INTERCULTURAL COMMUNICATION SKILLS IN ENGLISH 1 | `3(3-0-6)` | `ICE 1`, `ICSE 1` | อิ้งค์ 1 AIT | AIT | วิชาภาษาอังกฤษ AIT |
| `90641010` | ทักษะการสื่อสารภาษาอังกฤษระหว่างวัฒนธรรม 2 | INTERCULTURAL COMMUNICATION SKILLS IN ENGLISH 2 | `3(3-0-6)` | `ICE 2`, `ICSE 2` | อิ้งค์ 2 AIT | AIT | วิชาภาษาอังกฤษ AIT |
| `90642012` | กระบวนการคิดเชิงออกแบบ | DESIGN THINKING | `3(3-0-6)` | `DT`, `Design Thinking` | ดีไซน์ธิงกิ้ง | AIT | วิชา GE ความคิดสร้างสรรค์ |
| `90642033` | กฎหมายสำหรับคนรุ่นใหม่ | LAW FOR NEW GENERATION | `3(3-0-6)` | `Law` | กฎหมาย, ลอว์ | IT, DSBA | วิชา GE ด้านกฎหมายและจริยธรรม |
| `90643021` | ผู้ประกอบการสมัยใหม่ | MODERN ENTREPRENEURS | `3(3-0-6)` | `ME` | ผู้ประกอบการ | IT, DSBA | วิชา GE ด้านธุรกิจและสตาร์ตอัป |
| `90644007` | ภาษาอังกฤษพื้นฐาน 1 | FOUNDATION ENGLISH 1 | `3(3-0-6)` | `ENG 1`, `FE 1` | อิ้ง 1, อังกฤษ 1, ภาษาอังกฤษ 1 | IT, DSBA | มีใน ACRONYM_MAP แล้ว |
| `90644008` | ภาษาอังกฤษพื้นฐาน 2 | FOUNDATION ENGLISH 2 | `3(3-0-6)` | `ENG 2`, `FE 2` | อิ้ง 2, อังกฤษ 2, ภาษาอังกฤษ 2 | IT, DSBA | ภาษาอังกฤษตัวต่อ |
| `90644042` | การสื่อสารและการนำเสนออย่างมืออาชีพ | PROFESSIONAL COMMUNICATION AND PRESENTATION | `3(3-0-6)` | `PCP`, `Presen` | พรีเซนต์, การนำเสนอ | IT, DSBA | วิชาการนำเสนอ |
| `96641001` | โรงเรียนสร้างเสน่ห์ | CHARM SCHOOL | `2(1-2-3)` | `Charm`, `CS` | ชาร์ม, ชาร์มสคูล | BIT | วิชา GE ของ BIT |
| `96641002` | ความฉลาดทางดิจิทัล | DIGITAL INTELLIGENCE QUOTIENT | `3(3-0-6)` | `DIQ` | ดีไอคิว | BIT | วิชา GE ของ BIT |
| `96641003` | กีฬาและนันทนาการ | SPORTS AND RECREATIONAL ACTIVITIES | `1(0-3-2)` | `Sport` | กีฬา | BIT | วิชาพละ BIT |
| `96642033` | กฎหมายสำหรับคนรุ่นใหม่ | LAW FOR NEW GENERATION | `3(3-0-6)` | `Law` | กฎหมาย | BIT | วิชา GE BIT |
| `96643021` | ผู้ประกอบการสมัยใหม่ | MODERN ENTREPRENEURS | `3(3-0-6)` | `ME` | ผู้ประกอบการ | BIT | วิชา GE BIT |
| `96644007` | ภาษาอังกฤษพื้นฐาน 1 | FOUNDATION ENGLISH 1 | `3(3-0-6)` | `ENG 1`, `FE 1` | อิ้ง 1, อังกฤษ 1 | BIT | วิชาภาษาอังกฤษ BIT |
| `96644008` | ภาษาอังกฤษพื้นฐาน 2 | FOUNDATION ENGLISH 2 | `3(3-0-6)` | `ENG 2`, `FE 2` | อิ้ง 2, อังกฤษ 2 | BIT | วิชาภาษาอังกฤษ BIT |
| `96644042` | การสื่อสารและการนำเสนออย่างมืออาชีพ | PROFESSIONAL COMMUNICATION AND PRESENTATION | `3(3-0-6)` | `PCP` | การนำเสนอ, พรีเซนต์ | BIT | วิชาภาษาอังกฤษ BIT |

---

## 💡 3. ข้อเสนอแนะเชิงระบบในการรองรับตัวย่อ (System Improvement Recommendations)

### 3.1 ตัวย่อเด่นที่ควรเพิ่มเข้าสู่ระบบทันที (Unambiguous Acronyms):
- **`ISD` / `ISAD`** ➔ ชี้ไปยัง `06066304 การวิเคราะห์และออกแบบระบบสารสนเทศ` (IT/DSBA) หรือ `06036121` (BIT)
- **`DSA`** ➔ ชี้ไปยัง `06066301 โครงสร้างข้อมูลและอัลกอริทึม` (Data Structures and Algorithms)
- **`PSP`** ➔ ชี้ไปยัง `06066303 การแก้ปัญหาและการโปรแกรมคอมพิวเตอร์` (Problem Solving and Computer Programming)
- **`ITF`** ➔ ชี้ไปยัง `06016402` / `06036100` (Information Technology Fundamentals)
- **`CNI`** ➔ ชี้ไปยัง `06016419 โครงสร้างพื้นฐานเครือข่ายการสื่อสาร` (Communication Network Infrastructure)
- **`BDS`** ➔ ชี้ไปยัง `06026213 ระบบข้อมูลมหัต` (Big Data Systems)
- **`ERP`** ➔ ชี้ไปยัง `06036110 การวางแผนทรัพยากรองค์กร` (Enterprise Resource Planning)
- **`NLP`** ➔ ชี้ไปยัง `06046410` (Natural Language Processing)
- **`CV`** ➔ ชี้ไปยัง `06046409` (Computer Vision)
- **`DL`** ➔ ชี้ไปยัง `06046406` (Deep Learning)
- **`AIoT`** ➔ ชี้ไปยัง `06046413` (Artificial Intelligence and Internet of Things)

### 3.2 ตัวย่อกำกวมที่ควรแสดงทางเลือกให้ผู้ใช้ (Ambiguous Acronyms):
- **`AI`**: อาจหมายถึงสาขา `AIT`, หรือวิชา `06046413 AIoT`, หรือ `06046440 สัมมนา AI`
- **`DB` / ฐานข้อมูล**: มีทั้ง `06066300 แนวคิดระบบฐานข้อมูล` และ `06016414/06026207 NoSQL Database`
- **`DS`**: อาจหมายถึง `Data Structures` (โครงสร้างข้อมูล) หรือ `Data Science` (วิทยาการข้อมูล)
- **`NET` / เครือข่าย**: มีทั้ง `06016413 ระบบเครือข่ายเบื้องต้น` และ `06016419 โครงสร้างพื้นฐานเครือข่าย`
- **`WEB`**: มีทั้ง `06066302 Web Programming (Frontend)` และ `06016418 Server-Side Web (Backend)`