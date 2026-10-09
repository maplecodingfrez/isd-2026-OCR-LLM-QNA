/* ตั้งธีม/ภาษาที่บันทึกไว้บน <html> ก่อนวาดหน้า (โหลดแบบ blocking ใน <head>) กันจอกะพริบธีมผิด — ไม่ฝังเป็น inline script ตามกติกา index.html = โครงสร้างล้วน */
try {
  var h = document.documentElement, t = localStorage.getItem("theme"), l = localStorage.getItem("lang");
  h.dataset.theme = t === "dark" ? "dark" : "light";   // light is the default; only an explicit saved choice gives dark
  if (l === "en" || l === "th") h.lang = l;
} catch (e) {}
