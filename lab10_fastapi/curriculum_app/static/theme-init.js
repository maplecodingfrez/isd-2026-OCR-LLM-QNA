/* ตั้งธีม/ภาษาที่บันทึกไว้บน <html> ก่อนวาดหน้า (โหลดแบบ blocking ใน <head>) กันจอกะพริบธีมผิด — ไม่ฝังเป็น inline script ตามกติกา index.html = โครงสร้างล้วน */
try {
  var h = document.documentElement, t = localStorage.getItem("theme"), l = localStorage.getItem("lang");
  if (t === "light" || t === "dark") h.dataset.theme = t;
  if (l === "en" || l === "th") h.lang = l;
} catch (e) {}
