# Formula 5 — 12 минутын хамгаалалт ба demo

Хүний багийн баталгаатай хуваарилалтаар ярих хэсгийг хуваав. Нууц үг нь `evidence/private/`-д; слайд эсвэл projector дээр нээхгүй. Хоёр өөр browser profile/incognito context ашиглавал requester ба approver session хоорондоо солигдохгүй.

| Хугацаа | Гишүүн | Хийх зүйл / гол тайлбар |
|---|---|---|
| 00:00–01:00 | Тэлмүүн | Зорилго, шинэ кейс, хүрээ. Байгууллагын тоо зохиомол; UI/test нь бодит орчноос. Slide1. |
| 01:00–03:00 | Доржсэмбэ | Slide2–3, засаглал ба менежментийн ялгаа; Odoo18+PostgreSQL16, модуль/bridge, локал deployment. |
| 03:00–05:00 | Бадрал | Slide5–6,16asset Inventory дахь ижил register;14risk; RM-01 lookup; AST002→RSK01→A5.3/A8.15→evidence. |
| 05:00–08:00 | Батдэмбэрэл | Slide4/8, бодит grade request → өөр reviewer approve → student own grade. Requester≠approver, revision, direct-write deny. |
| 08:00–10:00 | Эрхэмбаяр | Slide7/9, Incident→Report→Investigate→Resolve→Close; analyst vsCISO; grade audit actor/pre/post; restore JSON. |
| 10:00–11:00 | Бадрал | Slide10,SoA15yes/10partial; MFA/physical/offsite/SETA төлөвлөгөөний шалтгаан; EISP/Access/RTP. |
| 11:00–12:00 | Тэлмүүн | 39tests0failed0errors, нотолгооны индекс, дүгнэлт; AI assistance ба хүний баталгаажуулалтын ялгаа. |

## Live grade demo

1. `campus.lecturer@orgil.example` хэрэглэгчээр Formula Campus → Дүн өөрчлөх хүсэлт → Шинэ. Өөрийн хичээлийн Демо Анар enrollment сонгоно.
2. Одоогийн score85,revision1 гэдгийг шалга. Дараагийн бодит demo-д proposed score86,шалтгаан≥10 тэмдэг,нотолгоо`DEMO-REHEARSAL-YYYYMMDD` өгнө. Батлагдсан 39 дугаарын хүсэлтийг өөрчлөхгүй.
3. Хадгалж submitted болго. Өөрийн request-ийг өөрөө approve хийж болохгүйг эрх/автомат тесттэй тайлбарла.
4. Тусдаа context-д `campus.reviewer@orgil.example` нэвтэрч шинэ submitted хүсэлтийг approve хийнэ. Student account-аар зөвхөн өөрийн шинэ score ба revision-ийг харуулна.
5. Audit detail-д батлагчийн login,хуучин→шинэ дүн,revision-ийг тулгана. Шинэ demo хийвэл score85 гэсэн хуучин screenshot нь 2026-11-16-ны snapshot гэдгийг хадгална; шинэ үр дүнг тусад нь бүртгэнэ.

## Incident demo

`student_demo` → өөрийн шинэ synthetic incident мэдээлнэ. `erkhembayar` → Investigate,root_cause/resolution оруулж Resolve. `dorjsembe` → шаардлагатай сургамж ба notification decision-ийг шалгаж Close. ISMS ба OCA Helpdesk хоёрын stage ижил байгааг үзүүлнэ. Existing closedINC-2026-0021-г дахин нээхгүй, устгахгүй.

## Бэлтгэл ба fallback

- `odoo/` дотор `docker compose up -d`, дараа `docker compose ps`; browser`http://127.0.0.1:8069`.
- Ажиллаж буй DB дээр `init-db`,бүх importer,backup restore скриптийг хамгаалалтын дундуур ажиллуулахгүй.
- `evidence/screenshots/01–16` ба JSON/log-ууд локал fallback. Screenshot нь заавал бодит UI; үйл явдлыг болсон мэт зохиож үзүүлэхгүй.
- 39 тестийн regression командыг `management/operations.md`-оос авна. Odoo CLI үед веб түр зогсоно.
- Багийн 5 гишүүн өөрсдийн хийсэн шалгалт,ойлгосон тайлбар,өөрчлөлтийг worklog-д огноо/нотолгоотой нэмнэ. Агентын ажлыг хүний хийсэн ажил гэж нэрлэхгүй.
