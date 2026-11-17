# Каноник өгөгдлийн багц (`biydaalt/data/`)

Энэхүү хавтаст «Formula University» (Formula University — сургалтын зохиомол кейс)-ийн ISO/IEC 27001:2022 болон Odoo 18.0 Community Edition (`university_isms` ба `campus_university`) системд зориулсан каноник өгөгдлийн багц хадгалагдана.

- **Эзэмшигч:** OpenCode (Gemini 4 Argon)
- **Гэрээний хувилбар:** `management/schema-university_isms.md` v1 ба `management/decisions.md` (`D01`–`D07`)
- **Эрсдэлийн аргачлал (`D04`):** `RM-01 v1.0` — Лекц 8–9 Слайд 19-ийн 5×5 матрицын lookup (`low`/`medium`/`high`), тоон оноо `score = likelihood × impact`. Хөрөнгийн CIA үнэ цэнэ нь `max(C, I, A)` (`1..3` → `low`/`medium`/`high`), CIA нийлбэр (`3..9`)-аас тусдаа тооцогдоно.

## Файлын жагсаалт

| Файл | Мөрийн тоо | Тайлбар |
|---|---:|---|
| `departments.csv` | 8 | Formula University-ийн 8 алба, нэгжийн бүтэц (`hr.department`) |
| `users.csv` | 11 | Formula 5 багийн 5 гишүүн + 6 зохиомол албан тушаалын хэрэглэгч (`res.users`, 6 RBAC бүлэг) |
| `assets.csv` / `assets.json` | 16 | Даалгавар 3 — Мэдээллийн болон биет хөрөнгийн бүртгэл (`AST-001`–`AST-016`, бүх16 нь Inventory каталогтой;5 hardware DEMO serial, facility non-stock) |
| `threats.csv` | 14 | Аюул заналын каталог (`T-01`–`T-14`) |
| `vulnerabilities.csv` | 14 | Эмзэг байдлын каталог (`V-01`–`V-14`) |
| `risks.csv` / `risks.json` | 14 | Даалгавар 4 — Эрсдэлийн бүртгэл (`RSK-01`–`RSK-14`, `RM-01 v1.0` 5×5 матриц, анхны ба үлдэгдэл эрсдэл) |
| `risk_matrix_rm01.json` | 25 нүд | `RM-01 v1.0` (Лекц 8–9 Слайд 19) 5×5 матрицын бүх 25 нүдний эталон хүснэгт |
| `soa.csv` / `controls_soa.json` | 93 | Даалгавар 5 ба 8 — ISO/IEC 27001:2022 Annex A-ийн бүх 93 хяналт (үүнээс `selected=True` 25 гол хяналтын Odoo хэрэгжилт) |
| `incidents.csv` / `incidents.json` | 6 | Даалгавар 6 — 5 үе шаттай (`incident` → `report` → `investigate` → `resolve` → `close`) зөрчлийн тасалбарууд |
| `policies.csv` | 4 | Даалгавар 7 — `biydaalt/policies/` дахь 4 бодлогын баримт бичгийн мета-мэдээлэл (`POL-01`–`POL-04`) |
| `stakeholders_objectives.json` | — | Даалгавар 1 ба Clause 4.1–4.3, 6.2 SMART зорилтуудын бүтэцлэгдсэн өгөгдөл |
