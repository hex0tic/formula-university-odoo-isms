# Odoo ERP их сургуулийн бие даалт: орчны зөвхөн унших аудит

- Аудитор: Infrastructure analyst, Codex туслах агент.
- Аудитын өдөр: 2026-11-16, Asia/Ulaanbaatar (UTC+08:00).
- Үндсэн ажиглалт: 10:38-10:45; тайлан бичсэн: 2026-11-16T10:47:45+08:00.
- Бие даалтын үндсэн зам: `/home/sembee/University-coursework/3A_semester/Мэдээллийн аюулгүй байдлын засаглал ба менежмент/biydaalt`.
- Эзэмшил: зөвхөн `management/environment-audit.md`; `messages.md`, `worklog.md`-д `fcntl.flock` түгжээтэй append хийх эрхтэй.

## 1. Шийдвэр гаргахад хэрэгтэй дүгнэлт

**Байгаа Docker Engine + Compose runtime-ийг ашиглаж, бие даалтад зориулсан тусдаа Odoo Community + PostgreSQL төсөл байгуулах нь боломжтой сонголт.** Шинэ Ubuntu VM, OS ISO татах хэрэгцээ энэ аудитаар тогтоогдоогүй. Registry хайлтаар Odoo-д тохирох verified available Linux server VM олдоогүй боловч хост дээр ажиллаж буй Docker болон PostgreSQL 16-ийн cached image байна.

Техникийн санал: `odoo:18.0` Community official image + cached `postgres:16-alpine`. Odoo 18-ын албан баримт PostgreSQL 12 ба түүнээс дээш хувилбар дэмжинэ гэж заасан тул PostgreSQL 16 нь хувилбарын шаардлагыг хангана [S1, S2]. Энэ нь суулгаж туршсан үр дүн биш; custom module/OCA compatibility, image-ийн гарал ба шинэчлэлт, эхлэлт, нөөцлөлтийн шалгалтыг deployment эзэн гүйцэтгэнэ. 18.0 бол санал болгосон суурь бөгөөд хамгийн сүүлийн Odoo хувилбар гэсэн мэдэгдэл биш. Эцсийн хувилбарыг Coordinator ба deployment эзэн батална.

Хязгаарлах гол хүчин зүйл нь root filesystem-ийн **97% ашиглалт**. `/`, `/home`, `/var/lib/docker` нэг partition дээр, харин `/data` тусдаа бөгөөд илүү сул зайтай. PostgreSQL data, Odoo filestore, backup-д `/data/sembee/` дотор шинээр, зөвхөн энэ бие даалтын эзэмшлийн зам сонгохыг санал болгоно. Docker image/layer ба default log нь daemon root талд зай эзэлсээр байх тул `/data` дээр bind mount хийх нь root-ийн зайны асуудлыг бүрэн шийдэхгүй.

Энэ аудит VM/container үүсгээгүй, image татаагүй, үйлчилгээ асаагаагүй/зогсоогоогүй, group reserve хийгээгүй, registry өөрчлөөгүй, existing disk/volume шилжүүлээгүй, cleanup/prune хийгээгүй. Хуучин PostgreSQL data volume болон өөр хичээлийн Ubuntu container-ийг ашиглахаар санал болгоогүй; дахин ашиглах объект нь Docker runtime ба тохирох cached image layer юм.

## 2. Эх сурвалж ба ажлын хил

Уншсан бодлого:

- `/home/sembee/.codex/skills/shared-lab-vms/SKILL.md`.
- `/home/sembee/.local/share/lab-vms/POLICY.md`.
- `/home/sembee/AGENTS.md`, `/home/sembee/AGENTS.local.md`.
- Багийн `management/README.md`, `assignments.md`, `messages.md`, `worklog.md`.

Coordinator аль хэдийн `lab-vms refresh` ажиллуулсан тул давтан refresh хийгээгүй. Ашигласан registry-ийн `updated_at`: **2026-11-16T02:37:13.801833+00:00**, Улаанбаатарын цагаар **10:37:13.801833+08:00**.

Мэдээллийн эх сурвалж нь бодит CLI/stdout, `/proc`-ийн сонгосон non-secret metadata, сонгосон Docker inspect талбар, OS release файл. `.env`, password/token, хувийн түлхүүр, database-ийн өгөгдөл, container environment эсвэл Odoo credential config-ийг уншаагүй. Docker inspect-ийг бүхэлд нь хэвлээгүй; process argv-г бүхэлд нь хэвлээгүй. `/etc/os-release`-ийг Docker archive stdout-оос санах ойд уншсан бөгөөд local extract файл үүсгээгүй.

## 3. Registry, media болон lease: E01

### 3.1 Хайлт

Бүх `find`/`media` команд exit code 0; тааралтгүй үед `found: false`, `candidates: []` эсвэл `sources: []` буцсан.

| Командын шүүлтүүр | Бодит үр дүн |
|---|---|
| `find --role odoo` | 0 candidate |
| `find --os linux` | 0 candidate |
| `find --os ubuntu` | 0 candidate |
| `find --os debian` | 0 candidate |
| `find --role linux` | 0 candidate |
| `find --role database` | 0 candidate |
| `find --role container` | 0 candidate |
| `find --role web` | 0 candidate |
| `find --role postgres` | 0 candidate |
| `find --os kali` | 1 candidate: `m06-kali-attacker`, guest-unverified, leased |
| `find --role server` | 3 Windows Server candidate; Linux Odoo server reuse-д сонгоогүй |
| `media --os ubuntu`, `media --os debian`, `media --os linux` | тус бүр 0 source |
| `media` | Kali 2026.2 archive; Windows Server 2022 / Windows 11 / Windows 10 ISO; бүртгэлтэй Server 2016 ISO нь `exists: false` |

Registry нийт **58 VM/disk илрүүлэлт**, үүнээс **11 id-тай curated entry**, **6 guest-verified entry**, **36 empty-disk placeholder**. 58 гэдэг нь 58 ажиллах VM гэсэн утга биш. Шүүлтүүр нь бүх Linux distribution-ийг нэгтгэдэг taxonomy гэж үзээгүй; Ubuntu, Debian, Kali болон role-уудыг тус тусад нь хайсан.

Registry scan warning: `/home/sembee/University-coursework`, `/home/sembee/Documents` дотор зарим зам уншигдахгүй байсан тул inventory бүрэн байх баталгаа байхгүй.

### 3.2 Сонголтод нөлөөлөх candidate

| Candidate / group | Registry ба filesystem нотолгоо | Шийдвэр |
|---|---|---|
| `m06-kali-attacker` / `m06-lab` | Kali 2026.2; `guest-unverified`; disk `/data/sembee/ceh-vms/kali/kali-linux-2026.2-qemu-amd64.qcow2`; registry `backing_path: null`, virtual capacity 86,000,000,000 B; lease байна | Attacker course-run, баталгаажсан ерөнхий server биш. Өөрчлөхгүй |
| `m06-server2016-auditor` / `m06-lab` | Windows Server 2016 Core, `guest-verified`; 42,949,672,960 B raw disk; lease байна | Windows course state хадгална; Odoo Linux орчинд сонгохгүй |
| `m06-server2016-gui` / `m06-lab` | Windows Server 2016 GUI, `guest-verified`; 42,949,672,960 B raw disk; lease байна | Дээрхтэй адил |
| `protocols-gui-server` / `protocols-gui` | Windows Server 2022 GUI; `guest-verified`; lease null; registry `backing_path: null`, virtual capacity 68,719,476,736 B; canonical-existing | Lease байхгүй нь ашиглах зөвшөөрөл биш. OS/курсийн үүрэг зөрөх тул энэ төсөлд сонгохгүй |
| Windows AD, Cisco router/firewall, unknown GNS3 disk | Өөр topology/course; зарим нь lease-тэй, unknown/empty disk нь ready environment биш | Хэвээр хадгална |

Эдгээр disk chain-ийн утгыг coordinator-ийн refresh-ээс үүссэн registry metadata-аас уншсан; live `qemu-img info` давтан хийгээгүй (`qemu-img` executable PATH-д алга). VM асаах, guest рүү нэвтрэх, firmware/TPM state-г өөрчлөх үйлдэл хийгээгүй. Энэ аудитаар тохирох verified available Linux guest сонгогдоогүй.

### 3.3 Lease snapshot

| Group | Owner | reserved_at (UTC, эх утга) |
|---|---|---|
| `m07-lab` | `apeiron-ceh-m07-20261103` | `2026-11-04T06:26:50.333140+00:00` |
| `m06-lab` | `user-start-kali-20261104` | `2026-11-04T14:49:36.844584+00:00` |
| `cisco-router` | `fnsa333-biydaalt-20261111` | `2026-11-11T07:07:47.028922+00:00` |
| `ad-lab` | `fnsa333-biydaalt-20261111` | `2026-11-11T07:07:46.636766+00:00` |
| `cisco-firewall` | `fnsa333-biydaalt-20261111` | `2026-11-11T07:07:47.373665+00:00` |

Хуучин огноотой lease-ийг stale гэж үзэж цэвэрлээгүй. `/proc` snapshot-д QEMU process таараагүй нь lease-ийг хүчингүй болгох үндэслэл биш.

## 4. Хост ба бодит нөөц: E02

| Үзүүлэлт | Ажигласан утга / команд |
|---|---|
| OS | `/etc/os-release`: `Arch Linux`, `ID=arch` |
| Kernel / architecture | `uname -srmo`: `Linux 7.2.15-arch1-1 x86_64 GNU/Linux` |
| CPU | Intel Core 7 150U; `lscpu`: 12 online logical CPU, VT-x |
| RAM total | `/proc/meminfo`: `16045616 kB` = ойролцоогоор 15.30 GiB |
| RAM available | 10:42:32 snapshot: `3732484 kB` = ойролцоогоор 3.56 GiB; эхний `free -h`: 4.2 GiB available |
| Swap | total `41576952 kB`; free `30556748 kB` буюу ойролцоогоор 10.51 GiB used (10:42:32) |
| Load average | `3.35 3.14 2.59` (1/5/15 минут, 10:42:32) |
| Memory pressure | `/proc/pressure/memory`: some avg10=1.44, avg60=1.40, avg300=0.71; full avg10=1.44, avg60=1.39, avg300=0.69 |
| Хэрэглэгч | uid/gid 1000 `sembee`; docker group 965 |
| KVM | `/dev/kvm` байна; audit хэрэглэгч read/write боломжтой; ашиглаагүй |

`df -B1` snapshot **2026-11-16T10:42:32+08:00**:

| Зам | Device / filesystem | Total bytes | Used bytes | Available bytes | Use% |
|---|---|---:|---:|---:|---:|
| `/` | `/dev/nvme0n1p7`, btrfs | 349069901824 | 335166967808 | 12882636800 | 97% |
| `/home/sembee/University-coursework` | мөн device, `/home` subvolume | 349069901824 | 335166967808 | 12882636800 | 97% |
| `/var/lib/docker` | мөн device, `/var` subvolume | 349069901824 | 335166967808 | 12882636800 | 97% |
| `/data` | `/dev/nvme0n1p5`, btrfs | 149999845376 | 99176763392 | 49127845888 | 67% |

Available bytes-ийг GiB-д хөрвүүлэхэд root **ойролцоогоор 12.00 GiB**, `/data` **45.75 GiB**. Эхний `df -h`-ийн `13G`/`46G` нь дээш тоймлосон харуулалт; яг 13 GiB сул гэсэн утга биш. RAM/disk нь snapshot бөгөөд бусад агентын ажлаар өөрчлөгдөнө.

`findmnt`: `/var/lib/docker` нь `/dev/nvme0n1p7[/@var]`; `/data` нь тусдаа `/dev/nvme0n1p5`. `/data/sembee` нь `sembee:sembee`, `drwx------`; шинэ assignment-owned data directory байгуулах filesystem эрх боломжтой гэж үзсэн, write probe хийгээгүй.

## 5. Docker / Podman: E03

- Docker client/server: **29.9.3**, server API **1.56**.
- `docker compose version`: **Docker Compose version 5.7.1**.
- `docker` болон `docker-compose` executable байна; `podman`, `podman-compose` олдоогүй.
- Docker daemon: Arch Linux / x86_64, CPU 12, `MemTotal=16430710784`, storage driver `overlayfs`, `DockerRootDir=/var/lib/docker`.
- `/run/docker.sock` (`/var/run/docker.sock`): mode `0660`, uid 0, gid 965; sembee хэрэглэгч socket ашиглан query амжилттай хийсэн.
- `docker.service`: active/running/enabled, MainPID **717**.
- `containerd.service`: active/running, MainPID **675**.
- `/proc`: дээрх daemon, 4 containerd-shim, 2 docker-proxy харагдсан. Odoo/PostgreSQL/QEMU нэртэй process болон сонгосон Python process-ийн Odoo argv тааралт харагдаагүй.
- Docker нийт **59 container**, **4 running**, **53 image**. Runtime daemon ажиллаж буй нь бодитоор батлагдсан; шинэ Odoo stack ажилласан гэж дүгнээгүй.

### 5.1 Ажиллаж буй container

| ID | Нэр | Image | Порт / ажиглалт |
|---|---|---|---|
| `d22ea49b2677` | `nyoom_local-app-1` | `nyoom_local-app` | container `3000/tcp`, host publish харагдахгүй |
| `e6ec560b73c1` | `nyoom_local-bot-1` | `nyoom_local-bot` | container `3001/tcp`, host publish харагдахгүй |
| `ed607c5ecf4d` | `nyoom_local-edge-1` | `nyoom_local-edge` | `0.0.0.0:8080->8080/tcp`, `[::]:8080->8080/tcp` |
| `c6985d74dd6b` | `lab2-arch-php-1` | `lab2-arch-php` | container `9000/tcp`; healthy |

`docker stats --no-stream` тухайн агшинд дээрх container-ууд 7.230 / 9.234 / 11.68 / 2.809 MiB memory харуулсан; нийт хостын өндөр RAM хэрэглээг зөвхөн эдгээр дөрвөн container үүсгэсэн гэж дүгнээгүй. Container/service-д ямар ч өөрчлөлт хийгээгүй.

### 5.2 Cached image ба зориулалт

| Image | Local ID (товч) | Inspect size, bytes | Ашиглах санал |
|---|---|---:|---|
| `postgres:16-alpine` | `721873c34ceb` | 419395599 | Odoo 18-д зориулсан ШИНЭ database container-ийн image layer-ийг дахин ашиглах candidate |
| `postgres:18.1-alpine` | `aa6eb304ddb6` | 402244356 | Байгаа ч энэ аудитаар Odoo 18 stack-д сонгоогүй |
| `ubuntu:24.04` | `fe81560990fa` | 115474792 | General Linux base image; бэлэн Odoo/server VM биш |
| `debian:stable-slim` | `a717a3346973` | 116495927 | General Linux base image; stable tag-ийг OS version гэж баталгаажаагүй |
| `postgis/postgis:16-3.4` | `44126d872ac9` | CLI reported 855 MB | Өөр төсөлд ашигласан; Odoo-д PostGIS шаардлагатай гэсэн нотолгоо алга |
| Odoo repository/tag | — | — | Local image жагсаалтад тааралтгүй |

`postgres:16-alpine` local metadata:

```text
ID=sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
RepoDigests=[postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea]
Created=2026-09-17T21:31:24.32976807Z
OS=linux
Arch=amd64
Config.Volumes={/var/lib/postgresql/data:{}}
```

Энэ digest нь **local inspect-ээс ирсэн**; алсын registry-тэй тулгаж гарал/гарын үсэг/patch currency-г батлаагүй. Энэ image-ээр шинэ database эхлүүлж хувилбар query/test хийгээгүй. Image layer reuse нь хуучин database data volume reuse гэсэн утга биш.

### 5.3 Existing Linux/database candidate-ийг асаалгүй шалгасан нь

- `coursework-lab7-ubuntu-20261108`, ID `053116a3db12`, image `lab7-redo-ubuntu:20261108`: exited, PID=0, NetworkMode=none. `/etc/os-release` файлын бодит агуулга `Ubuntu 24.04.5 LTS`, `VERSION_ID=24.04`, codename noble. Wireless security Lab7-ийн `evidence/lab7-redo-20261108` writable болон `src` read-only bind mount-тай.
- `lab7`, ID `caee5d03ae57`, image `lab7-ubuntu:1`: exited, PID=0, NetworkMode=host. Бодит `/etc/os-release` мөн `Ubuntu 24.04.5 LTS`. Wireless security Lab7 root `/lab` руу writable bind mount-тай.
- Дээрх OS файлыг `docker cp -L CONTAINER:/etc/os-release -` stdout tar-оос санах ойд уншсан. Container-ийг start/exec хийгээгүй. Filesystem OS батлагдсан ч healthy boot/service батлагдаагүй; өөр хичээлийн data/evidence учир Odoo болгохгүй.
- `cygnus-dev-postgres-1`, ID `82f477572473`, image `postgres:18.1-alpine`: exited, PID=0, `cygnus-dev_default` network. `cygnus-dev_postgres-data` volume `/var/lib/postgresql` руу mount хийсэн, Cygnus postgres-init bind mount-тай. Хуучин volume-д database query/file read хийгээгүй; Odoo руу холбохгүй.
- `beebee-test-db`, `beebee-sec-db` нь `postgis/postgis:16-3.4`, exited. GNS3.APP-DB нь course-specific tools image, exited; нэр нь бэлэн PostgreSQL server гэдгийг батлахгүй.

Docker storage snapshot:

```text
TYPE           TOTAL ACTIVE SIZE      RECLAIMABLE
Images         53    29     27.14GB   6.186GB (22%)
Containers     59    4      538.4MB   452.1MB (83%)
Local Volumes  29    6      1.994GB   1.466GB (73%)
Build Cache    37    0      9.58GB    335.2MB
```

Reclaimable гэдэг нь устгах зөвшөөрөл биш. Нэг ч prune/delete/cleanup хийлгүй хадгалсан.

## 6. Existing Odoo service/source/config: E04

- `docker ps -a`-ийн name/image шүүлтүүрт Odoo тааралт **0**.
- `docker image ls`-д Odoo repository/tag тааралт **0**.
- `odoo`, `psql`, `postgres` executable PATH-д байхгүй.
- `systemctl show odoo.service postgresql.service`: LoadState=not-found, ActiveState=inactive, MainPID=0.
- `systemctl list-unit-files` болон user unit query-д Odoo/PostgreSQL/Podman matching unit олдоогүй. User query exit code 1, output хоосон; энэ нь бүх user service-ийг үгүйсгэх бүрэн нотолгоо биш.
- `/etc/odoo`, `/etc/odoo.conf`, `/opt/odoo`, `/srv/odoo`, `/var/lib/odoo`, `/usr/share/odoo`, `/usr/lib/python3/dist-packages/odoo`, шалгасан Python 3.13/3.14 site-packages Odoo path, `/home/sembee/odoo` байхгүй.
- `rg --files --hidden --no-ignore -g '*[Oo][Dd][Oo][Oo]*'`-ийг `/opt`, `/srv`, `/usr/local`, `/etc/systemd/system`, `/home/sembee/University-coursework`, `/home/sembee/Projects`, `/home/sembee/Documents/Codex`, `/data/sembee` хүрээнд ажиллуулсан. `.git`, node_modules, virtualenv, credential/cache directory-уудыг хассан. Таарсан цорын ганц файл нь энэ бие даалтын Odoo PDF; source/config олдоогүй.
- Permission denied: `/opt/containerd`, өөр хичээлийн зарим GNS3 PKI/RADIUS log зам, нэг хуучин Codex backup directory. Эрхийг өөрчилж нээх оролдлого хийгээгүй. Бүх filesystem/бүх virtualenv-д Odoo огт байхгүй гэж батлахгүй; шалгасан хүрээнд олдоогүй.

## 7. Порт ба сүлжээ: E05

`ss -ltnup` ба дараах сонгосон `ss -H -ltn` snapshot:

| TCP port | Тухайн агшны төлөв | Deployment-д үзүүлэх нөлөө |
|---|---|---|
| 8069 | Listener харагдаагүй | Odoo host candidate; зөвхөн `127.0.0.1:8069:8069` publish санал |
| 8071, 8072 | Listener харагдаагүй | Зөвхөн сонгосон Odoo worker/realtime mode шаардвал loopback/proxy төлөвлөнө |
| 5432 | Listener харагдаагүй | PostgreSQL-ийг host руу publish хийх шаардлагагүй; тусдаа Compose network дотор байлгана |
| 8080 | `0.0.0.0:8080`, `[::]:8080` LISTEN | Existing `nyoom_local-edge-1`; Odoo энэ портыг булаахгүй |
| 80, 443 | Listener харагдаагүй | HTTPS/reverse proxy суулгаж туршаагүй |

Listener байхгүй нь порт reserve хийгдсэн гэсэн үг биш. OpenCode/Deployment агент бие даан ажиллаж байгаа тул deployment эзэн ажиллуулахын яг өмнө дахин шалгана. Шинэ stack-ийн network/subnet үүсгээгүй, firewall/NAT тохиргоо өөрчлөөгүй.

## 8. Coordinator ба deployment эзэнд өгөх бодит төлөвлөгөө

1. `management/assignments.md`, `messages.md`-ээр нэг deployment эзнийг эцэслэж, shared state өөрчлөхийн өмнө POLICY-ийн дагуу тохирох шинэ төслийн group reservation-ийг Coordinator зохицуулна. Audit ямар ч group reserve хийгээгүй. Аудитын явцад ownership солигдсон: 10:42:40-ийн assignments snapshot-д deployment нь Deployment агент, OpenCode нь dataset/policies гэж бичигдсэн; эцсийн зохицуулалтыг багийн одоогийн заавар шийднэ.
2. Existing Docker/Compose-ийг ашиглана. Ubuntu VM/ISO/container-ийг дахин татаж эхлэх шаардлага одоогоор байхгүй; standalone Odoo official image дотроо application dependencies-тэй [S1].
3. Тусдаа Compose project name, шинэ network, шинэ PostgreSQL data, шинэ Odoo filestore ашиглана. 29 existing volume болон Cygnus/Beebee/Lab7 evidence-ийг холбохгүй. Код, compose, README нь бие даалтын `odoo/` дотор байрлана; mutable data-д `/data/sembee/` дотор шинэ assignment-owned directory сонгоно. Эдгээр замыг аудит үүсгээгүй.
4. Odoo 18 Community хувилбар нь боломжит суурь. Local PostgreSQL 16 image-ийг эхлээд reuse candidate гэж үзнэ; deploy хийхдээ origin/digest/update болон Odoo/OCA module compatibility-г баталгаажуулна. Official Odoo 18 image local-д байхгүй тул зөвхөн сонгосон application image-ийн download/build шаардлага үлдэнэ. Энэ аудит download хийгээгүй.
5. Odoo-г loopback 8069 дээр гаргана; PostgreSQL-ийг internal network-д байлгана. Addons-ийг assignment-local mount-аар өгнө. PostgreSQL 16 image-ийн data mount destination нь local inspect-аар `/var/lib/postgresql/data`; өөр major image сонговол mount layout-г дахин тулгана [S3].
6. Жижиг сургалтын demo-д нэг Odoo application process + нэг PostgreSQL container-оос эхлэхийг санал болгоно. Эхний resource budget-ийг Odoo ~1.5-2 GiB, PostgreSQL ~0.5-1 GiB гэж төлөвлөж болно; энэ нь хэмжсэн хэрэгцээ/албан minimum биш, урьдчилсан төсөөлөл. Snapshot RAM available 3.56 GiB, swap хэрэглээ өндөр тул owner эхлүүлсний дараа бодит memory/latency/error-оор тохируулна. Multiworker load test/OOM тест энэ audit-д ороогүй.
7. Root filesystem-ийн headroom-ийг image download, writable layer, log growth-оос өмнө дахин шалгана. `/data` bind mounts нь database/filestore-ийн өсөлтийг тусад нь байрлуулна; Docker daemon root-ийг бүх төслөөр нь нүүлгэх буюу бусдын image/cache/data-г устгах ажлыг энэ төслийн энгийн суулгалтад хамруулахгүй.
8. Deployment owner-ийн баталгаажуулалт: `compose config --quiet`, pinned image inventory, database readiness, Odoo login, custom module install/upgrade, 5 RBAC түвшин, audit log, incident workflow, backup/restore туршилт, screenshot. Эдгээрийг энэ read-only audit гүйцэтгэсэн гэж тайлагнахгүй.

## 9. Аюулгүй дахин шалгах командууд

Доорх нь унших командууд; password/environment/log-ийн нууц мэдээлэл хэвлэхгүй. CLI executable нь `/home/sembee/.local/bin/lab-vms`.

```bash
/home/sembee/.local/bin/lab-vms find --role odoo
/home/sembee/.local/bin/lab-vms find --os ubuntu
/home/sembee/.local/bin/lab-vms find --os debian
/home/sembee/.local/bin/lab-vms find --role database
/home/sembee/.local/bin/lab-vms find --role container
/home/sembee/.local/bin/lab-vms media --os ubuntu
/home/sembee/.local/bin/lab-vms media --os debian

docker version --format 'Client={{.Client.Version}} Server={{.Server.Version}} API={{.Server.APIVersion}}'
docker compose version
docker info --format 'Root={{.DockerRootDir}} Driver={{.Driver}} Containers={{.Containers}} Running={{.ContainersRunning}} Images={{.Images}}'
docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.State}}\t{{.Ports}}'
docker image ls --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}'
docker image inspect postgres:16-alpine --format 'ID={{.Id}} Digests={{json .RepoDigests}} OS={{.Os}} Arch={{.Architecture}} Size={{.Size}} Volumes={{json .Config.Volumes}}'
docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
docker system df

systemctl show docker.service containerd.service odoo.service postgresql.service -p Id -p LoadState -p ActiveState -p MainPID --no-pager
ss -H -ltn
free -h
df -B1 --output=source,fstype,size,used,avail,pcent,target / /home/sembee/University-coursework /var/lib/docker /data
findmnt -T /var/lib/docker -o TARGET,SOURCE,FSTYPE
findmnt -T /data -o TARGET,SOURCE,FSTYPE
```

Lease-ийг утга өөрчлөхгүй унших жишээ:

```bash
python3 - <<'PYLEASE'
import json
from pathlib import Path
p = Path('/home/sembee/.local/share/lab-vms/leases.json')
for group, lease in json.loads(p.read_text()).items():
    print(group, lease.get('owner'), lease.get('reserved_at'))
PYLEASE
```

Stopped Ubuntu container-ийн OS файлыг local extract хийлгүй унших хэрэглэсэн арга:

```bash
python3 - <<'PYOS'
import io, subprocess, tarfile
name = 'coursework-lab7-ubuntu-20261108'
r = subprocess.run(['docker', 'cp', '-L', name + ':/etc/os-release', '-'],
                   check=True, capture_output=True, timeout=20)
with tarfile.open(fileobj=io.BytesIO(r.stdout), mode='r:*') as archive:
    for member in archive.getmembers():
        if member.isfile() and member.name.rsplit('/', 1)[-1] == 'os-release' and member.size < 16384:
            for line in archive.extractfile(member).read().decode().splitlines():
                if line.split('=')[0] in ('NAME', 'ID', 'VERSION_ID', 'PRETTY_NAME'):
                    print(line)
PYOS
```

`docker inspect` бүхэл output, `docker compose config`-ийн quiet бус output, `.env`, `docker logs`/`journalctl` бүхэл output, registry credential file-ийг багийн чатанд хуулж хэрэглэхгүй. Энэ аудитад үйлчилгээ эхлүүлэх команд ажиллуулаагүй.

## 10. Баталгааны түвшин ба нээлттэй үлдсэн ажил

**Бодитоор батлагдсан:** runtime query амжилттай; host resources; image/container inventory; stopped Ubuntu filesystem OS; selected service state; lease snapshot; сонгосон портын listener; шалгасан хүрээний source/config хайлт.

**Батлагдаагүй:** cached PostgreSQL binary-ийн бодит `SELECT version()`; image remote provenance/patch status; Odoo runtime, official image pull/build, database migration, custom module; UAT; backup/restore; бүрэн filesystem дэх Odoo absence; unknown VM-ийн guest OS. Read-only хүрээг дагаж эдгээрийг хийгээгүй. Registry болон filesystem permission warning-уудыг дээр тэмдэглэсэн.

`messages.md`-д 10:40 орчим эхний status, 10:41:38-д ASAP reuse findings илгээсэн; эцсийн тайлангийн мэдээллийг мөн түгжээтэй append хийнэ. Тайлан нь snapshot тул deployment эхлэхийн өмнө багийн шинэ өөрчлөлттэй тулгана.

## 11. Албан техникийн эх сурвалж

- [S1] Docker Official Image: Odoo; maintainer Odoo, supported tags болон PostgreSQL/container/filestore холболтын жишээ. 2026-11-16 live web-ээр шалгасан: `https://hub.docker.com/_/odoo`.
- [S2] Odoo 18.0, Source install, PostgreSQL хэсэг: PostgreSQL 12+ дэмждэг; administrative `postgres` account-аар application холбохгүй. 2026-11-16 live web-ээр албан `.rst` эхийн 179-209 мөрийг шалгасан: `https://raw.githubusercontent.com/odoo/documentation/18.0/content/administration/on_premise/source.rst`. Rendered HTML хаяг `https://www.odoo.com/documentation/18.0/administration/on_premise/source.html` нь fetch timeout буцаасан тул агуулгыг нь `.rst` primary source-оос баталгаажуулсан.
- [S3] Docker Official Image: PostgreSQL; image major version ба volume layout-ийн ялгаа, persistence/init тайлбар. 2026-11-16 live web-ээр шалгасан: `https://hub.docker.com/_/postgres`.
