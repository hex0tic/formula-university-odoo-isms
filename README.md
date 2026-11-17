# Formula University — Odoo ERP ба ISO/IEC 27001:2022

Formula 5 багийн их сургуулийн шинэ кейс, академик систем болон ISMS хэрэгжүүлэлт. Кейсийн өгөгдөл зохиомол; UI, test, audit ба сэргээх шалгалт нь бодит локал орчноос гарсан.

## Материал

- `reports/Formula5_FormulaUniversity_Odoo_ISMS_Report.docx` — засварлах боломжтой Word хувилбар.
- `reports/Formula5_FormulaUniversity_Odoo_ISMS_Report.pdf` — 28 хуудасны нэгдсэн тайлан.
- `reports/Formula5_FormulaUniversity_Odoo_ISMS_Presentation.pptx` — 10 слайдын засварлах боломжтой танилцуулга.
- `reports/demo-script.md` — 5 хүний 12 минутын хамгаалалт.
- `management/README.md` — төлөвлөгөө, харилцаа, worklog, үүрэг, хичээлийн судалгаа, нэр томьёо, нотолгооны индекс.
- `odoo/addons/` — академик модуль, ISMS, audit/Helpdesk/Inventory интеграц.
- `data/`, `policies/`, `evidence/` — canonical бүртгэл, бодлого, бодит screenshot ба тест.

## Ажиллуулах

`odoo/` дотор `docker compose up -d`. Хөтөч: `http://127.0.0.1:8069`. Одоо байгаа DB-г ажиллуулахад дахин импорт шаардлагагүй. Нэвтрэх мэдээлэл хамгаалсан `evidence/private/` болон `odoo/.env` дотор; тараах архивт ороогүй. Дэлгэрэнгүй: `management/operations.md`, `management/odoo-guide.md`.

## Баталгаажуулалт

16 хөрөнгө ба 16 Inventory product; 14 эрсдэл; 25 сонгосон хяналт (15 yes,10 partial); 7 incident/7Helpdesk ticket; 39 тест 0failed0errors; локалrestore190attachmentchecksumтаарсан. Хүний хариуцах үүрэг нь хэрэглэгчийн баталсан хуваарь;AI тусламжтай хийсэн ажлыг хүн өөрөө хийсэн гэж зохиогоогүй.

Гуравдагч талын эх ба лиценз: `THIRD_PARTY.md`.

## GitHub репозитор

Төслийн тусдаа private репозитор: [hex0tic/formula-university-odoo-isms](https://github.com/hex0tic/formula-university-odoo-isms).

Репозиторт код, кейсийн өгөгдөл, бодлого, удирдлагын баримт, тайлангийн DOCX/PDF, PPTX болон шалгалтын нотолгоо багтана. `.env`, нууц үгтэй тохиргоо, `evidence/private/`, өгөгдлийн сангийн нөөц ба runtime лог ороогүй. Шинээр clone хийсэн орчинд локал нууц үг, өгөгдлийн санг [ажиллуулах зааврын](management/operations.md#шинэ-тусдаа-орчинд-босгох-дараалал) дагуу бэлтгэнэ.
