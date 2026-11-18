from pathlib import Path
from xml.sax.saxutils import escape
import csv,json,math,re,hashlib,datetime
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph,Spacer,Table,TableStyle,Image,Frame,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY,TA_CENTER,TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
ROOT=Path(__file__).resolve().parents[2]
WS=ROOT/'reports/build'
(WS/'work/report').mkdir(parents=True,exist_ok=True)
OUT=ROOT/'reports/Formula5_FormulaUniversity_Odoo_ISMS_Report.pdf'
for name,file in [('Body','LiberationSerif-Regular.ttf'),('Bold','LiberationSerif-Bold.ttf'),('Italic','LiberationSerif-Italic.ttf')]:
 pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/liberation/'+file))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')
W,H=A4; LEFT=30*mm; RIGHT=15*mm; TOP=20*mm; BOTTOM=20*mm; CW=W-LEFT-RIGHT; CH=H-TOP-BOTTOM
styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=12,leading=14.2,alignment=TA_JUSTIFY,firstLineIndent=10*mm,spaceAfter=7),
 'flat':ParagraphStyle('flat',fontName='Body',fontSize=12,leading=14.2,spaceAfter=7),
 'head':ParagraphStyle('head',fontName='Bold',fontSize=12,leading=15,spaceBefore=8,spaceAfter=10),
 'caption':ParagraphStyle('caption',fontName='Italic',fontSize=11,leading=13,alignment=TA_CENTER,spaceBefore=6,spaceAfter=8),
 'cell':ParagraphStyle('cell',fontName='Body',fontSize=9,leading=10.5),
 'small':ParagraphStyle('small',fontName='Body',fontSize=10,leading=12,spaceAfter=6),
 'cover':ParagraphStyle('cover',fontName='Bold',fontSize=18,leading=23,alignment=TA_CENTER,spaceAfter=14),
 'center':ParagraphStyle('center',fontName='Body',fontSize=12,leading=16,alignment=TA_CENTER,spaceAfter=10),
}
def clean(t):
 return re.sub(r'(\d)([А-Яа-яӨөҮү])', r'\1 \2', re.sub(r'([А-Яа-яӨөҮү])(\d)', r'\1 \2', str(t))).replace('\u2011','-').replace('–','-').replace('—','-')
def P(t,style='body'):
 return Paragraph(clean(t),styles[style])
def text(t):return escape(clean(t))
def B(t):return P(t,'head')
def bullet(t):return P('• '+t,'flat')
def table(rows,widths=None,size=9):
 widths=widths or [CW/len(rows[0])]*len(rows[0]); st=ParagraphStyle('c',parent=styles['cell'],fontSize=size,leading=size+1.7)
 data=[[Paragraph(text(v).replace('\n','<br/>'),st) for v in row] for row in rows]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='CENTER')
 t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#8E969A')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E7EBED')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 return t
def figure(name,caption,maxh=250):
 path=ROOT/'evidence/screenshots'/name
 iw,ih=PILImage.open(path).size; scale=min(CW/iw,maxh/ih)
 return [Image(str(path),width=iw*scale,height=ih*scale,hAlign='CENTER'),P(caption,'caption')]
def csvdata(name):
 with (ROOT/'data'/name).open() as f:return list(csv.DictReader(f))
assets=csvdata('assets.csv');risks=csvdata('risks.csv');threats={x['code']:x for x in csvdata('threats.csv')};vulns={x['code']:x for x in csvdata('vulnerabilities.csv')}
controls=[x for x in json.loads((ROOT/'data/controls_soa.json').read_text()) if str(x['selected']).lower()=='true']
levels=[['low','low','low','low','medium'],['low','low','medium','medium','medium'],['low','medium','medium','medium','high'],['low','medium','medium','high','high'],['medium','medium','high','high','high']]
lev={'low':'Бага','medium':'Дунд','high':'Өндөр'};stat={'yes':'Тийм','partial':'Хэсэгчилсэн','no':'Үгүй'}
classmn={'public':'Нээлттэй','internal':'Дотоод','restricted':'Хязгаарлагдмал','confidential':'Нууц'}
team=[['Э. Доржсэмбэ','B241870023','Архитектур, суулгалт, интеграц'],['Б. Батдэмбэрэл','B241870018','Академик модуль, RBAC, тест'],['А. Эрхэмбаяр','B241870055','ISMS, Helpdesk, Inventory, ажиллагаа'],['Б. Бадрал','B241870051','Засаглал, бодлого, эрсдэл, SoA'],['Б. Тэлмүүн','B241870042','Чанар, тайлан, слайд, хамгаалалт']]
pages=[]
def add(title,items,section=None):pages.append({'title':title,'items':items,'section':section})

add('Нүүр хуудас',[
 Spacer(1,20),P('ШИНЖЛЭХ УХААН, ТЕХНОЛОГИЙН ИХ СУРГУУЛЬ','center'),P('Мэдээлэл, холбооны технологийн сургууль','center'),Spacer(1,42),
 P('МЭДЭЭЛЛИЙН АЮУЛГҮЙ БАЙДЛЫН<br/>ЗАСАГЛАЛ БА МЕНЕЖМЕНТ','cover'),P('F.NSA338 · Бие даалтын нэгдсэн тайлан','center'),Spacer(1,20),
 P('Formula University:<br/>Odoo ERP ба ISO/IEC 27001:2022','cover'),P('Дүнгийн өөрчлөлтийн тусдаа батлалттай<br/>их сургуулийн мэдээллийн систем','center'),Spacer(1,28),
 P('Баг: Formula 5','center'),table([['Гишүүн','Оюутны код']]+[[a,b] for a,b,c in team],[CW*.6,CW*.4],11),Spacer(1,32),P('Улаанбаатар хот<br/>2026 оны 11 дүгээр сарын 16','center'),
 P('Formula University нь сургалтын зориулалттай зохиомол кейс. Системийн зураг, тест, ажиллагааны үр дүнг локал Odoo орчноос бодитоор гаргав.','small')])

toc=[('1. Удиртгал ба байгууллагын нөхцөл',3),('2. Odoo модуль ба ISO уялдаа',5),('3. Хөрөнгийн бүртгэл',7),('4. Эрсдэлийн үнэлгээ',9),('5. Хяналтын зураглал',13),('6. Зөрчлийн удирдлага',15),('7. МАБ-ын бодлогууд',17),('8. RBAC, аудит ба SoA',23),('9. Дүгнэлт ба сайжруулалт',27),('10. Хавсралт ба ажиллуулах заавар',28),('11. Ашигласан эх сурвалж',28)]
add('Агуулга ба хураангуй',[
 B('АГУУЛГА'),*[P(f'<link href="#page{n}" color="black">{text(t)} ................................ {n}</link>','flat') for t,n in toc],
 B('Хураангуй'),P('Бие даалтаар их сургуулийн семестрийн дүнг засварлах хүсэлтийг өөр ажилтан баталдаг үйлчилгээг Odoo 18 Community дээр хөгжүүлж, хөрөнгө, эрсдэл, бодлого, зөрчил, audit логтой холбов. Бүртгэлд 16 хөрөнгө, 14 эрсдэл, 25 сонгосон хяналт, үндсэн 3 бодлого болон нэмэлт AUP багтсан.'),
 P('Дүнг 72-оос 85 болгон өөр хэрэглэгчээр баталсан UI ажиллагаа, таван шаттай Community Helpdesk урсгал, 39 автомат тест, PostgreSQL ба filestore-ийн тусдаа сэргээх туршилт амжилттай болсон. SoA нь 15 хэрэгжсэн, 10 хэсэгчилсэн хяналтыг ялган тайлбарлана.'),
 P('Түлхүүр үг: засаглал, ISMS, Odoo Community, үүрэг салгалт, RBAC, эрсдэл, SoA, audit.','small')])

add('1. Удиртгал ба байгууллагын нөхцөл',[
 B('1.1. Асуудал, зорилго'),P('Семестрийн дүнгийн хаалтын дараа протоколын нийлбэр, шивэлтийн алдааг залруулах хэрэгцээ гардаг. Хүсэлтийг чат, цахим шуудангаар авч нэг ажилтан шууд засдаг бол хэн зөвшөөрсөн, ямар нотолгоо байсан, хуучин дүн хэд байсан нь салангид үлдэнэ. Энэ кейсийн гол зорилго нь дүнгийн бүрэн бүтэн байдал, оюутны мэдээллийн нууцлал, үйлчилгээний хүртээмжийг хамтад нь удирдах юм.'),
 B('1.2. Байгууллагын орчин - Clause 4'),P('Formula University нь 3,600 оюутан, 280 ажилтан, 3 бүрэлдэхүүн сургууль, 2 байртай гэж загварчлав. Сургалтын алба дүн ба дипломын бүртгэл хөтөлнө. Кибер-Физик лаборатори тоног төхөөрөмж нийлүүлэгчтэй хамтран ажиллаж, судалгааны өгөгдөл болон симулятор ашиглана. Эдгээр хэмжээ, сервер, NAS, CCTV нь кейсийн загварын өгөгдөл юм.'),
 table([['Оролцогч','Хэрэгцээ / хүлээлт','Хариу хяналт'],['Оюутан','Өөрийн зөв дүн, хувийн мэдээллийн нууцлал','Өөрийн бичлэгт хандах record rule'],['Багш','Протоколын алдаа залруулах боломж','Хариуцсан хичээлийн хүсэлт'],['Сургалтын алба','Баталгаат дүн, хариуцлагын мөр','Тусдаа батлагч, revision шалгалт'],['Удирдлага','Тасралтгүй ажиллагаа, эрсдэлийн тайлагнал','Эзэн, SoA, сэргээх төлөвлөгөө'],['Нийлүүлэгч / аудитор','Хязгаарлагдсан хандалт, нотолгоо','Хугацаатай эрхийн бодлого; унших эрх']],[CW*.2,CW*.39,CW*.41],10),
 B('1.3. Хамрах хүрээ'),P('Хамрах хүрээнд оюутан, хичээл, хичээл санал болголт, сонголт, дүнгийн хүсэлт, ISMS бүртгэл, Helpdesk болон Inventory каталог орно. LMS, SSO, VPN, физик хамгаалалт, байгууллагын NAS нь кейсийн орчны хамаарал болон treatment төлөвлөгөөнд багтана. Локал хэрэгжүүлэлт нь Odoo ба PostgreSQL контейнерээр ажиллана.'),
],1)

add('1.4. Засаглал, үүрэг ба хэмжилт',[
 P('Засаглал нь удирдлагаас чиглэл тогтоох, эрсдэлийн шалгуур батлах, хяналтын үр дүнг үнэлэх үйл ажиллагаа. Менежмент нь тэр чиглэлийн дагуу хүний нөөц, процесс, технологийг төлөвлөж хэрэгжүүлэх ажил юм. EISP нь удирдлагын чиглэлийг, Access Control нь тодорхой асуудлын дүрмийг, системийн тохиргоо ба runbook нь хэрэгжилтийн зааврыг илэрхийлнэ. [2-5]'),
 table([['Clause','Кейсийн шийдвэр','Баримт / хэмжүүр'],['4. Нөхцөл','Үйлчилгээ, оролцогч, хамаарлыг тогтоох','Кейс, scope, 16 хөрөнгө'],['5. Манлайлал','Ректор чиглүүлж, CISO хяналт хариуцах','EISP, эзэн, үүрэг тусгаарлалт'],['6. Төлөвлөлт','RM-01 аргачлал, treatment, SoA','14 эрсдэл, 25 сонгосон хяналт'],['7. Дэмжлэг','Бодлогын хувилбар ба танилцсан мөр','POL-01-03, demo acknowledgment'],['8. Ажиллагаа','Дүн, зөрчил, хөрөнгийн workflow','Тусдаа батлалт, таван шат'],['9. Үнэлгээ','Тест, аудит, сэргээх туршилт','39 тест; 190 checksum'],['10. Сайжруулалт','Зөрчлийн шалтгаан, сургамж, шинэ ажил','Close gate, MFA/нөөцийн төлөвлөгөө']],[CW*.2,CW*.4,CW*.4],10),
 B('Багийн хариуцах ажлын хуваарилалт'),table([['Гишүүн','Хариуцах хүрээ']]+[[a,c] for a,b,c in team],[CW*.3,CW*.7],10),
 P('Энэ хүснэгт нь хэрэглэгчийн заавраар баталсан ажлын хуваарилалт. Агентын хийсэн суулгалт, код, тестийг тухайн хүн өөрөө хийсэн гэсэн оролцооны нотолгоо болгон ашиглахгүй. Гишүүд өөрсдийн шалгалт, тайлбар, хамгаалалтаа worklog-д тэмдэглэнэ.','small'),
 P('Зорилтот RPO ≤24 цаг, RTO ≤4 цаг. Бодит локал сэргээх хугацаа 48.414 секунд байсан ч энэ нь бүх кампусын ачаалал, тоног төхөөрөмжийн сэргэлтийг хэмжсэн дүн биш.','small')])

add('2. Odoo модуль ба ISO уялдаа',[
 B('2.1. Технологийн сонголт'),P('Odoo нь өгөгдөл, хэрэглэгч, эрх, бизнесийн үйлдлийг нэгдсэн ORM ба модуль бүтэцтэй удирддаг ERP платформ. Community Edition-ийн base, mail, hr, project, stock боломжийг ашиглаж, сургалтын үйлчилгээ ба ISMS домэйныг өөрийн модулиар нэмэв. OCA helpdesk_mgmt нь Community-тэй нийцэх Helpdesk хэрэгжүүлэлт. [6-8]'),
 table([['Бүрэлдэхүүн','Хэрэгжүүлэлт','Зориулалт / холбоо'],['Odoo 18.0 Community','Build 18.0-20261112','Web client, ORM, security'],['PostgreSQL 16','isms-db, host port publishгүй','Транзакц ба хүснэгт'],['campus_university','Өөрийн хөгжүүлэлт','Оюутан, хичээл, дүн; 5.3, 8.3'],['university_isms','Өөрийн хөгжүүлэлт','Asset, risk, control, policy, incident'],['campus_isms_bridge','Өөрийн хөгжүүлэлт','Academic audit; asset/incident холбоос'],['helpdesk_mgmt + bridge','OCA 18.0 + өөрийн bridge','Зөрчлийн таван шат; 5.24-5.26'],['stock + 2 bridge','Inventory ба өөрийн каталог','16 product; owner/class/location/risk'],['isms.audit.mixin','Аппликейшний audit','Actor, цаг, өөрчлөлт; 8.15']],[CW*.29,CW*.29,CW*.42],10),
 B('2.2. Байршуулах бүтэц'),P('Хөтөч → 127.0.0.1:8069 → isms-odoo → isms-db гэсэн урсгалтай. Compose төсөл isms, сүлжээ isms-net; өгөгдлийн сан ба filestore нь /data/sembee/odoo-isms дор хадгалагдана. Веб үйлчилгээ loopback интерфейст, PostgreSQL нийтэд нээгдээгүй. [9]'),
 P('VM reuse policy-г уншиж, lab-vms refresh болон registry search хийсэн. Тохирох verified Odoo VM байгаагүй тул хостын Docker runtime, өмнө хадгалсан PostgreSQL image-ийг ашиглав. Шинэ VM диск импортлоогүй, бусад хичээлийн үндсэн дискийг өөрчлөөгүй.','small'),
],2)

add('2.3. Академик системийн хэрэгжилт',[
 P('campus.program → campus.student → campus.enrollment ← campus.offering ← campus.course гэсэн холбоо нь суралцагч, хөтөлбөр, хичээл, улирлын сонголтыг удирдана. campus.grade.change нь enrollment-ийн одоогийн дүн, revision-ийг snapshot авч, санал болгосон дүн ба нотолгооны лавлагааг хадгална.'),
 P('Багш өөрийн хичээлд draft хүсэлт үүсгэн submitted болгоно. Өөр эрхтэй сургалтын албаны ажилтан approved эсвэл rejected шийдвэр гаргана. Approve хийхэд requester ≠ approver, дүн 0-100, төлөв ба revision таарч буй эсэхийг сервер шалгана. Дүн ба revision нэг транзакцад шинэчлэгдэж, давхар шинэчлэлт мөрийн lock-оор хамгаалагдана.'),
 *figure('03-grade-approved-independent-reviewer.png','Зураг 1. Бодит UI: GCR/2026/00039, 72 → 85, тусдаа батлагч.',245),
 P('Хүсэлт гаргагч campus.lecturer@orgil.example, батлагч campus.reviewer@orgil.example. Оюутан өөрийн жагсаалтад 85.00, revision 1-ийг харсан. Эдгээр нь зохиомол demo хэрэглэгчээр гүйцэтгэсэн бодит ажиллагаа. [10]'),
 P('Оноог шууд write хийх, хүсэлт гаргагчийг хуурамчаар солих, өөрийн хүсэлтийг батлах, хуучирсан revision ашиглах оролдлогыг автомат тестээр хориглосон. UI-ийн товч нуух аргаас гадна public action болон ORM түвшинд шалгалт хийсэн.','small')])

shortnames=['Оюутны хувийн мэдээлэл','Дүн ба өөрчлөлтийн журнал','Odoo ERP/ISMS платформ','Moodle LMS','Элсэлтийн портал','Шалгалтын нууц сан','Дипломын бүртгэл','Судалгааны өгөгдөл/код','SCADA/PLC стенд','Виртуалчлалын кластер','Нөөцийн NAS','Серверийн өрөө','Галт хана/VPN','Албаны зөөврийн компьютер','SSO/цахим шуудан','Нийтийн вэб портал']
assetRisk={a['code']:[r['code'] for r in risks if a['code'] in r['asset_codes'].split(';')] for a in assets}
def assetrows(part):
 rows=[['Код / хөрөнгө','Эзэн / хариуцагч','Ангилал / байршил','C/I/A / эрсдэл']]
 for i in part:
  a=assets[i];loc=a['location'];loc=loc.replace('Серверийн өрөө','Сервер').replace('Хичээлийн','').replace('Мэдээллийн','')
  rows.append([a['code']+'\n'+shortnames[i],a['owner_login']+'\n'+a['custodian_login'],classmn[a['classification']]+'\n'+loc,'/'.join(a[k] for k in ['confidentiality','integrity','availability'])+'\n'+', '.join(assetRisk[a['code']])])
 return rows
add('3. Хөрөнгийн бүртгэл',[
 P('Мэдээллийн хөрөнгө гэдэгт зөвхөн сервер бус, оюутны өгөгдөл, дүн, шалгалтын материал, судалгааны код, үйлчилгээ, орчны хамаарлыг хамруулав. Эзэн нь ашиглалт ба эрсдэлийг шийдвэрлэх үүрэгтэй; хариуцагч нь өдөр тутмын техникийн хамгаалалт, хадгалалтыг хэрэгжүүлнэ. [4,5]'),
 P('C/I/A нь нууцлал, бүрэн бүтэн байдал, хүртээмж; тус бүр 1-3. Хөрөнгийн үнэ цэнийг max(C,I,A)-аар тооцно. Эрсдэлийн 1-5 магадлал/нөлөөллийн онооноос тусдаа хэмжүүр юм.'),
 P('Хүснэгт 1. Хөрөнгийн бүртгэл AST-001-008.','caption'),table(assetrows(range(8)),[CW*.24,CW*.22,CW*.32,CW*.22],9.2),
 P('AST-001 ба AST-002 нь хувийн мэдээлэл агуулна. Дүнгийн хүсэлт, аудиттай холбосон AST-002 дээр integrity=3 гэж үнэлсэн. Байршил, тоног төхөөрөмжийн нэр нь кейсийн загвар; локал хостод энэ бүх төхөөрөмж бий гэсэн үг биш.','small')
],3)
add('3.1. Inventory дахь ижил бүртгэл',[
 P('Хүснэгт 2. Хөрөнгийн бүртгэл AST-009-016.','caption'),table(assetrows(range(8,16)),[CW*.24,CW*.22,CW*.32,CW*.22],8.8),
 *figure('14-inventory-catalog.png','Зураг 2. Inventory бүтээгдэхүүний каталогт холбосон 16 хөрөнгө.',185),
 P('Бүх16 хөрөнгө isms.asset.product_id ↔ product.product холбоостой. Мэдээлэл, үйлчилгээ, facility нь stock тоо хэмжээ үүсгэхгүй service каталог. Таван hardware-д DEMO-AST-xxx-001 төлөөлөх серийн код бүртгэсэн. Худалдан авалт, үлдэгдэл, бодит төхөөрөмжийн тооллого зохиогоогүй. [11]','small')])

add('4. Эрсдэлийн үнэлгээ',[
 B('4.1. RM-01 v1.0 аргачлал'),P('Эрсдэлийг хөрөнгө, аюул занал, эмзэг байдал, боломжит үр дагавартай холбоно. Магадлал (М), нөлөөлөл (Н)-ийг 1-5-аар үнэлж тоон оноо = М × Н гэж гаргана. Түвшинг Лекц 8-9, слайд 19-ийн lookup матрицаар тогтоов. [5]'),
 table([['М / Н','1','2','3','4','5']]+[[str(i+1)]+[lev[x] for x in row] for i,row in enumerate(levels)],[CW*.2]+[CW*.16]*5,11),
 P('Хүснэгт 3. Эрсдэлийн үндсэн ангиллын матриц.','caption'),
 P('Магадлал: 1-ховор, 2-боломжтой, 3-дунд, 4-өндөр, 5-маш өндөр. Нөлөөлөл: 1-хязгаарлагдсан, 2-бага үйлчилгээний саатал, 3-нэгжийн ажиллагаанд мэдэгдэхүйц, 4-гол үйлчилгээнд ноцтой, 5-их сургуулийн үндсэн үйл ажиллагаа ба нэр хүндэд онц ноцтой гэж кейсийн шалгуураар үнэлсэн.'),
 B('4.2. Ангиллын тайлбар'),P('Өндөр эрсдэлд удирдлагын хяналттай бууруулах ажил эхлүүлнэ. Дунд эрсдэлд эзэн, хугацаа, ажлын нотолгоо тогтооно. Бага эрсдэлийг зөвхөн эрх бүхий CISO үндэслэлтэйгээр хүлээн авч, дахин хянах огноо өгнө. Оноо бага байгаа нь автоматаар acceptance болсон гэсэн үг биш.'),
 P('Sem10-ийн 1-6 / 7-12 / 13-25 босго нь энэ lookup-тай дөрвөн нүдэнд зөрнө: (1,5), (5,1), (2,3), (3,2) нь энд Дунд. Иймээс хоёр аргачлалыг ижил гэж нэрлээгүй; системийн 25 нүдийг энэ матрицаар тестэлсэн. [5,12]'),
 P('14 анхны эрсдэлийн тархалт: 5 өндөр, 8 дунд, 1 бага. Үлдэгдлийн оноонууд нь treatment бүрэн хэрэгжсэний дараах зорилтот үнэлгээ; одоогийн үр дүн гэж шууд тооцохгүй.','small')
],4)

def riskdetail(part):
 items=[]
 for i in part:
  r=risks[i];l=int(r['likelihood']);im=int(r['impact']);
  items += [B(r['code']+' - '+r['name']),P('Хөрөнгө: '+r['asset_codes'].replace(';',', ')+'. Аюул: '+text(threats[r['threat_code']]['name'])+'. Эмзэг байдал: '+text(vulns[r['vulnerability_code']]['name'])+'.','small'),P(f'М={l}; Н={im}; оноо={l*im}; түвшин={lev[levels[l-1][im-1]]}. Эзэн: {r["owner_login"]}. Хяналт: {r["control_codes"].replace(";",", ")}.','small')]
 return items
add('4.3. Эрсдэлийн бүртгэл RSK-01-07',riskdetail(range(7)))
add('4.4. Эрсдэлийн бүртгэл RSK-08-14',riskdetail(range(7,14)))

add('4.5. Эрсдэлийг бууруулах тэргүүлэх ажил',[
 P('Эхний ээлжид дүнгийн integrity, PII нууцлал, сэргээх чадварыг хамгаална. Хяналтын зорилгыг оноо бууруулах тооцоотой хамт тодорхойлж, хэрэгжүүлэлтийг source, тест, screenshot, ажилласан орчны нотолгоогоор батална. [5,10-14]'),
 table([['Эрсдэл / стратеги','Ажил ба одоогийн нотолгоо','Эзэн / зорилтот огноо'],['RSK-01,09 / бууруулах','Тусдаа батлалт, record rule, revision, audit хэрэгжсэн. MFA rollout төлөвлөгөөтэй.','batdemberel / 2026-11-25'],['RSK-02 / бууруулах','Локал DB+filestore restore PASS. Тусгаарласан immutable нөөцийн архитектур төлөвлөгөөтэй.','batdemberel / 2026-12-05'],['RSK-03 / бууруулах','Аппликейшний audit write/unlink хориг, actor ба pre/post. DB admin-аас тусдаа log sink төлөвлөнө.','dorjsembe / 2026-11-20'],['RSK-04 / бууруулах','Өөрийн болон хариуцсан бичлэгийн RBAC. Экспорт, retention, хуульд нийцлийн нэмэлт үнэлгээ хийнэ.','badral / 2026-11-30'],['RSK-05 / бууруулах','Нийлүүлэгчийн ≤8 цагийн хандалтын бодлого. VPN/NDA бодит rollout хийгдээгүй.','lab_head / 2026-12-01'],['RSK-13 / шилжүүлэх','CDN/DDoS үйлчилгээ ба SLA сонгох. Гэрээ болон reverse proxy нь төлөвлөгөө.','batdemberel / 2026-12-18'],['RSK-14 / хүлээн авах','Бага түвшний үндэслэл, мэдээлэх суваг, SETA хөтөлбөр. CISO-ийн acceptance gate шаардлагатай.','dorjsembe / 2026-11-30']],[CW*.21,CW*.55,CW*.24],10),
 P('Эндэх огноо нь зохиомол кейсийн ажлын зорилтот хугацаа. Хичээлийн хамгаалалтын календарийн батлагдсан огноо гэж үзээгүй. Үлдэгдэл эрсдэлийн acceptance-г score талбар импортолсноор батлагдсан гэж тайлбарлахгүй.','small'),
 B('Project холбоо'),P('isms.risk нь project.task-тай treatment ажлыг холбох боломжтой. Эзэн, хугацаа, нотолгоо, дахин үнэлгээг нэг ажлын мөрөнд хөтөлнө. Системийн хяналт амжилттай болсон эсэхийг аудитор үнэлсний дараа CISO acceptance action ажиллуулна.')])

# mapping concise, grounded proof per control
proof={
'5.1':'isms.policy: хувилбар, 3 live approval/ack', '5.2':'hr.department, users/groups, үүргийн матриц','5.3':'Grade requester ≠ approver; auditor read-only','5.9':'16 asset ↔ Inventory product; эзэн, ангилал, эрсдэл','5.10':'AUP бодлого, asset lifecycle; байгууллагын rollout төлөвтэй','5.12':'Нээлттэй/дотоод/хязгаарлагдмал/нууц ангилал','5.15':'ACL + record rules, student/lecturer isolation','5.16':'Хэрэглэгч, role; JML automation төлөвтэй','5.17':'Хамгийн бага урт 10; private credential files','5.18':'Эрхийн role, auditor; улирлын review төлөвтэй','5.19':'Supplier risk, asset owner; гэрээ/VPN төлөвтэй','5.24':'ISMS incident ба OCA Helpdesk, 5 stage','5.25':'Severity, assessment, notification decision','5.26':'Root cause, resolution, CISO closure gate','5.28':'Audit ба evidence reference; external WORM төлөвтэй','5.34':'PII flag, student isolation; retention/эрх зүйн үнэлгээ','6.3':'Policy demo ack; бодит SETA сургалт төлөвтэй','6.8':'Reporter өөрийн incident-ийг мэдээлэх суваг','7.2':'Facility asset ба physical treatment; карт/CCTV загвар','8.2':'ISMS manager, analyst, auditor эрхийн тусгаарлалт','8.3':'Оюутны өөрийн, багшийн хариуцсан бичлэг','8.5':'auth_totp суусан; enrollment, MFA rollout төлөвтэй','8.13':'Local DB+filestore restore PASS; offsite төлөвтэй','8.15':'Actor/time/model/өөрчлөлт; log write/unlink хориг','8.28':'Server action checks, ORM, revision, native security tests'}
for part,title in [(controls[:13],'5. Хяналтын зураглал - I'),(controls[13:],'5.1. Хяналтын зураглал - II')]:
 rows=[['Annex A / хяналт','Odoo хэрэгжүүлэлт ба нотолгоо','Холбогдох эрсдэл']]
 for x in part:
  rc=[r['code'] for r in risks if x['control_code'] in r['control_codes'].split(';')]
  rows.append([x['control_code']+' '+x['name_mn'],proof[x['control_code']],', '.join(rc) or 'Нийт хамрах хүрээ'])
 add(title,[P('Сонгосон25 хяналт нь кейсийн хөрөнгө, эрсдэл, бизнесийн өөрчлөлттэй холбоотой. Технологийн болон баримтжуулалтын хэрэгжилтийг ялгаж, үйл ажиллагааны хүрээнд нь үнэлсэн. [4-8,10-14]'),table(rows,[CW*.34,CW*.46,CW*.2],9.1),P('Жишээ: AST-002 → RSK-01/RSK-09 → A.5.3 ба A.8.15 → campus.grade.change → independent approval screenshot ба audit pre/post. Энэ холбоо нь хяналтын зорилгоос бодит үйлдэл хүртэл мөрдөх боломж өгнө.','small')],5 if part is not None and title.startswith('5. ') else None)

add('6. Зөрчлийн удирдлага',[
 P('Мэдээллийн аюулгүй байдлын үйл явдал нь үнэлэх шаардлагатай ажиглалт; зөрчил нь хамгаалалтад сөрөг нөлөөтэй гэж үнэлсэн тохиолдол. Хэрэглэгч мэдээлж, шинжээч ангилан шалгаж, эрх бүхий удирдлага хаалтыг хянана. ISMS incident нь canonical бүртгэл, Community Helpdesk нь түүнтэй нэг нэгээр холбогдсон тасалбар юм.'),
 table([['Үе шат','Үйлдэл ба gate','Гол үүрэг'],['Incident','Анхны ажиглалт, asset, severity, тайлбар','Reporter'],['Report','Албан мэдээлэл, мэдээлсэн цаг','Reporter / Analyst'],['Investigate','Шалтгаан, нөлөө, мэдэгдэх эсэхийн үнэлгээ','Analyst'],['Resolve','Root cause ба resolution заавал','Analyst'],['Close','Сургамж, хяналт; manager эрх заавал','CISO / Manager']],[CW*.18,CW*.59,CW*.23],10),
 *figure('10-helpdesk-kanban.png','Зураг 3. Бодит OCA Community Helpdesk-ийн таван үе шат.',245),
 P('Шат алгасах, analyst-аар CISO closure хийх, бусдын incident харах, холбоос салгах, тасалбар устгах оролдлогыг тест хориглосон. Kanban drag нь ISMS серверийн action руу дамждаг тул төлөвийг UI-ээр шууд сольж хамгаалалт тойрохгүй. [13]','small')
],6)

add('6.1. Бодит software exercise',[
 B('INC-2026-0021 - Дүнгийн хуурамч хүсэлтийг шалгах'),P('Баталгаагүй сувгаар ирсэн дүнгийн өөрчлөлтийн хүсэлтийг student_demo мэдээлж, erkhembayar analyst эрхээр шалган шийдвэрлэж, dorjsembe CISO эрхээр хаасан. Энэ нь зохиомол тохиолдлыг бодит системийн үүрэг, төлөв, шаардлагатай талбараар ажиллуулсан software exercise юм. [10]'),
 *figure('13-incident-closed.png','Зураг 4. Close төлөв, шийдвэрлэлт ба сургамжтай incident.',260),
 table([['Шилжилт','Actor','Helpdesk үр дүн'],['Incident → Report','student_demo','Report'],['Report → Investigate','erkhembayar','Investigate'],['Investigate → Resolve','erkhembayar','Resolve'],['Resolve → Close','dorjsembe','Close']],[CW*.43,CW*.29,CW*.28],10),
 P('6 canonical incident дээр энэ live exercise нэмэгдэж нийт7 incident,7 Helpdesk ticket болсон. Helpdesk id17 ба incident id34 нь системийн sequence; тест хэрэглэснээр дугаар тасалдсан байж болно. Дугаарыг гоё болгохын тулд дахин дугаарлаагүй.'),
 P('Шилжилтүүд автомат скриптээр богино хугацаанд хийгдсэн тул ижил секундийн timestamp-ийг байгууллагын бодит response time гэж дүгнээгүй. Хүний сургалт хийсэн гэх нотолгоо болгон ашиглахгүй.','small')])

add('7. Бодлого I - EISP (1/2)',[
 P('POL-01 · Хувилбар1.2 · Дотоод хэрэглээ · Эзэн: CISO','flat'),P('Кейсийн удирдлагын батлах үүрэг: Ректор / удирдах зөвлөл. Локал software exercise: dorjsembe manager account, 2026-11-16. Жилд нэгээс доошгүй удаа болон ноцтой зөрчлийн дараа хянана.','small'),
 B('7.1. Зорилго ба хамрах хүрээ'),P('Formula University-ийн сургалт, судалгаа, удирдлагын мэдээллийн нууцлал, бүрэн бүтэн байдал, хүртээмжийг эрсдэлд суурилсан удирдлагаар хамгаална. Бүх ажилтан, багш, оюутан, гэрээт нийлүүлэгчийн эрх бүхий ашиглалт болон их сургуулийн мэдэлд буй мэдээллийн хөрөнгийг хамарна.'),
 B('7.2. Удирдлагын үндсэн шаардлага'),bullet('Хөрөнгө бүр эзэн, ангилал, байршил, ашиглалтын зорилго, эрсдэлийн холбоостой байна. Эзэн нь мэдээллийг зөвшөөрсөн зорилгоор ашиглуулах ба хадгалах хугацааг тогтооно.'),bullet('Хандалтыг шаардлагатай хамгийн бага эрхээр олгоно. Өөрчлөлт хүсэх, батлах, аудитлах үүргийг тусгаарлана. Дүнгийн өөрчлөлтийг нотолгоогүй болон өөрийн зөвшөөрлөөр батлахгүй.'),bullet('МАБ-ын эрсдэлийг RM-01 матрицаар үнэлж, эзэн, treatment, хугацаа, үлдэгдлийн шалгууртай бүртгэнэ. Өндөр эрсдэлийг удирдлагад тайлагнаж, хяналтгүйгээр хүлээн авахгүй.'),bullet('Зөрчил, сэжигтэй үйл явдлыг ISMS мэдээлэх сувгаар бүртгэнэ. Шалтгаан, нөлөөлөл, хариу арга хэмжээ, сургамжийг баримтжуулж хаана.'),bullet('Өгөгдлийн сан ба filestore-ийг хамтад нь нөөцөлж, тусдаа орчинд сэргээхийг тогтмол шалгана. RPO ≤24цаг, RTO ≤4цагийг кейсийн зорилт болгоно.'),
 B('7.3. Үүрэг'),P('Ректор бодлого, нөөц, эрсдэлийн шалгуурыг батална. CISO ISMS хэрэгжилт ба тайлагналыг удирдана. МТ баг тохиргоо, нөөц, логийг ажиллуулна. Хөрөнгийн эзэн ангилал, хандалт, эрсдэлийн шийдвэрийг хариуцна. Дотоод аудитор хараат бусаар нотолгоо шалгана.'),
],7)

add('7.4. EISP - Хэрэгжилт ба үнэлгээ (2/2)',[
 B('Баримтжуулалт ба танилцуулга'),P('Бодлого бүр код, хувилбар, эзэн, батлах үүрэг, баталсан огноо, дахин хянах огноотой байна. Хувилбар солигдох үед дахин танилцуулна. Батлагдсан агуулгыг шууд засахгүй, review workflow-оор шинэ хувилбар бэлтгэнэ. Хэрэглэгч зөвхөн өөрийн нэрээр танилцсан бүртгэл үүсгэнэ.'),
 B('Хяналт-шинжилгээ'),table([['Хэмжүүр','Шалгах арга','Давтамж / эзэн'],['Дүнгийн тусдаа батлалт','Requester≠approver; audit тулгалт','Өөрчлөлт бүр / сургалтын алба'],['Хандалтын зохистой байдал','Идэвхтэй account ба role review','Улирал бүр / CISO, HR'],['Зөрчлийн бүрэн хаалт','Root cause, resolution, lessons','Тохиолдол бүр / analyst, manager'],['Нөөцийн сэргэлт','DB counts, filestore checksum','Улирал бүр / МТ баг'],['Хяналтын хэрэгжилт','SoA, evidence, эрсдэлийн дахин үнэлгээ','Улирал бүр / дотоод аудитор']],[CW*.28,CW*.42,CW*.3],10.5),
 B('Зөрчил ба exception'),P('Бодлогоос зөрөх түр хэрэгцээг шалтгаан, эзэн, хугацаа, нөхөх хяналттайгаар CISO-д бүртгүүлнэ. Сургалтын дүнгийн self-approval болон audit устгахыг exception болгож зөвшөөрөхгүй. Алдаа, зөрчлийн шалтгааныг сургамж болгон процесс, хандалт, сургалтыг шинэчилнэ.'),
 B('Тухайн орчны бодит хэрэгжилт'),P('Odoo-д дөрвөн бодлогын агуулга бүртгэлтэй. Үндсэн POL-01-03 нь2026-11-16-нд live action-аар батлагдаж, demo reporter тус бүрт нэг acknowledgment үүсгэсэн. Энэ нь policy workflow ажиллаж буйг нотолно. Байгууллагын бүх хэрэглэгч бодитоор сургагдсан, бүх удирдлага гарын үсэг зурсан гэсэн үр дүнг энэ demo-оос дүгнэхгүй.'),
 P('Холбоо: Clause 5.1-5.3, 7.5, 9.1, 10.2; Annex A.5.1, 5.2, 5.3. Эх бодлогын дэлгэрэнгүйг policies/01-information-security-policy-EISP.md-д хадгалсан. [3,4,15]','small')])

add('7.5. Бодлого II - Хандалтын хяналт (1/2)',[
 P('POL-02 · Хувилбар1.2 · ISSP · Эзэн: CISO · Хяналт: 6сар тутам','flat'),
 B('Зорилго ба зарчим'),P('Хэрэглэгчийг хувийн account-аар таньж, үүрэг ба хариуцсан мэдээлэлд нь тохирсон хамгийн бага эрх олгоно. Account хуваалцахгүй. Бизнесийн батлагч ба техникийн администраторын эрхийг тусгаарлана. Системд нэвтрэх боломж нь бүх өгөгдлийг унших эрх гэсэн үг биш.'),
 B('Эрх олгох, солих, хаах'),table([['Үе','Шаардлага','Хариуцагч'],['Joiner','Тушаал/гэрээ, эзний хүсэлт, CISO зөвшөөрөл, role','HR + эзэн + МТ'],['Mover','Шинэ үүрэгт тохирох эрх; хуучин хэрэгцээгүй эрх хасах','Эзэн + МТ'],['Leaver','Мэдээлэл ирснээс 4 цагийн дотор account хаах зорилт','HR + МТ'],['Review','Идэвхгүй, давхар, давуу эрхтэй account шалгах','CISO + аудитор'],['Supplier','Зөвшөөрсөн ≤8цагийн цонх, MFA, гэрээ, лог','Эзэн + CISO']],[CW*.17,CW*.59,CW*.24],10.5),
 B('Танилт ба баталгаажуулалт'),bullet('Нууц үгийн хамгийн бага урт10 тэмдэг. Түр нууц үгийг хамгаалсан сувгаар өгч, нийтэд ил тайлан эсвэл repository-д хадгалахгүй.'),bullet('Багш, сургалтын алба, админ, нийлүүлэгчид TOTP MFA хэрэгжүүлэх зорилт тавина. auth_totp module суулгасан эсэх ба account enrollment хийсэн эсэхийг тус тусад нь шалгана.'),bullet('Өөрөө бүртгүүлэх боломжийг хааж, эрх бүхий ажилтан account үүсгэнэ. Улирал тутмын review, leaver closure-ийн нотолгоог тусад нь хөтөлнө.'),
 P('Энэ бодлогын JML, supplier VPN болон бүх хэрэглэгчийн MFA нь байгууллагын rollout-ийн шаардлага. Локал prototype-д бүх үйл явцыг автоматжуулсан гэсэн тайлбар хийгээгүй.','small')])

add('7.6. Хандалтын хяналт - Хэрэгжилт (2/2)',[
 B('Бизнесийн эрхийн тусгаарлалт'),bullet('Оюутан өөрийн student болон enrollment-ийг уншина; бусдын хувийн мэдээлэл, дүнгийн өөрчлөлтөд хандахгүй.'),bullet('Багш зөвхөн өөрийн offering-ийн enrollment дээр хүсэлт гаргана. Хүсэлт гаргагч, хуучин дүн, revision-ийг хэрэглэгч хуурамчаар солихгүй.'),bullet('Сургалтын албаны эрхтэй ажилтан өөр хүний submitted хүсэлтийг батална. Өөрийн хүсэлтийг батлах болон enrollment.score-г шууд write хийхийг сервер хориглоно.'),bullet('ISMS reporter өөрийн incident-ийг мэдээлнэ; analyst шалгаж шийдвэрлэнэ; manager шаардлагатай тайлбартайгаар хаана. Auditor бүртгэлийг унших ба өөрчлөхгүй.'),
 B('Техникийн хамгаалалт'),P('Odoo ACL нь model-level үйлдлийг, record rule нь тухайн хэрэглэгчид харагдах бичлэгийг, field groups нь тусгай талбарыг хязгаарлана. Public method бүр group, state, owner шалгалттай байна. Context-д ирсэн boolean утгыг trusted authority гэж үзэхгүй; дотоод workflow нь RPC-ээр сэргээх боломжгүй object identity token ашиглана. [6]'),
 B('Хяналт ба нотолгоо'),table([['Шалгах оролдлого','Хүлээгдэх үр дүн'],['Student → өөр оюутны record','AccessError / жагсаалтаас тусгаарлагдах'],['Багш → өөр offering','AccessError'],['Requester → өөрийн request approve','AccessError / UserError'],['RPC → score/state/approver forge','Хориглох'],['Auditor → asset/risk/ticket write','AccessError'],['Хуурамч audit skip context','Audit бичлэг хэвийн үүсэх']],[CW*.54,CW*.46],10),
 P('Эдгээр allow/deny шалгалтууд39 native тестийн багцад орсон. Нарийвчилсан үр дүн evidence/tests/final-regression-20261116.log-д бий.','small'),
 P('Холбоо: A.5.3, 5.15-5.18, 8.2, 8.3, 8.5, 8.15. Эх бодлого: policies/02-access-control-policy-ISSP.md. [13,15]','small')])

add('7.7. Бодлого III - Эрсдэлийг бууруулах төлөвлөгөө (1/2)',[
 P('POL-03 · Хувилбар1.2 · RTP · Эзэн: CISO · RM-01 v1.0','flat'),
 B('Шийдвэрийн журам'),P('Эрсдэл бүрд бууруулах, зайлсхийх, шилжүүлэх, хүлээн авах стратегиас сонгоно. Шийдвэр нь хөрөнгийн үнэ цэн, магадлал, нөлөөлөл, өртөг, хэрэгжих боломж, үүрэг хариуцлагатай уялдана. Сонгосон хяналт бүрийг SoA-д applicability ба implementation гэсэн тусдаа талбараар илэрхийлнэ.'),
 table([['Эрсдэл','Treatment / ажил','Зорилтот үлдэгдэл'],['RSK-01,09','SoD, grade workflow, MFA, аудит','1×4=4, Бага'],['RSK-02','Тусгаарласан нөөц, patch, restore','1×4=4, Бага'],['RSK-03','Audit лог, гадаад хадгалалтын төлөвлөгөө','1×3=3, Бага'],['RSK-04','RBAC, PII ангилал, экспорт/retention review','1×4=4, Бага'],['RSK-05','Supplier NDA, хугацаатай MFA-VPN','1×4=4, Бага'],['RSK-06,07','JML, шалгалтын сангийн нууцлал','1×3=3, Бага'],['RSK-08,10,11','Secure coding, endpoint, physical controls','1×3=3, Бага'],['RSK-12,13','Staging/backup, CDN/SLA','1×2=2, Бага'],['RSK-14','Мэдээлэх суваг, SETA, хяналттай acceptance','1×2=2, Бага']],[CW*.21,CW*.55,CW*.24],10.5),
 B('Шалгах зарчим'),P('Хэрэгжүүлэх ажил дууссан эсэхийг зөвхөн төлөв эсвэл seed-ээр дүгнэхгүй. Код, тохиргоо, ажиллагааны лог, тест, screenshot эсвэл гэрээ/сургалтын нотолгоо шаардана. Зорилтот үлдэгдэл оноо нь бүрэн хэрэгжүүлсний дараа дахин үнэлэх таамаг юм.'),
 P('Локал хяналт нь бизнесийн workflow, RBAC, програмын audit, incident, Inventory mirror болон restore rehearsal-ийг нотолсон. Кампусын бүх тоног төхөөрөмж, хүний сургалт, гэрээт үйлчилгээний үр дүнг энэ орчноос батлаагүй.','small')])

add('7.8. RTP - Acceptance ба хяналт (2/2)',[
 B('Хариуцлага ба acceptance gate'),P('Хөрөнгийн эзэн үр дагаврыг тодорхойлно. Шинжээч эрсдэлийн оноо ба treatment-ийн нотолгоог шинэчилнэ. Техникийн баг хяналтыг хэрэгжүүлж шалгана. CISO шаардлагатай шалгуур хангагдсаны дараа action-аар accepted_by/date-г батална. Үнэлгээ өөрчлөгдвөл өмнөх acceptance хүчин төгөлдөр хэвээр үлдэхгүй.'),
 B('Дахин үнэлэх trigger'),bullet('Шинэ мэдээллийн систем, нийлүүлэгч, өгөгдлийн төрөл нэмэгдэх.'),bullet('Ноцтой зөрчил, audit finding, сэргээх туршилтын алдаа гарах.'),bullet('Хууль, гэрээ, удирдлагын чиглэл эсвэл сургалтын үйл ажиллагаа өөрчлөгдөх.'),bullet('Төлөвлөсөн хугацаанд treatment дуусаагүй буюу хамгаалалтын үр нөлөө буурах.'),
 table([['Одоогийн ажил','Нотлогдсон хүрээ','Дараагийн шалгалт'],['Дүнгийн батлалт','72→85, тусдаа actor, revision','Хүний demo ба улирлын audit'],['Application audit','Write/unlink deny, pre/post actor','External sink, retention, integrity'],['Local backup/restore','10 хүснэгт,190 attachment checksum','Offsite immutable, failure rehearsal'],['MFA','Module installed, enrollment шалгаагүй','Тусдаа account enrollment/login test'],['Physical / supplier','Asset/risk/policy бүртгэл','Карт/CCTV/VPN/гэрээний бодит evidence'],['SETA','Demo policy acknowledgment','Бодит сургалтын ирц, үр дүн']],[CW*.23,CW*.41,CW*.36],10.5),
 P('Төлөвлөсөн хяналт бүрийн эзэн, хугацааг эрсдэлийн бүртгэлд хадгална. Үлдэгдэл эрсдэл зөвшөөрөгдөхгүй хэвээр бол удирдлагад дахин шийдвэрлүүлнэ. Хүлээн авах нь эрсдэлийг орхих бус, шийдвэр ба хариуцлагаа баримтжуулсан удирдлагын үйлдэл юм.'),
 P('Холбоо: Clause 6.1.2, 6.1.3, 8.2, 8.3, 9.1. Эх бодлого: policies/03-risk-treatment-plan-RTP.md. [4,5,15]','small')])

add('8. RBAC, аудит ба SoA',[
 B('8.1. Хэрэглэгч ба эрхийн бодит шалгалт'),P('19 идэвхтэй internal account байгаа snapshot-д кейсийн11 хэрэглэгч, академик7 demo хэрэглэгч, администратор багтана. Demo нууц үгийг private файлд хадгалж тайланд оруулаагүй. Case account нэр нь багийн гишүүн өөрөө нэвтэрсэн гэсэн нотолгоо биш. [10,14]'),
 table([['Үүрэг','Унших хүрээ','Өөрчлөх хүрээ / хориг'],['Оюутан','Өөрийн student/enrollment','Дүн засахгүй; бусдыг харахгүй'],['Багш','Өөрийн offering-ийн мэдээлэл','Өөрийн хичээлд хүсэлт; approveгүй'],['Сургалтын алба','Академик бүртгэл','Өөр хүний submitted хүсэлт approve'],['ISMS Reporter','Өөрийн incident, бодлого','Incident мэдээлэх, өөрийн ack'],['Asset owner','Хариуцсан asset/risk','Зөвшөөрсөн хүрээнд asset/risk'],['ISMS Analyst','Хөрөнгө, эрсдэл, incident','Investigate/Resolve; Closeгүй'],['CISO / Manager','ISMS нийт бүртгэл','Policy approve, acceptance, Close'],['Дотоод аудитор','ISMS ба academic audit scope','Унших; write/unlink хориг']],[CW*.24,CW*.36,CW*.4],10),
 B('Тестийн үр дүн'),table([['Модуль','Тест','Үр дүн'],['campus_university','11','PASS'],['campus_isms_bridge','3','PASS'],['university_isms','18','PASS'],['university_isms_stock','1','PASS'],['university_isms_helpdesk','6','PASS'],['Нийт','39','0 failed, 0 errors']],[CW*.6,CW*.15,CW*.25],10.5),
 P('Эрхийн зөвшөөрөх, хориглох хоёр талыг; direct write, context forgery, state skipping, stale revision, reporter isolation болон auditor read-only-г шалгасан. Системийн бүх боломжит эмзэг байдлыг бүрэн үгүйсгэсэн дүгнэлт биш. [13]','small')
],8)

add('8.2. Аудит ба сэргээх нотолгоо',[
 *figure('16-grade-audit-detail.png','Зураг 5. Дүнгийн audit: батлагч, цаг, дүн ба revision-ийн өөрчлөлт.',210),
 P('isms.audit.mixin нь хамруулсан model-ийн create/write/unlink болон workflow өөрчлөлтийг actor, timestamp, model, record, pre/post мэдээлэлтэй хадгална. Campus bridge-ийн grade audit-д батлагч campus.reviewer, дүн72→85, revision0→1 зөв таарсан. Audit model-ийн write/unlink-ийг хэрэглэгчид болон ORM түвшинд хориглосон. CLI үйлдэлд IP хоосон байж болно.'),
 P('Энэ нь програмын түвшний хамгаалалт. PostgreSQL-ийн бүрэн эрхтэй администратороос тусгаарласан WORM хадгалалт эсвэл бүх уншилт, бүх сүлжээний үйлдлийн лог гэж үзээгүй. Гадаад log sink, хадгалах хугацаа, хандалтын хяналтыг дараагийн ажилд төлөвлөнө.'),
 table([['Сэргээх шалгалт','Бодит үр дүн'],['Хугацаа','2026-11-16, 11:22:59-11:23:55 (UTC+8)'],['Өгөгдөл','PostgreSQL custom dump + filestore tar'],['Тусдаа DB','orgil_restore_20261116_032259; primary overwriteгүй'],['Харьцуулалт','10 хүснэгтийн count,190 attachment SHA1 таарсан'],['Сэргээх / нийт','48.414сек / 55.974сек'],['Cleanup','Туршилтын DB устсан; веб буцаж ассан']],[CW*.32,CW*.68],10.2),
 P('Нөөцийн snapshot нь Helpdesk sync-ээс өмнөх6 incident,0ticket-тэй байсан; count-ийг тухайн snapshot-той нь тулгасан. Одоогийн live snapshot7incident/7ticket. Local backup нь NAS/offsite/immutable эсвэл шифрлэгдсэн хадгалалт гэсэн нотолгоо биш. [12]','small')])

for index,part in enumerate([controls[:12],controls[12:]]):
 rows=[['Хяналт / хамаарал','Хэрэгжилт','Үндэслэл ба хүрээ']]
 for x in part:
  rows.append([x['control_code']+' '+x['name_mn']+'\nЭзэн: '+x['responsible_login'],'Хамаарал: Тийм\n'+stat[x['implementation']],x['justification']+'\n'+proof[x['control_code']]])
 add('8.3. Statement of Applicability - '+('I' if index==0 else 'II'),[
 P('Бүртгэлд Annex A-ийн93 хяналт байна. Доорх25 нь энэ төслийн сонгосон хүрээ бөгөөд бүгд кейст хамааралтай. Applicability нь хэрэгцээг, implementation нь бодит хэрэгжилтийг тус тус илэрхийлнэ. Сонгоогүй хяналтыг автоматаар хамаарахгүй гэж үзээгүй.'),table(rows,[CW*.32,CW*.17,CW*.51],8.6),
 P('Хэрэгжсэн15, хэсэгчилсэн10. “Тийм” нь тайланд тайлбарласан локал prototype-ийн хүрээнд үнэлсэн. “Хэсэгчилсэн” нь хэрэгжсэн хэсэг болон үлдэх ажлыг тодорхой ялгасан төлөв юм. Бүх их сургуулийн ISO баталгаажуулалтын дүгнэлт биш. [14]','small')])

add('9. Дүгнэлт ба сайжруулалт',[
 P('Их сургуулийн дүнгийн өөрчлөлтийг зөвхөн техникийн засвар бус, эрх бүхий хүсэлт, тусдаа зөвшөөрөл, мөрдөх нотолгоотой удирдлагын процесс болгон хэрэгжүүлэв. Оюутны өөрийн мэдээлэл, багшийн хариуцсан хичээл, сургалтын албаны батлалт, аудитын хараат бус байдлыг Odoo-ийн ACL, record rule, серверийн action шалгалтаар холбосон.'),
 P('Хөрөнгө16, эрсдэл14, сонгосон хяналт25, үндсэн бодлого3, Helpdesk5шат нь нэг кейсийн мэдээллээр уялдсан. Бодит дүнгийн72→85батлалт,7incident/7ticket,39тест болон190attachmentтай сэргээх rehearsal нь хэрэгжүүлэлтийн нотолгоо болов. SoA хэрэгжсэн ба төлөвлөсөн ажлыг ялгаж, шийдвэр гаргагчид үлдэх эрсдэлийг харах боломж өгнө.'),
 B('Дараагийн сайжруулалт'),table([['Эрэмбэ','Ажил','Хүлээн авах нотолгоо'],['1','MFA enrollment ба privileged account review','Account enrollment + login recovery test'],['2','Offsite immutable backup ба external audit sink','Restore rehearsal, retention/integrity check'],['3','JML ба supplier access workflow','Баталсан request, revoke хугацаа, VPN log'],['4','SETA ба бодлогын rollout','Бодит ирц, үнэлгээ, version-specific ack'],['5','Ачаалал, export, retention, privacy review','Хэмжилт, approved retention, data access audit']],[CW*.13,CW*.43,CW*.44],10.5),
 B('AI хэрэглээ ба хүний оролцоо'),P('Codex, OpenCode болон бусад AI агентуудыг заавар ба лекц судлах, кейс төлөвлөх, код хөгжүүлэх, суулгалт, тест, screenshot авах, тайлан бэлтгэхэд ашиглав. Харилцаа management/messages.md, явц worklog.md-д хадгалагдана. Кейсийн өгөгдөл зохиомол; тест, screenshot нь ажилласан орчноос гарсан.'),
 P('Хүний багийн хариуцах үүргийг хуудас4-т өгсөн. Агентын account ашигласан ажиллагааг хүний өөрийн гүйцэтгэл гэж зохиогоогүй. Гишүүд эцсийн бүтээлийг уншиж, өөрсдийн хэрэглэгчээр шалган, тайлбарлаж хамгаалах ба бодит хувь нэмрээ огноо, өөрчлөлт, нотолгоотой worklog-д бүртгэнэ.','small')
],9)

add('10. Хавсралт · 11. Эх сурвалж',[
 B('10.1. Ажиллуулах ба demo'),P('Үндсэн хавтас: biydaalt/. odoo/ дотор docker compose up -d; веб хаяг http://127.0.0.1:8069. Тохиргоо ба нууц үг .env, evidence/private/ дор хамгаалагдсан. Нууц үгийг тайлан, слайд, source archive-д оруулахгүй. Одоо байгаа DB-г эхлүүлэхэд importer дахин ажиллуулах шаардлагагүй.','small'),
 P('Demo дараалал: кейс ба архитектур(2мин),16asset/14risk/SoA(2мин),дүнгийн хүсэлт ба тусдаа батлалт(3мин),incident/Helpdesk(2мин),RBAC/audit/restore(2мин),дүгнэлт(1мин). Дэлгэрэнгүй reports/demo-script.md болон management/odoo-guide.md.','small'),
 P('Нотолгооны индекс: evidence/screenshots/01-16, evidence/tests/final-regression-20261116.log, live-exercise.json, inventory-catalog.json, backup-restore-20261116_032259.json. Бүрэн шаардлагын матриц: management/requirements.md; сургалтын эхийн зураглал: course-review.md; нэр томьёо: glossary.md.','small'),
 B('11. Ашигласан эх сурвалж'),
 P('[1] Багшийн “БД төсөл_ Odoo ERP-ISO27001 26-27А.pdf”,6 хуудас, бие даалтын заавар.','small'),
 P('[2] Лекц1-2: Мэдээллийн аюулгүй байдлын засаглал ба менежментийн үндэс. Хичээлийн локал эх; course-review.md-д source path-тай.','small'),
 P('[3] Лекц4-5: Засаглал, бодлого, EISP/ISSP/SysSP. Өмнөх семинарын бодлого ба ёс зүйн тайлангууд.','small'),
 P('[4] ISO/IEC 27001:2022. Information security, cybersecurity and privacy protection - Information security management systems - Requirements. ISO, 2022. <link href="https://www.iso.org/standard/27001" color="black">iso.org/standard/27001</link>.','small'),
 P('[5] Лекц8-9, слайд19: 5×5 эрсдэлийн матриц; Sem10: assets/risks/CIA ажлын файл. RM-01 шийдвэрийн тайлбар management/decisions.md D04.','small'),
 P('[6] Odoo18 documentation. Security in Odoo; access rights, record rules, field access, security pitfalls. <link href="https://www.odoo.com/documentation/18.0/developer/reference/backend/security.html" color="black">odoo.com/documentation/18.0/.../security.html</link>.','small'),
 P('[7] Odoo18 documentation. Server framework, ORM, module structure. <link href="https://www.odoo.com/documentation/18.0/developer/tutorials/server_framework_101.html" color="black">odoo.com/documentation/18.0</link>.','small'),
 P('[8] OCA/helpdesk, helpdesk_mgmt, branch18.0, commit9fbf485f7ab7961fd06250965990523e05e00ecd. AGPL-3. SOURCE-PROVENANCE.json.','small'),
 P('[9] Deployment: odoo/docker-compose.yml, management/environment-audit.md, odoo/README.md. [10] Live evidence: evidence/tests/live-exercise.json ба campus-ui-manifest.json.','small'),
 P('[11] Inventory evidence: inventory-catalog.json. [12] Restore evidence: backup-restore-20261116_032259.json. [13] Native regression: final-regression-20261116.log,39тест.','small'),
 P('[14] data/soa.csv, controls_soa.json; management/soa-qa.md. [15] policies/01-03*.md. Өөрийн төслийн баримт ба нотолгоо, 2026-11-16.','small')
],10)

assert len(pages)==28,len(pages)
c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('Formula University - Odoo ERP ба ISO/IEC 27001:2022');c.setAuthor('Formula 5');c.setSubject('F.NSA338 бие даалт, AI-assisted software implementation')
usage=[]
for i,page in enumerate(pages,1):
 c.bookmarkPage('page'+str(i))
 if page['section'] is not None: c.addOutlineEntry(page['title'],'page'+str(i),0,False)
 if i>1:
  c.setFont('Body',9);c.setFillColor(colors.black);c.drawString(LEFT,H-13*mm,'Formula 5 | Formula University | F.NSA338')
  c.setLineWidth(.3);c.line(LEFT,H-15*mm,W-RIGHT,H-15*mm)
  c.drawCentredString(W/2,12*mm,str(i))
 items=([B(page['title'])] if i>2 else [])+page['items']
 frame=Frame(LEFT,BOTTOM,CW,CH,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
 original=len(items);frame.addFromList(items,c)
 if items: raise RuntimeError(f'Page {i} overflow: {len(items)} of {original}, first={str(items[0])[:180]}')
 usage.append({'page':i,'title':page['title'],'remaining_height':round(frame._y-BOTTOM,2)})
 c.showPage()
c.save()
(WS/'work/report/layout.json').write_text(json.dumps(usage,ensure_ascii=False,indent=2))
print(json.dumps({'output':str(OUT),'pages':len(pages),'bytes':OUT.stat().st_size,'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()},ensure_ascii=False))
