# Formula University — эрх олголт, нэгж, RBAC, ажилтны эрх цуцлах

Шалгасан огноо: 2026-11-18. Current Odoo DB болон addon source-д тулгуурлав. Энэ баримт эрх өөрчлөх зааварчилгаа болохоос энэ шалгалтаар хэний ч эрхийг өөрчлөөгүй, данс архивлаагүй.

## 1. Хэн эрх олгодог вэ?

Current DB-д `base.group_system` / `base.group_erp_manager` бүхий идэвхтэй данс: `admin`, `batdemberel` (CIO). Эдгээр данс Settings → Users & Companies → Users дээр хэрэглэгч үүсгэж, Access Rights-ийн үүрэг оноож/цуцална. CISO `dorjsembe`-д энэ техникийн Settings эрх байхгүй: ISMS-ийн батлах бизнес эрх нь хэрэглэгчийн эрх удирдах техникийн эрхтэй адил биш.

Кейсийн POL-02 §4: HR тушаал + CISO/нэгжийн даргын зөвшөөрөл → эрх нээх. Зөвшөөрөх нь менежментийн шийдвэр, хэрэгжүүлэх нь админы ажил. Энэ батлах хүсэлт/гүйцэтгэлийг хоёр өөр хүнээр албаддаг зориулалтын access-request workflow кодод олдсонгүй. Одоогийн admin техникийн хувьд шууд бүлэг оноож чадна. UI-аар res.users үүсгэх, groups_id/active өөрчлөх, res.groups.users өөрчлөхөд ISMS audit access_change бичих hook байна; энэ нь батлах workflow-ийн оронд тооцогдохгүй.

## 2. Нэгжид хуваарилсан байдал

hr.employee.department_id → hr.department; parent_id нь нэгжийн шатлал, manager_id нь нэгжийн удирдлага; hr.employee.user_id нь ажилтан ба нэвтрэх дансны холбоос.

Current DB: 12 идэвхтэй ажилтан, 12 нь user_id холбоостой. Ректорын ажлын албанд дараах нэгжүүд харьяалагдана:

| Нэгж | Удирдлага / үндсэн гишүүн |
|---|---|
| Мэдээллийн аюулгүй байдлын алба | Доржсэмбэ CISO; Эрхэмбаяр SOC Analyst |
| Мэдээллийн технологи ба цахим засаглалын алба | Батдэмбэрэл CIO |
| Сургалтын нэгдсэн алба | Бадрал |
| Дотоод аудит ба чанарын алба | Тэлмүүн |
| Захиргаа, хүний нөөцийн алба | Энхжаргал (зохиомол) |
| МТ ба кибер аюулгүй байдлын сургууль | Түвшинбаяр (зохиомол) |

Кибер-Физик судалгааны лаборатори нь МТ ба кибер аюулгүй байдлын сургуулийн дэд нэгж; удирдагч Ганзориг (зохиомол). Administration гэсэн суурь нэгж мөн байна.

Employees → ажилтан → Department / Manager / Related User хэсгээр бүртгэлийг холбодог. HR мэдээлэл удирдах `hr.group_hr_user`, `hr.group_hr_manager` эрх current DB-д зөвхөн admin-д байна. `hr_officer` гэсэн албан тушаалтай user-д эдгээр бүлэг байхгүй; албан тушаалын текст эрх олгохгүй. Байгууллагын нэгжийн менежер байх нь өөрөө HR эсвэл ISMS удирдах эрх үүсгэхгүй.

## 3. RBAC яг юугаар ажилладаг вэ?

- User → res.groups: ямар үйлдэл хийх үүрэгтэй вэ?
- ACL: тухайн модельд унших/үүсгэх/засах/устгах эрх байна уу?
- Record rules: яг ямар бичлэгт энэ үйлдлийг зөвшөөрөх вэ?
- Model method guard: эрсдэл батлах, бодлого батлах, инцидент хаах зэрэг тусгай үйлдэлд үүрэг болон төлөвийн нэмэлт шалгалт.
- Menu groups: UI-д цэс харагдуулах. Цэс нуух нь дангаараа хамгаалалт биш.

Current ISMS нь department-bound тусгаарлалттай биш. `hr.employee.department_id` болон `isms.asset.department_id` нь бүртгэлийн холбоос; ISMS record rule-д department_id нөхцөл байхгүй. Нэгж шилжүүлэхэд groups_id, owner_id, custodian_id автоматаар шинэчлэгдэхгүй.

Бодит жишээ:
- Reporter өөрийн мэдээлсэн инцидент, батлагдсан бодлого харна.
- Asset Owner бүх хөрөнгийг уншиж чадна; зөвхөн owner_id эсвэл custodian_id нь өөртэй нь таарсан хөрөнгийг засна. Хөрөнгийн read rule-д нэгжээр эсвэл эзэмшигчээр хязгаарлаагүй.
- Asset Owner эрсдэлийг owner_id нь өөр эсвэл холбогдсон asset.owner_id нь өөр үед харна. Зөвхөн custodian байх нь risk read rule-ийн нөхцөлд байхгүй.
- Asset Owner өөрийн хөрөнгийн инцидентийг нэмэлтээр уншина.
- Analyst/CISO сургууль даяарх хөрөнгө, эрсдэлтэй ажиллах өргөн эрхтэй; CISO-д батлах тусгай эрх бий.
- Auditor нь ISMS аудитын өгөгдлийг уншина; implied Reporter эрхээр өөрийн инцидент мэдээлэх боломж мөн хадгалагддаг.

Иймээс Бадралыг өөр нэгжид шилжүүлсэн ч хуучин owner_id/эрсдэл хариуцлагыг өөрчлөхгүй бол өмнөх хандалт хэвээр үлдэнэ. Нэгжийн хилээр хамгаалах шаардлагатай бол тусдаа department-based record rules, эрх шилжүүлэх процесс хэрэгтэй; одоо хэрэгжсэн мэт тайлагнахгүй.

Campus academic модуль тусдаа дүрэмтэй: оюутан өөрийн profile/дүн; багш өөрт оноосон хичээл ба оюутны дүн; registrar/auditor өргөн унших хүрээ. Энд ч ISMS CISO байх нь автоматаар campus registrar болохгүй.

## 4. Ажилтан ажлаас гарвал

POL-02 §4-ийн зорилтот SLA: шилжихэд хуучин эрхийг24цагт хураах; чөлөөлөгдөхөд бүх системийн эрх/сесс/API/VPN-г ажлын4цагт идэвхгүй болгох. Эдгээр хугацааг хэмжиж автоматаар гүйцэтгэх бүрэн JML workflow одоогоор алга; SoA5.18 ч partial гэж бүртгэгдсэн.

Зөв дараалал:
1. HR ажлаас чөлөөлөх/гэрээ дуусах шийдвэр, хүчинтэй цагийг бүртгэж CISO/CIO-д мэдэгдэнэ.
2. CIO эсвэл admin Settings → Users & Companies → Users → хэрэглэгч → Action/gear → Archive хийж нэвтрэх дансыг active=False болгоно.
3. Кодын түвшинд идэвхгүй данс шинэ нэвтрэлт хийхгүй; Odoo session token active талбарыг агуулдаг тул дараагийн session validation дээр хуучин token таарахгүй. API key authentication ч user.active нөхцөл шалгадаг. Дэлгэц дээр өмнө нь ирсэн өгөгдөл, татсан PDF арилна гэсэн үг биш; идэвхтэй P2P media шууд зогсохыг энэ шалгалтаар туршаагүй.
4. API keys-ийг revoke/remove хийнэ. Archive нь түлхүүрийн бүртгэлийг устгахгүй; дараа нь user unarchive хийхэд хуучин key сэргэж ашиглагдах эрсдэлийг тусад нь хаана.
5. Хөрөнгө owner/custodian, эрсдэл owner, нээлттэй инцидентийн assignee, project tasks, controls responsible-ийг шинэ ажилтанд шилжүүлнэ; дамжуулалтыг нотолгоотой хадгална.
6. Employees дээр HR бүртгэлийг архивлаж departure date/reason тэмдэглэнэ. Installed hr.employee.toggle_active болон hr.departure.wizard нь холбоотой res.users.active-г өөрчилдөггүй. Employee Archive дангаараа login-ийг хаахгүй.
7. Moodle, email, VPN, GitHub зэрэг тусдаа систем байвал тус бүрд эрх цуцална. Odoo archive тэдгээрийг автоматаар цуцлах connector одоогийн addon-д байхгүй.
8. Audit log дээр хэн, хэзээ groups/active өөрчилснийг шалгаж HR шийдвэр, шилжүүлсэн ажлын жагсаалттай тулган хаана. Archive мэдээллийн түүхийг хадгална; данс устгахыг үндсэн арга болгохгүй.

Түр түдгэлзүүлэхэд мөн user archive ашиглаж болно. Unarchive нь хадгалагдсан бүлгийг автоматаар цэвэрлэхгүй тул дахин нээхээс өмнө эрхийг дахин хянана.

## 5. Нотолгооны эх сурвалж

- policies/02-access-control-policy-ISSP.md §3–4: зорилтот бодлого; хэрэгжилтийн баталгаа биш.
- odoo/addons/university_isms/security/ir.model.access.csv: ACL.
- odoo/addons/university_isms/security/isms_security.xml: үүрэг, implied groups, record rules.
- odoo/addons/university_isms/models/asset.py: department/owner/custodian холбоос.
- odoo/addons/university_isms/models/res_users.py: create/group/active audit hooks.
- odoo/addons/campus_university/security/campus_security.xml: academic data scope.
- Installed Odoo18 base/models/res_users.py: session active талбар, API active check.
- Installed Odoo18 hr/models/hr_employee.py, hr/wizard/hr_departure_wizard.py: HR archive нь user archive биш.
- Current DB read-only queries: department hierarchy, employee/user links, live ir.rule, admin/HR group membership.

Энэ шалгалтаар automatic offboarding-ийн end-to-end тест хийгээгүй, хэрэглэгчийн эрх/бүртгэл өөрчлөөгүй.
