-- ============================================================
-- dict_industry 种子数据（行业树 + 关键词）
-- 幂等：列不存在才加；code 不存在才插
-- 关键词供 data_clean.load_industries / infer_industry_id 匹配
-- ============================================================

-- 1) 补 keywords 列（老库没有）
SET @has_kw := (SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name='dict_industry' AND column_name='keywords');
SET @ddl := IF(@has_kw = 0,
    'ALTER TABLE dict_industry ADD COLUMN `keywords` VARCHAR(512) NOT NULL DEFAULT '''' COMMENT ''匹配关键词，逗号分隔'' AFTER `name`',
    'SELECT 1');
PREPARE s FROM @ddl; EXECUTE s; DEALLOCATE PREPARE s;

-- 2) 一级行业（parent_id=0）
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'gc', '工程建设', '', 1, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='gc');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'sb', '设备货物', '', 2, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='sb');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'xxh', '信息化', '', 3, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='xxh');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'fw', '商务服务', '', 4, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='fw');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'jy', '教育培训', '', 5, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='jy');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'yl', '医疗卫生', '', 6, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='yl');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'why', '文化体育', '', 7, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='why');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'nl', '农林牧渔', '', 8, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='nl');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'sm', '商贸物流', '', 9, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='sm');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'sh', '社会公共', '', 10, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='sh');
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT 0, 'qt', '其他行业', '其他', 99, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code='qt');

-- 3) 二级行业：(code, 父code, name, keywords)
INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'sz' code, 'gc' pc, '市政工程' name, '道路,桥梁,隧道,管网,路灯,排水,排污,人行道,城市道路,市政' kw, 1 sort
      UNION ALL SELECT 'fw2','gc','房屋建筑','房屋,建筑,楼房,办公楼,厂房,宿舍,居住用房,事业单位用房,业务用房,用房',2
      UNION ALL SELECT 'zx','gc','装修装饰','装修,装饰,装潢,幕墙,门窗,吊顶,涂料,粉刷,修缮',3
      UNION ALL SELECT 'yl2','gc','园林绿化','园林,绿化,景观,植树,养护,花木,庭院',4
      UNION ALL SELECT 'sl','gc','水利工程','水利,水库,河道,堤防,灌渠,供水,防汛,治水',5
      UNION ALL SELECT 'dl','gc','电力工程','电力,电气,变电站,输配电,线路架设,电缆敷设,光伏,风电,电网',6
      UNION ALL SELECT 'jt','gc','交通工程','公路,铁路,轨道,机场,港口,航道,高速',7
      UNION ALL SELECT 'hb','gc','环保工程','环保,污水处理,垃圾,固废,废气,脱硫,除尘,环境治理,排污口',8
      UNION ALL SELECT 'xf','gc','消防工程','消防,火灾,喷淋,灭火,防火,烟感',9
      UNION ALL SELECT 'jc','gc','基础工程','桩基,地基,土方,开挖,回填,脚手架,基坑,基础施工',10
      UNION ALL SELECT 'gcsj','gc','工程设计监理','工程设计,勘察,监理,造价,可研,可行性研究,评估,检测,咨询',11
      UNION ALL SELECT 'zb','gc','工程总承包','总承包,总包,代建,项目管理',12
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'ty' code, 'sb' pc, '通用设备' name, '设备,机械,机床,泵,阀,压缩机,起重,仪器仪表,实验设备' kw, 1 sort
      UNION ALL SELECT 'bg','sb','办公设备','办公设备,打印机,复印机,扫描仪,家具,桌椅,文件柜,电脑,计算机',2
      UNION ALL SELECT 'jy2','sb','教学设备','教学设备,实验台,实训,黑板,课桌,多媒体教室,教学仪器',3
      UNION ALL SELECT 'yl3','sb','医疗设备','医疗器械,诊断设备,手术,病床,监护仪,ct,核磁,b超,内窥镜',4
      UNION ALL SELECT 'dz','sb','电子电器','电器,电子,空调,冰箱,电视,开关,插座,照明,电梯',5
      UNION ALL SELECT 'cg','sb','交通工具','车辆,汽车,货车,客车,船舶,飞机,特种车',6
      UNION ALL SELECT 'jscl','sb','金属材料','钢材,钢铁,铝材,铜材,型材,管材,金属制品,钢筋',7
      UNION ALL SELECT 'jzcl','sb','建筑材料','水泥,混凝土,砂石,砖,石材,玻璃,防水材料,保温',8
      UNION ALL SELECT 'shg','sb','石油化工','石油,化工,燃料,汽油,柴油,涂料,沥青,天然气',9
      UNION ALL SELECT 'mt','sb','煤炭矿产','煤炭,矿山,采选,选矿,矿产,勘探',10
      UNION ALL SELECT 'fz','sb','服装被具','服装,制服,衣被,纺织,布料,鞋帽,床上用品',11
      UNION ALL SELECT 'cl','sb','仓储物料','物资,耗材,材料,用品,备件,配件,五金',12
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'rj' code, 'xxh' pc, '软件开发' name, '软件,系统开发,平台开发,app,小程序,代码,信息系统开发' kw, 1 sort
      UNION ALL SELECT 'xtjc','xxh','系统集成','系统集成,综合布线,机房建设,弱电,智能化,安防工程',2
      UNION ALL SELECT 'wltx','xxh','网络通信','网络,通信,交换机,路由器,光纤,专线,基站,5g,宽带',3
      UNION ALL SELECT 'sjzx','xxh','数据中心','数据中心,服务器,存储,云计算,虚拟化,机房',4
      UNION ALL SELECT 'afjk','xxh','安防监控','安防,监控,摄像头,门禁,报警系统,对讲,视频监控',5
      UNION ALL SELECT 'wlyw','xxh','信息化运维','运维,驻场,技术支持,保障服务,信息安全,等保',6
      UNION ALL SELECT 'sjy','xxh','数据与算法','大数据,人工智能,算法,数据治理,数据库,中台',7
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'wy' code, 'fw' pc, '物业管理' name, '物业,保洁,保安,绿化养护,维修服务,后勤' kw, 1 sort
      UNION ALL SELECT 'hy','fw','会议会展','会议,会展,展览,会务,论坛,推介会,洽谈会,发布会,展示会',2
      UNION ALL SELECT 'gg','fw','广告宣传','广告,宣传,推广,品牌,媒体投放,标识,展板',3
      UNION ALL SELECT 'ys','fw','印刷服务','印刷,印制,标签,名片,宣传品,画册,装订',4
      UNION ALL SELECT 'zx2','fw','咨询服务','咨询,策划,调研,评估,审计,法务,战略',5
      UNION ALL SELECT 'rlzy','fw','人力资源','招聘,劳务派遣,用工服务,人才服务,猎头',6
      UNION ALL SELECT 'zl','fw','租赁服务','租赁,租借,借用,设备租赁,场地租赁',7
      UNION ALL SELECT 'bx','fw','保险服务','保险,承保,理赔,再保险',8
      UNION ALL SELECT 'wy2','fw','维护修理','维修,保养,修理,维护,年检,校准',9
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'gd' code, 'jy' pc, '高等教育' name, '大学,高校,学院,研究生,本科,继续教育,成人教育,学历教育' kw, 1 sort
      UNION ALL SELECT 'zyjy','jy','职业培训','培训,实训,考证,资格认证,技能大赛,研修,进修,继续教育培训',2
      UNION ALL SELECT 'jcjy','jy','基础教育','中小学,小学,中学,幼儿园,义务教育,高中,职业教育',3
      UNION ALL SELECT 'tssc','jy','教材图书','教材,课本,图书,文献,教辅,期刊',4
      UNION ALL SELECT 'zhjy','jy','智慧教育','智慧教育,在线教育,录播,电子班牌,教学平台',5
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'yy' code, 'yl' pc, '医疗服务' name, '医院,诊疗,门诊,住院,卫生院,体检,救治' kw, 1 sort
      UNION ALL SELECT 'ggws','yl','公共卫生','公共卫生,疫苗,防疫,疾控,传染病,卫生监督',2
      UNION ALL SELECT 'yp','yl','药品耗材','药品,药材,试剂,医用耗材,敷料,疫苗采购',3
      UNION ALL SELECT 'ylyl','yl','医疗信息化','his,电子病历,挂号,医院信息,智慧医疗',4
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'whys' code, 'why' pc, '文化艺术' name, '文化,艺术,演出,文物,非遗,图书馆,剧团,展览馆' kw, 1 sort
      UNION ALL SELECT 'tyfw','why','体育服务','体育,运动,健身,赛事,场馆,器材,球类',2
      UNION ALL SELECT 'ylzy','why','娱乐旅游','娱乐,旅游,景区,酒店,餐饮,民宿,度假',3
      UNION ALL SELECT 'ty2','why','体育用房','体育和娱乐用房,体育馆,健身中心,活动中心',4
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'ny' code, 'nl' pc, '农业' name, '农业,种植,农机,化肥,农药,种子,灌溉,大棚' kw, 1 sort
      UNION ALL SELECT 'ly','nl','林业','林业,造林,护林,森林,防火,苗圃',2
      UNION ALL SELECT 'xmy','nl','畜牧渔业','畜牧,养殖,兽医,渔业,水产,饲料,防疫',3
      UNION ALL SELECT 'ny2','nl','农产品','农产品,粮食,蔬菜,水果,粮油,初级农产品',4
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'ls' code, 'sm' pc, '零售批发' name, '零售,批发,商超,超市,便利店,电商,直营店' kw, 1 sort
      UNION ALL SELECT 'wl','sm','物流运输','物流,运输,货运,配送,仓储,快递,搬运',2
      UNION ALL SELECT 'sp','sm','食品材料','食品,食材,粮油,蔬菜,肉类,副食,食堂物资',3
      UNION ALL SELECT 'sp2','sm','商业服务用房','商业和服务业用房,商铺,营业厅,卖场',4
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

INSERT INTO dict_industry (parent_id, code, name, keywords, sort, status)
SELECT p.id, c.code, c.name, c.kw, c.sort, 1
FROM (SELECT 'shjz' code, 'sh' pc, '社会救助' name, '社会救助,低保,扶贫,福利,养老,残疾,救助物资' kw, 1 sort
      UNION ALL SELECT 'sqfw','sh','社区服务','社区,街道办,居委会,网格,便民,社工',2
      UNION ALL SELECT 'gggl','sh','公共管理','政府机关,行政,审批,公共设施,公共设施管理,市政管理',3
      UNION ALL SELECT 'ga','sh','公安司法','公安,法院,检察,司法,监狱,禁毒,交警',4
      UNION ALL SELECT 'rc','sh','人才就业','就业服务,招聘服务,招聘会,社保,公积金,职业介绍,人才中介,人力资源服务,人事代理,人才派遣',5
      UNION ALL SELECT 'zt','sh','土地整治','土地,平整,复垦,测绘,规划,确权',6
) c JOIN dict_industry p ON p.code = c.pc
WHERE NOT EXISTS (SELECT 1 FROM dict_industry WHERE code=c.code);

-- ------------------------------------------------------------
-- 4) 关键词同步（已存在的行也刷新为本文件定义的关键词）
-- ------------------------------------------------------------
UPDATE dict_industry d JOIN (
    SELECT 'sz' code, '市政工程' name, '道路,桥梁,隧道,管网,路灯,排水,排污,人行道,城市道路,市政' kw
    UNION ALL SELECT 'fw2','房屋建筑','房屋,建筑,楼房,办公楼,厂房,宿舍,居住用房,事业单位用房,业务用房,用房'
    UNION ALL SELECT 'zx','装修装饰','装修,装饰,装潢,幕墙,门窗,吊顶,涂料,粉刷,修缮'
    UNION ALL SELECT 'yl2','园林绿化','园林,绿化,景观,植树,养护,花木,庭院'
    UNION ALL SELECT 'sl','水利工程','水利,水库,河道,堤防,灌渠,供水,防汛,治水'
    UNION ALL SELECT 'dl','电力工程','电力,电气,变电站,输配电,线路架设,电缆敷设,光伏,风电,电网'
    UNION ALL SELECT 'jt','交通工程','公路,铁路,轨道,机场,港口,航道,高速'
    UNION ALL SELECT 'hb','环保工程','环保,污水处理,垃圾,固废,废气,脱硫,除尘,环境治理,排污口'
    UNION ALL SELECT 'xf','消防工程','消防,火灾,喷淋,灭火,防火,烟感'
    UNION ALL SELECT 'jc','基础工程','桩基,地基,土方,开挖,回填,脚手架,基坑,基础施工'
    UNION ALL SELECT 'gcsj','工程设计监理','工程设计,勘察,监理,造价,可研,可行性研究,评估,检测,咨询'
    UNION ALL SELECT 'zb','工程总承包','总承包,总包,代建,项目管理'
    UNION ALL SELECT 'ty','通用设备','设备,机械,机床,泵,阀,压缩机,起重,仪器仪表,实验设备'
    UNION ALL SELECT 'bg','办公设备','办公设备,打印机,复印机,扫描仪,家具,桌椅,文件柜,电脑,计算机'
    UNION ALL SELECT 'jy2','教学设备','教学设备,实验台,实训,黑板,课桌,多媒体教室,教学仪器'
    UNION ALL SELECT 'yl3','医疗设备','医疗器械,诊断设备,手术,病床,监护仪,ct,核磁,b超,内窥镜'
    UNION ALL SELECT 'dz','电子电器','电器,电子,空调,冰箱,电视,开关,插座,照明,电梯'
    UNION ALL SELECT 'cg','交通工具','车辆,汽车,货车,客车,船舶,飞机,特种车'
    UNION ALL SELECT 'jscl','金属材料','钢材,钢铁,铝材,铜材,型材,管材,金属制品,钢筋'
    UNION ALL SELECT 'jzcl','建筑材料','水泥,混凝土,砂石,砖,石材,玻璃,防水材料,保温'
    UNION ALL SELECT 'shg','石油化工','石油,化工,燃料,汽油,柴油,涂料,沥青,天然气'
    UNION ALL SELECT 'mt','煤炭矿产','煤炭,矿山,采选,选矿,矿产,勘探'
    UNION ALL SELECT 'fz','服装被具','服装,制服,衣被,纺织,布料,鞋帽,床上用品'
    UNION ALL SELECT 'cl','仓储物料','物资,耗材,材料,用品,备件,配件,五金'
    UNION ALL SELECT 'rj','软件开发','软件,系统开发,平台开发,app,小程序,代码,信息系统开发'
    UNION ALL SELECT 'xtjc','系统集成','系统集成,综合布线,机房建设,弱电,智能化,安防工程'
    UNION ALL SELECT 'wltx','网络通信','网络,通信,交换机,路由器,光纤,专线,基站,5g,宽带'
    UNION ALL SELECT 'sjzx','数据中心','数据中心,服务器,存储,云计算,虚拟化,机房'
    UNION ALL SELECT 'afjk','安防监控','安防,监控,摄像头,门禁,报警系统,对讲,视频监控'
    UNION ALL SELECT 'wlyw','信息化运维','运维,驻场,技术支持,保障服务,信息安全,等保'
    UNION ALL SELECT 'sjy','数据与算法','大数据,人工智能,算法,数据治理,数据库,中台'
    UNION ALL SELECT 'wy','物业管理','物业,保洁,保安,绿化养护,维修服务,后勤'
    UNION ALL SELECT 'hy','会议会展','会议,会展,展览,会务,论坛,推介会,洽谈会,发布会,展示会'
    UNION ALL SELECT 'gg','广告宣传','广告,宣传,推广,品牌,媒体投放,标识,展板'
    UNION ALL SELECT 'ys','印刷服务','印刷,印制,标签,名片,宣传品,画册,装订'
    UNION ALL SELECT 'zx2','咨询服务','咨询,策划,调研,评估,审计,法务,战略'
    UNION ALL SELECT 'rlzy','人力资源','招聘,劳务派遣,用工服务,人才服务,猎头'
    UNION ALL SELECT 'zl','租赁服务','租赁,租借,借用,设备租赁,场地租赁'
    UNION ALL SELECT 'bx','保险服务','保险,承保,理赔,再保险'
    UNION ALL SELECT 'wy2','维护修理','维修,保养,修理,维护,年检,校准'
    UNION ALL SELECT 'gd','高等教育','大学,高校,学院,研究生,本科,继续教育,成人教育,学历教育'
    UNION ALL SELECT 'zyjy','职业培训','培训,实训,考证,资格认证,技能大赛,研修,进修,继续教育培训'
    UNION ALL SELECT 'jcjy','基础教育','中小学,小学,中学,幼儿园,义务教育,高中,职业教育'
    UNION ALL SELECT 'tssc','教材图书','教材,课本,图书,文献,教辅,期刊'
    UNION ALL SELECT 'zhjy','智慧教育','智慧教育,在线教育,录播,电子班牌,教学平台'
    UNION ALL SELECT 'yy','医疗服务','医院,诊疗,门诊,住院,卫生院,体检,救治'
    UNION ALL SELECT 'ggws','公共卫生','公共卫生,疫苗,防疫,疾控,传染病,卫生监督'
    UNION ALL SELECT 'yp','药品耗材','药品,药材,试剂,医用耗材,敷料,疫苗采购'
    UNION ALL SELECT 'ylyl','医疗信息化','his,电子病历,挂号,医院信息,智慧医疗'
    UNION ALL SELECT 'whys','文化艺术','文化,艺术,演出,文物,非遗,图书馆,剧团,展览馆'
    UNION ALL SELECT 'tyfw','体育服务','体育,运动,健身,赛事,场馆,器材,球类'
    UNION ALL SELECT 'ylzy','娱乐旅游','娱乐,旅游,景区,酒店,餐饮,民宿,度假'
    UNION ALL SELECT 'ty2','体育用房','体育和娱乐用房,体育馆,健身中心,活动中心'
    UNION ALL SELECT 'ny','农业','农业,种植,农机,化肥,农药,种子,灌溉,大棚'
    UNION ALL SELECT 'ly','林业','林业,造林,护林,森林,防火,苗圃'
    UNION ALL SELECT 'xmy','畜牧渔业','畜牧,养殖,兽医,渔业,水产,饲料,防疫'
    UNION ALL SELECT 'ny2','农产品','农产品,粮食,蔬菜,水果,粮油,初级农产品'
    UNION ALL SELECT 'ls','零售批发','零售,批发,商超,超市,便利店,电商,直营店'
    UNION ALL SELECT 'wl','物流运输','物流,运输,货运,配送,仓储,快递,搬运'
    UNION ALL SELECT 'sp','食品材料','食品,食材,粮油,蔬菜,肉类,副食,食堂物资'
    UNION ALL SELECT 'sp2','商业服务用房','商业和服务业用房,商铺,营业厅,卖场'
    UNION ALL SELECT 'shjz','社会救助','社会救助,低保,扶贫,福利,养老,残疾,救助物资'
    UNION ALL SELECT 'sqfw','社区服务','社区,街道办,居委会,网格,便民,社工'
    UNION ALL SELECT 'gggl','公共管理','政府机关,行政,审批,公共设施,公共设施管理,市政管理'
    UNION ALL SELECT 'ga','公安司法','公安,法院,检察,司法,监狱,禁毒,交警'
    UNION ALL SELECT 'rc','人才就业','就业服务,招聘服务,招聘会,社保,公积金,职业介绍,人才中介,人力资源服务,人事代理,人才派遣'
    UNION ALL SELECT 'zt','土地整治','土地,平整,复垦,测绘,规划,确权'
) t ON t.code = d.code
SET d.keywords = t.kw, d.name = t.name;
