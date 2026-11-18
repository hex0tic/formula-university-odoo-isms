# Шаардлага ба хүлээн авах шалгуур

Эх сурвалж: `../БД төсөл_ Odoo ERP-ISO27001 26-27А.pdf`, 6 хуудас. 2026-11-16-нд бүх хуудсыг зургаар уншсан. Албан зааврын шаардлага болон хэрэглэгчийн нэмэлтийг тусад нь тэмдэглэв.

## Хамрах ажил

Odoo Community Edition дээр их сургуулийн бодит нөхцөлд ойр зохиомол кейсийн мэдээллийн аюулгүй байдлын менежментийн тогтолцоо (Information Security Management System, ISMS)-г төлөвлөж, баримтжуулж, хэрэгжүүлнэ. ISO/IEC 27001:2022 Clause 4–10, Annex A-тай холбоог тайлбарлана. Odoo нь өөрөө ISO баталгаажуулалт олгохгүй; хяналтын бодит үйл ажиллагаа, нотолгоог удирдах хэрэгсэл болно.

| ID | Шаардлага | Эх | Хүлээн авах нотолгоо | Эзэн |
|---|---|---|---|---|
| R01 | Odoo Community Edition; локал Docker эсвэл source deployment | х.1–2 §3 | version, compose/image/source ID, login screenshot | Deployment агент |
| R02 | Байгууллагын кейс: үйл ажиллагаа, өгөгдлийн төрөл, гол эрсдэл, Clause 4 | х.3 Д1 | case.md, context/stakeholders/scope, тайлангийн танилцуулга | Codex |
| R03 | Odoo модуль сонголт, control бүртэй холбоо, сонгосон үндэслэл | х.3 Д2 | module–control–implementation хүснэгт | Codex/Deployment агент |
| R04 | Хөрөнгийн бүртгэл ≥10; Asset, Owner, Classification, Location, Risk | х.4 Д3 | canonical register + Odoo Inventory/Documents дахь бодит бүртгэл ба screenshot | OpenCode/Deployment агент |
| R05 | Эрсдэлийн бүртгэл ≥10; Threat, Vulnerability, Likelihood, Impact, Risk Level | х.4 Д4 | эрсдэлийн аргачлал, 5×5 матриц, ≥10 мөр; оноо тооцоолол | OpenCode |
| R06 | Annex A 20–25 хяналт сонгож Odoo implementation-тэй холбох | х.4 Д5 | 25 хяналтын mapping; asset→risk→treatment→control→evidence холбоо | OpenCode/Deployment агент |
| R07 | Incident → Report → Investigate → Resolve → Close таван шат | х.4 Д6 | workflow диаграм, Community Helpdesk дахь тасалбарын бодит шилжилт | Deployment агент |
| R08 | Information Security Policy, Access Control Policy, Risk Treatment Plan зэрэг 2–3 бодлого, тус бүр 1–2 хуудас | х.4 Д7 | 3 бодлого, эзэн/батлах үүрэг/хянан үзэх давтамж/хэрэгжилт | OpenCode |
| R09 | ≥5 өөр эрхийн түвшин (RBAC) | х.5 Д8 | бүлэг ба ACL/record rule матриц; 5+ хэрэглэгч; allow/deny шалгалт; screenshot | Deployment агент/Codex |
| R10 | Хэрэглэгчид үүсгэх | х.5 Д8 | users screenshot, role membership, synthetic demo accounts | Deployment агент |
| R11 | Хэрэглэгчийн үйлдлийг audit log-д бодитоор бүртгэх | х.5 Д8 | өөр хэрэглэгчийн create/write/approval/read test шаардлагын дагуу; actor/time/model/action | Deployment агент/Codex |
| R12 | Сонгосон Annex A бүрийн SoA: Тийм/Үгүй/Хэсэгчилсэн, тайлбар/үндэслэл | х.5 Д8 | 25 control-ын SoA, applicability ба implementation тусдаа талбар | OpenCode/Deployment агент |
| R13 | Нэг нэгдсэн Word эсвэл PDF тайлан, ойролцоогоор 20–30 хуудас | х.5 §6 | бүрэн render/структур/эх сурвалжийн QA | Баг |
| R14 | Нүүр: байгууллага, багийн гишүүд, огноо | х.5 §6.1 | Formula 5-ын баталгаатай 5 нэр, курс, зөв огноо | Баг |
| R15 | Тайлангийн дараалал: удиртгал; модуль/ISO; asset; risk; mapping; incident; policies; RBAC/audit/SoA; дүгнэлт; хавсралт/эх сурвалж | х.5 §6 | бүтэцтэй TOC, бүх хэсэг, зураг/хүснэгтийн тайлбар | Баг |
| R16 | Odoo screenshot PNG/JPG тайланд шингээх | х.4–6 | бодит UI screenshot; raw evidence, timestamp, тайлан дахь байрлал | Codex |
| R17 | PowerPoint/PDF 8–12 слайд | х.6 §8 | render хийж шалгасан presentation | Баг |
| R18 | Хамгаалалт ба Odoo demo 10–15 минут | х.6 §8 | demo script, 5 хүний ярих хэсэг, recoverable demo state | Баг |
| R19 | Гишүүн бүрийн бодит хувь нэмэр, login/Git trace, тайлбар | х.2,6 | хүний ажилд тулгуурласан contribution table; зохиомол хувь нэмэргүй | Хүний баг |
| R20 | Бүтээл өөрийнх; шууд хуулбарлахгүй; AI хэрэглээг төгсгөлд товч дурдана | х.6 §9 | эх сурвалж, AI assistance disclosure, бодит орчны нотолгоо | Бүгд |
| R21 | Монгол хэл; техникийн нэр ба Odoo module нэрийг англиар үлдээж болно | х.1 | glossary-д нийцсэн Монгол бичвэр | Бүгд |
| U01 | Үндсэн biydaalt/management дотор агент хоорондын messages.md, worklog.md, төлөвлөгөө зэрэг файлууд | хэрэглэгч | append-only бүртгэл, ажлын хуваарилалт | Codex |
| U02 | OpenCode, Deployment агент, Codex хамтран ярилцаж давхцалгүй ажиллах | хэрэглэгч | messages.md, эзэмших замууд, шийдвэрийн мөр | Бүгд |
| U03 | Шинэ, их сургуультай холбоотой, бодит нөхцөлд ойр кейс | хэрэглэгч | өмнөх семинарын кейсийг хуулбарлаагүй шинэ урсгал | Codex |
| U04 | Өмнөх лекц, семинарын засаглал/менежментийн ойлголтыг судлах | хэрэглэгч | course-review.md, glossary.md, кейсийн уялдаа | Sophia |
| U05 | Odoo татаж суулгах, зориулалт, ажиллуулах арга, бүтцийг тайлбарлах | хэрэглэгч | ажиллагаатай service, operations guide, архитектур | Deployment агент/Codex |
| U06 | Өөрсдийн их сургуулийн систем хөгжүүлэх | хэрэглэгч | campus_university custom module + ISMS integration + функционал/эрхийн шалгалт | Codex/Deployment агент |
| U07 | Баг 5 гишүүнтэй; нэрс өмнөх тайлангаас | хэрэглэгч | team.md ба эх тайлангийн мөр | Sophia |
| U08 | VM/server reuse policy, registry refresh/search ба reservation | AGENTS.md | environment-audit.md, deployment lease/registry | Deployment агент |

## Зөрүүг шийдсэн тайлбар

- Зааврын хуваарийн жишээнд 8–10 controls mapping гэж байгаа боловч дэлгэрэнгүй Даалгавар 5-д 20–25 гэж заасан: **25** хяналтыг үндсэн босго болгоно.
- Эх заавар 4 оюутны жишигтэй; хэрэглэгч **5 гишүүн** гэж тодруулсан тул 5 хүний хуваарилалт хэрэглэнэ.
- Community Edition гэсэн заавар болон Helpdesk/Documents нэрийн availability-г сонгосон хувилбарын primary source-оор шалгаж, Enterprise proprietary module-ийн оронд Community-compatible OCA/custom хэрэгжүүлэлтийг ил тод тайлбарлана. Asset Register нь rubric-ийн шаардсан Inventory-той заавал холбоно.
- Зааврын 12/13-р долоо хоногийн хуваарийг сургуулийн календарын огноогүй тул тодорхой өдөр болгон зохиохгүй.
- Хүний бодит хувь нэмэр, албан багшийн баталгаа, их сургуулийн ISO гэрчилгээ зэргийг агентуудын туршилтын үр дүнгээс дүгнэхгүй.

## Үнэлгээ

Ойлголт 1.5; практик хэрэгжүүлэлт 3.0; ISO mapping 2.0; бүтээлч байдал 2.0; баримт бичиг 1.5; нийт 10 оноо (эх PDF х.5–6).

## Баталгаажуулалтын босго

1. Шаардлага бүр canonical файл ба бодит нотолгоотой холбогдсон байна.
2. RBAC-ийн зөвшөөрөх болон хориглох туршилт хоёул өнгөрсөн байна.
3. Дүн өөрчлөхөд хүсэлт гаргагч өөрийн хүсэлтийг батлахгүй; баталсан өөрчлөлт л хүчинтэй дүнд тусна.
4. Audit log нь actor, timestamp ба өөрчлөлттэй; зөвхөн chatter-г бүрэн audit гэж нэрлэхгүй.
5. Seed дахин ачаалахад давхар бичлэг үүсгэхгүй; DB/filestore нөөцлөлт ба сэргээхийг тусад нь шалгана.
6. Одоо байгаа shared disk, service, өөр хичээлийн evidence-д өөрчлөлт оруулахгүй.
