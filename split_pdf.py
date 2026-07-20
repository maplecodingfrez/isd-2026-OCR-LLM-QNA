from pypdf import PdfReader, PdfWriter

reader = PdfReader(r"data\input\dsba_curriculum.pdf")
print("total pages:", len(reader.pages))

writer = PdfWriter()
for i in range(0, 10):
    writer.add_page(reader.pages[i])

with open(r"data\input\dsba_curriculum_subset.pdf", "wb") as f:
    writer.write(f)

print("subset saved: 10 pages")