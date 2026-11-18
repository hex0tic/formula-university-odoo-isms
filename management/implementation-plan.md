# Хэрэгжүүлэх төлөвлөгөө

## Зорилго ба эцсийн бүтэц

`case.md`-ийн академик бүртгэл ба хамтарсан лабораторийн кейсийг Odoo 18 Community дээр нэг орчин, нэг canonical dataset, давхцалгүй файлын эзэмшлээр хэрэгжүүлнэ. Албан шаардлагыг requirements.md-ийн ID-аар мөрдөнө.

```text
biydaalt/
  БД төсөл_ Odoo ERP-ISO27001 26-27А.pdf   эх заавар, өөрчлөхгүй
  management/                           удирдлага, харилцаа, төлөвлөгөө
  odoo/
    docker-compose.yml, config/, scripts/
    addons/campus_university/            академик үйлчилгээ (Codex)
    addons/university_isms/              ISMS domain (Deployment агент)
    addons/campus_isms_bridge/           audit/asset/incident интеграц
  data/                                 CSV/JSON canonical synthetic data
  policies/                             3 үндсэн ISMS бодлого (+ optional AUP)
  evidence/                             raw logs, tests, screenshots, manifest
  reports/                              эцсийн тайлан ба танилцуулга
```

## Үе шат ба dependency

| Үе | Ажил | Эзэн | Дууссан гэж үзэх нөхцөл |
|---|---|---|---|
| P0 | Заавар, өмнөх хичээл, team, VM inventory унших | Codex/Sophia/Infra | requirements, course-review, glossary, team, environment-audit |
| P1 | 3 агентын proposal-ийг нэгтгэх, case ба аргачлал тогтоох | Codex + Deployment агент/OpenCode | case, architecture, D01–D07; бүх тал ижил нэр/тоо/матриц ашиглах |
| P2 | Existing runtime reuse; Odoo/DB суулгах | Deployment агент | ажилладаг login, version/digest, loopback, isolated data, commands |
| P3a | Academic module: 6 model, views, rules, approval | Codex | install, security/workflow tests, demo flow |
| P3b | ISMS models, Inventory/Project/Helpdesk, RBAC, audit | Deployment агент | ≥5 role, immutable UI audit, incident 5 stages, core integration |
| P3c | Assets, risks, controls/SoA, policy dataset | OpenCode | schema нийцсэн UTF-8 CSV/JSON, stable codes, ≥15/12/25 |
| P4 | Нэг dataset импортлох, campus ба audit bridge холбоно | Deployment агент/Codex | idempotent import, no duplicate codes, actual actor/change traces |
| P5 | Allow/deny, incident transitions, matrix25, backup/restore шалгах | Codex + бүгд | бодит test logs, screenshot, evidence manifest |
| P6 | Report 20–30p, slides8–12, demo10–15min | Баг | бүх зураг бодит, нэр/тоо/claim таарсан, эх сурвалж ба AI disclosure |

P3a/P3b/P3c зэрэг явна. DB install/update, import, screenshot төлөв өөрчлөх ажиллагааг `management/runtime.lock`-аар дарааллуулна. Бусад агент code бичих ажлаа үргэлжлүүлж болно.

## Хэрэгжүүлэх хамгийн бага бүрэн урсгал

1. Registrar академик үндсэн бүртгэл үүсгэнэ. Lecturer хүсэлт гаргана.
2. Self-approval хориглогдоно; өөр registrar батална; revision өснө.
3. Student зөвхөн өөрийн мэдээллийг харна; auditor засахгүй уншина.
4. Grade ledger asset нь integrity risk ба A.5.3/A.8.3/A.8.15-тэй холбогдоно.
5. Incident бодитоор таван үе шат дамжиж actor/time, resolution/lesson-тэй хаагдана.
6. SoA нь сонгосон25 хяналтын applicability, status, justification, owner, evidence-г харуулна.

## Өгөгдөл ба дүрэм

- Сургалтын тоо, нэр, инцидент зохиомол; бодит оюутны регистр, утас, эрүүл мэндийн мэдээлэл хэрэггүй.
- Owner ба custodian-ыг ялгана. Asset valuation max(C,I,A), risk RM-01 lookup-ийг тусад нь хэрэглэнэ.
- Inherent/residual risk хоёр өөр; residual proposal-г бодитоор хэмжсэн үр дүн гэж нэрлэхгүй.
- High/medium risk acceptance-г эрх бүхий эзний шийдвэртэй холбож, зөвхөн оноог бууруулаад acceptance болсон гэж үзэхгүй.
- CSV/JSON ба Odoo дахь code/reference-г харьцуулж импортын дараа шалгана.

## Тест ба evidence төлөвлөгөө

| Шалгалт | Шаардлага | Нотолгоо |
|---|---|---|
| Native Odoo install ба registry | R01/U06 | module version/state, CLI log |
| Independent approval ба re-approve deny | R09/U06 | TransactionCase + UI form |
| Self-approval / direct write / forged context deny | R09 | error + unchanged score/revision |
| Student/lecturer record isolation | R09 | search/read deny ба allowed own records |
| Stale request reject | U06 | two requests, one approval, revision unchanged after second |
| Matrix25 | R05 | 25 input/result comparison |
| Asset Inventory ба control/risk links | R04/R06 | database check + UI screens |
| Helpdesk/incident 5-stage execution | R07 | actual transition timestamps + UI |
| Audit write/role/action trace ба tamper deny | R11 | actor/time/model/change, ordinary-user write/unlink denied |
| Backup+filestore restore | R01/R11 | actual backup/restore command log + counts |

## Баримтжуулалт ба тайлан

Тайлангийн хэсгүүд requirements R15-ын дарааллаар байна. Код/суулгалтын бүх дотоод үйлдлийг академик тайланд хуулбарлахгүй; хавсралт ба ажиллагааны зааварт шаардлагатай командыг оруулна. Албан хуваарь нь тайлан/танилцуулга 12-р долоо хоногийн эцэс, demo13-р долоо хоног; календарийн баталгаагүй огноо зохиохгүй. Багийн 5 хүний үүргийн санал ба бодит гүйцэтгэлийг ялгаж бүртгэнэ.
