# Formula University LAN HTTPS ба camera/microphone

2026-11-18. HTTP LAN origin дээр camera/mic хаагдсан тул локал HTTPS reverse proxy нэмэв.

## Нэвтрэх

`https://172.16.151.135:8443/web/login?db=orgil_isms`

Discuss: `https://172.16.151.135:8443/odoo/discuss?active_id=discuss.channel_1`

## Төхөөрөмж бүрд нэг удаа хийх

1. `FormulaUniversity_LAN_CA.crt` нийтийн CA сертификатыг багийн төхөөрөмжид хуулна. Энэ нь зөвхөн өөрсдийн локал coursework серверийн CA; тухайн төхөөрөмжийн trust store-д итгэмжлэхийг хэрэглэгч өөрөө хийнэ. CA нэр нь **Formula University Coursework LAN CA**. `ca.key`, `server.key` файлуудыг хэзээ ч тараахгүй.
2. Helium/Chrome-ийн Settings дотор certificate гэсэн үгээр хайж, сертификат удирдах хэсгийг нээнэ. Local/Trusted/Authorities сертификатын хэсэгт энэ CA-г import хийж website/server authentication-д итгэмжилнэ. Хэрэв browser нь OS trust store ашигладаг бол үйлдлийн системийн Trusted Root Certification Authorities хэсэгт импортлоно. Байршлын нэр нь browser/OS-оос хамаарна. Server-ийн leaf certificate биш CA файлыг импортлоно.
3. Хөтчийг бүрэн хааж нээнэ. HTTPS хаягт certificate warning байхгүйг шалгана. Warning хэвээр бол trust import-ийг засна; browser warning-ийг алгасах эсвэл HTTPS хамгаалалтыг унтраах аргыг хэрэглэхгүй.
4. Шинэ HTTPS origin дээр нэвтэрч Discuss call-д орно. Camera/Microphone хүсэлт гарвал хэрэглэгч өөрөө Allow сонгоно. Site settings өмнө Block байсан бол шинэ HTTPS хаягийн camera/mic тохиргоог Ask/Allow болгож, OS privacy болон төхөөрөмжийн холболтыг шалгана.
5. Энэ өөрчлөлт HTTPS ба WebSocket замыг баталгаажуулсан. Бүх төхөөрөмжийн camera/mic зөвшөөрөл болон хоёр талын бодит аудио/видеог хэрэглэгчид өөрсдөө туршина; сүлжээний WebRTC/NAT хязгаарлалт байвал тусад нь шалгана.

## Асаах

`biydaalt/odoo/` дотор `./scripts/start-lan.sh`. Скрипт private LAN IP, CA/server сертификат, Odoo proxy mode, HTTPS контейнерийг бэлтгэнэ. HTTP 8069 нь loopback дээр, HTTPS 8443 нь private LAN IP дээр; DB хост порт нээгээгүй. IP солигдвол скриптийг дахин ажиллуулж шинээр хэвлэсэн HTTPS хаягийг ашиглана. CA өөрчлөгдөөгүй бол дахин trust import хийх шаардлагагүй.

## Баталгаажуулалт

- Локал CA ашигласан strict TLS/IP verification + login HTTP 200 PASS. Certificate verification-ийг унтраагаагүй.
- HTTPS `/websocket?version=18.0-7` Upgrade → HTTP 101 PASS.
- `nginx -t` PASS; Odoo болон PostgreSQL ажиллаж байна.
- TLS private material: `evidence/private/tls/lan/`, gitignore-д хасагдсан. Nginx-д зөвхөн server.crt/server.key read-only mount хийсэн; CA private key mount хийгээгүй.
- Odoo өгөгдлийг импорт/дахин үүсгэх, хэрэглэгчийн нууц үг эсвэл role өөрчлөх үйлдэл хийгээгүй.
- Хост болон бусдын төхөөрөмжийн системийн trust store-г автоматаар өөрчлөөгүй.

Хэрэгцээ дуусвал төхөөрөмжөөс **Formula University Coursework LAN CA** trust entry-г устгаж болно.

## Discuss: өөрийн дүрс харагдаад бусдын дүрс харагдахгүй байх (TURN)

2026-11-18: HTTPS/WebSocket ажилласан ч client-to-client медиа холболт амжилтгүй гэсэн хэрэглэгчийн мэдэгдлээр шалгав. Odoo-д mail.ice.server 0 байсан; дуудлагын signaling HTTP200, өөр өөр partner бүхий 4 session байсан. Иймээс шууд ICE зам хаагдах тохиолдлын fallback болох authenticated LAN TURN relay нэмэв. Wi-Fi client isolation эсэхийг бүрэн тогтоогоогүй.

- Контейнер `isms-turn`, image `coturn/coturn:4.19.1-r0`, host network.
- Зөвхөн LAN IP `172.16.151.135`, listener TCP/UDP3478; relay UDP49160–49200.
- Odoo mail.ice.server: нэг STUN, TURN UDP ба TURN TCP гэсэн 3 мөр. Кейсийн хэрэглэгчдийн role/нэвтрэх нууц үг өөрчлөөгүй.
- Урт хугацааны TURN authentication; random secret нь `evidence/private/turn/credentials.json`, config нь ижил private хавтаст; Git/archive-д оруулахгүй. Нууц үггүй public relay биш.
- Loopback болон multicast peer-ийг хориглосон. TLS8443 болон Odoo loopback8069 хэвээр.
- `scripts/configure-lan-turn.py` нь start-lan.sh-ийн runtime lock дотор ICE өгөгдлийг шинэчилдэг. IP солигдвол start-lan.sh дахин ажиллуулна; скрипт TURN контейнерийг restart хийж шинэ listener IP-г идэвхжүүлнэ (ажиллаж буй дуудлагыг тасалж болох тул дуудлагын өмнө ажиллуулна).

Серверийн шалгалт: turnutils_uclient client-to-client UDP/TCP туршилт тус бүр 20 илгээсэн,20 хүлээж авсан,0 lost; tool нь эхний send dropped2 гэж давхар мэдээлсэн. Энэ нь нэг хост дээрх relay path шалгалт; хэрэглэгчдийн хоёр төхөөрөмжийн бодит camera/mic дуудлага амжилттай болсны баталгаа биш.

Хэрэглэгч бүр дуудлагаас гарч HTTPS хуудсаа Ctrl+Shift+R хийж, өөрийн account-аар нэг өрөөний дуудлагад дахин орно. Шинэ ICE тохиргоог шинэ join үед авна.

## RTC логт no transceiver available when updating direction

Хэрэглэгчийн бодит `RtcLogs_2026-ll-18_19-06.json` дээр hasTurn=true боловч peer26/27/29/30 бүгд updateDownload дахь transceiver байхгүй алдаагаар recovery хийсэн. Энэ нь TURN байгаагаар өөрөө шийдэгдэхгүй frontend negotiation дарааллын асуудлыг харуулсан.

`campus_rtc_fix` addon нь `PeerToPeer._createPeer`-ийг Odoo patch utility-аар өргөтгөж audio/camera/screen дарааллын transceiver-үүдийг synchronous үүсгэнэ; эхний negotiationneeded болон updateDownload-оос өмнө бэлэн болгоно. enableStreaming=false болон өмнө үүссэн slot-уудыг хадгалж, одоогийн upload track, per-peer direction-ийг ашиглана. Odoo upstream файлыг өөрчлөөгүй.

Суулгах: `scripts/odoo-cli.sh -i campus_rtc_fix --without-demo=all`. Суулгасан; шинэ `web.assets_web` багцад patch орсныг authenticated HTTPS fetch-ээр баталсан. Backend update үед контейнерийн IP солигдоход nginx хуучин IP cache-аас 502 өгсөн тул Docker DNS resolver127.0.0.11 + runtime upstream lookup хийж засав. HTTPS login200 болон шинэ frontend asset PASS.

Regression: яг upstream PeerToPeer болон patch utility-г mocked RTCPeerConnection-тай ажиллуулж baseline алдааг давтсан, patch дараа гурван slot, track, direction, streaming-disabled4case PASS. Энэ нь actual browser хоёр төхөөрөмжийн media test биш; 47nativeтестийн тоонд нэмээгүй. Evidence: `evidence/tests/rtc-initialization-20261118.json`.

Хүн бүр дуудлагаас гарч Ctrl+Shift+R хийгээд өөр өөр account-аар нэг өрөөнд дахин орно. Хэрэв алдаа үлдвэл шинэ RTC лог татаж, хуучин логтой огноогоор ялган оношлоно.

## 2026-11-18 — Certificate trust ба realtime connection lost
Хэрэглэгч HTTPS certificate анхааруулгыг **Advanced → Proceed**-ээр алгасаж байсан гэж баталсан. Энэ нь CA-г trust-д суулгасан гэсэн үг биш. 20:25 RTC логт идэвхтэй call байхгүй (`peers: []`). Browser worker bundle GET200 байсан ч HTTPS үед browser User-Agent бүхий `/websocket` upgrade серверт ирээгүй; Python authenticated WSS subscribe амжилттай. Browser certificate rejection нь гол сэжиг; browser дахин нээсний дараах баталгаа шаардлагатай.

Энэ хостын `/home/sembee/.pki/nssdb`, `/home/sembee/.local/share/pki/nssdb` хоёуланд CA байгаагүй. `certutil -A -t "C,,"`-ээр Formula University Coursework LAN CA-г SSL server trust-д суулгаж, импортын certificate SHA256 fingerprint таарсныг шалгасан. Өмнөх cert9.db сангуудын SQLite backup `evidence/private/tls/nss-backup-20261118/`-д хадгалсан. Хувийн түлхүүр хуваалцаагүй.

Бусад төхөөрөмж:
1. `https://172.16.151.135:8443/formula-university-lan-ca.crt`-ээс **зөвхөн public CA** татна. Nginx exact location-оор үйлчилнэ; directory listing байхгүй.
2. Chrome/Chromium/Helium: Settings → Privacy and security → Security → Manage certificates → Authorities / Local certificates → Trusted certificates → Import. Root CA-г websites/SSL-д trust хийнэ. macOS browser OS store ашиглаж байвал Keychain Access-д CA-г импортлоод SSL trust-ийг тохируулна.
3. Browser-ийг бүрэн хааж дахин нээнэ. Odoo HTTPS нь certificate анхааруулгагүй нээгдэх ёстой. Proceed эсвэл insecure-origin flag нь CA trust-ийг орлохгүй.
4. Realtime connection lost арилсан эсэх, хоёр тусдаа account-тай дуудлагын дүрс/дуу ирэхийг шалгана.

CA certificate SHA256 fingerprint:
`81:52:8B:EB:31:D0:05:10:55:63:DD:23:CF:03:E8:F7:E4:6B:33:98:6E:74:8C:CF:F7:29:12:33:62:0F:93:3A`

Хостын trust-ийг дараа нь буцаах шаардлагатай бол тухайн NSS сан бүр дээр `certutil -D -d sql:<NSS_DB_DIRECTORY> -n "Formula University Coursework LAN CA"` хэрэглэнэ. Бусад certificate-ийг хөндөхгүй.

Нотолгоо: `evidence/tests/lan-ca-trust-20261118.json`. End-to-end call хэрэглэгчийн баталгааг хүлээж байна.
