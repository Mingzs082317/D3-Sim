# d3_v11.31.py
# Mindray BeneHeart D3 Sim v11.31 - 临床安全与复盘系统 (动态阻抗+安全拦截)
# 基于 v10.1.3 升级，修复ECG冻结/解除及ECG Lab问题

import tkinter as tk
from tkinter import Canvas, messagebox, Toplevel, Label, Button, Scale, OptionMenu, StringVar, simpledialog, Checkbutton, IntVar, Frame, ttk
import random
import math
import time
import traceback
import pygame
import os
import sys
from pathlib import Path
from datetime import datetime
import json

# ==================== 智能音效加载 ====================

def find_sound_file(fname):
    """智能查找音效文件 - 支持任意位置"""
    paths = []
    
    if env := os.environ.get("D3_SOUND"):
        paths.append(Path(env) / fname)
    
    try:
        script_dir = Path(__file__).parent
        for sub in ["sounds", "audio", "sound", "sfx", ""]:
            paths.append(script_dir / sub / fname)
    except:
        pass
    
    try:
        cwd = Path.cwd()
        for sub in ["sounds", "audio", "sound", "sfx", ""]:
            paths.append(cwd / sub / fname)
    except:
        pass
    
    try:
        home = Path.home()
        for sub in ["Documents/D3_Sounds", "D3_Sounds", ".d3_sounds"]:
            paths.append(home / sub / fname)
    except:
        pass
    
    if getattr(sys, 'frozen', False):
        try:
            exe_dir = Path(sys.executable).parent
            for sub in ["sounds", "audio", "sound", "sfx", ""]:
                paths.append(exe_dir / sub / fname)
            paths.append(Path(sys.executable).parent / "_internal" / "sounds" / fname)
        except:
            pass
    
    for p in paths:
        try:
            if p.exists() and p.is_file():
                print(f"✅ 找到音效: {p}")
                return str(p)
        except:
            continue
    
    print(f"⚠️ 未找到音效: {fname}")
    return None

pygame.mixer.init()

sound_charging = None
sound_charged = None
sound_shock = None
sound_rosc = None  # ROSC音效

sound_files = ["charging.mp3", "charged.mp3", "shock.mp3", "rosc.mp3"]
for sf in sound_files:
    path = find_sound_file(sf)
    if path:
        try:
            sound = pygame.mixer.Sound(path)
            if sf == "charging.mp3":
                sound_charging = sound
            elif sf == "charged.mp3":
                sound_charged = sound
            elif sf == "shock.mp3":
                sound_shock = sound
            elif sf == "rosc.mp3":
                sound_rosc = sound
            print(f"✅ 加载成功: {sf}")
        except Exception as e:
            print(f"⚠️ 加载失败 {sf}: {e}")

loaded_count = sum(1 for s in [sound_charging, sound_charged, sound_shock, sound_rosc] if s is not None)
print(f"✅ 音效加载: {loaded_count}/4")

# ==================== 药品库系统 (AHA/PALS标准) ====================

class DrugDatabase:
    """AHA/PALS标准抢救药物数据库"""
    
    CATEGORIES = {
        "抗心律失常": ["胺碘酮", "利多卡因", "腺苷", "阿托品", "硫酸镁", "维拉帕米"],
        "血管活性": ["肾上腺素", "多巴胺", "去甲肾上腺素", "多巴酚丁胺", "米力农", "加压素"],
        "抗凝/溶栓": ["阿司匹林", "替格瑞洛", "氯吡格雷", "肝素", "依诺肝素", "阿替普酶"],
        "电解质/补液": ["氯化钾", "氯化钙", "碳酸氢钠", "葡萄糖酸钙", "生理盐水", "乳酸林格液"],
        "镇静/镇痛": ["咪达唑仑", "芬太尼", "吗啡", "丙泊酚", "氯胺酮"],
        "其他": ["呋塞米", "硝酸甘油", "硝普钠", "氨茶碱", "纳洛酮"]
    }
    
    DRUGS = {
        "肾上腺素": {
            "class": "血管活性",
            "indications": ["心脏骤停", "严重过敏反应", "低血压休克"],
            "route": "IV/IO",
            "dose_adult": "1mg q3-5min",
            "dose_child": "0.01mg/kg (0.1ml/kg of 1:10000) q3-5min",
            "max_dose": "无上限 (心脏骤停)",
            "onset": 1,
            "duration": 10,
            "half_life": 2,
            "contraindications": ["嗜铬细胞瘤", "闭角型青光眼"],
            "monitor": ["ECG", "血压", "心率"],
            "color": "#ff4444",
            "formulation": "1mg/1mL (1:1000) 或 1mg/10mL (1:10000)",
            "preparation": "心脏骤停: 1mg IV push; 过敏: 0.3-0.5mg IM"
        },
        "胺碘酮": {
            "class": "抗心律失常",
            "indications": ["室颤/VT无脉", "室速血流动力学稳定", "房颤"],
            "route": "IV/IO",
            "dose_adult": "300mg IV push, 可重复150mg",
            "dose_child": "5mg/kg IV push (max 300mg)",
            "max_dose": "2.2g/24h",
            "onset": 5,
            "duration": 30,
            "half_life": 58,
            "contraindications": ["严重窦房结疾病", "II/III度房室传导阻滞"],
            "monitor": ["ECG", "QT间期", "血压", "肝功能"],
            "color": "#ff8800",
            "formulation": "150mg/3mL 或 300mg/3mL",
            "preparation": "VT/VF: 300mg IV push; 房颤: 负荷量+维持量"
        },
        "利多卡因": {
            "class": "抗心律失常",
            "indications": ["室速", "室颤(无胺碘酮时)", "预防室速"],
            "route": "IV/IO",
            "dose_adult": "1-1.5mg/kg IV push, 可重复0.5-0.75mg/kg",
            "dose_child": "1mg/kg IV push",
            "max_dose": "3mg/kg",
            "onset": 1,
            "duration": 10,
            "half_life": 1.5,
            "contraindications": ["严重窦房结/房室传导阻滞", "预激综合征"],
            "monitor": ["ECG", "QRS间期", "神经系统"],
            "color": "#ffcc00",
            "formulation": "100mg/5mL, 500mg/50mL",
            "preparation": "1-1.5mg/kg IV push"
        },
        "腺苷": {
            "class": "抗心律失常",
            "indications": ["室上速(SVT)"],
            "route": "IV rapid push",
            "dose_adult": "6mg IV push, 若无效12mg",
            "dose_child": "0.1mg/kg (max 6mg), 若无效0.2mg/kg (max 12mg)",
            "max_dose": "12mg",
            "onset": 0.5,
            "duration": 2,
            "half_life": 0.5,
            "contraindications": ["哮喘", "II/III度房室传导阻滞"],
            "monitor": ["ECG", "血压"],
            "color": "#00ccff",
            "formulation": "6mg/2mL, 12mg/4mL",
            "preparation": "快速IV推注 + 生理盐水冲洗"
        },
        "阿托品": {
            "class": "抗心律失常",
            "indications": ["症状性心动过缓", "有机磷中毒", "房室传导阻滞"],
            "route": "IV/IO",
            "dose_adult": "0.5mg IV q3-5min (max 3mg)",
            "dose_child": "0.02mg/kg (min 0.1mg, max 0.5mg)",
            "max_dose": "3mg",
            "onset": 1,
            "duration": 30,
            "half_life": 2,
            "contraindications": ["闭角型青光眼", "前列腺肥大"],
            "monitor": ["心率", "血压"],
            "color": "#88ff88",
            "formulation": "0.4mg/mL, 0.5mg/mL, 1mg/10mL",
            "preparation": "0.5mg IV push"
        },
        "硫酸镁": {
            "class": "抗心律失常",
            "indications": ["尖端扭转型室速", "子痫", "严重哮喘"],
            "route": "IV/IO",
            "dose_adult": "2g IV push, 可重复",
            "dose_child": "25-50 mg/kg (max 2g)",
            "max_dose": "4g",
            "onset": 2,
            "duration": 20,
            "half_life": 4,
            "contraindications": ["重度肾功能不全", "心肌损伤"],
            "monitor": ["血压", "呼吸", "深腱反射"],
            "color": "#99ff99",
            "formulation": "2g/50mL, 4g/100mL, 10g/100mL",
            "preparation": "2g IV push 或 1-4g/h维持"
        },
        "维拉帕米": {
            "class": "抗心律失常",
            "indications": ["房颤/房扑", "室上速", "高血压急症"],
            "route": "IV",
            "dose_adult": "2.5-5mg IV push, 可重复",
            "dose_child": "0.1mg/kg IV",
            "max_dose": "10mg",
            "onset": 2,
            "duration": 20,
            "half_life": 3,
            "contraindications": ["严重心衰", "房室传导阻滞", "预激综合征"],
            "monitor": ["ECG", "血压", "心率"],
            "color": "#66ddff",
            "formulation": "2.5mg/2mL, 5mg/2mL",
            "preparation": "2.5-5mg IV push"
        },
        "多巴胺": {
            "class": "血管活性",
            "indications": ["低血压", "心源性休克", "严重心动过缓"],
            "route": "IV infusion",
            "dose_adult": "2-20 μg/kg/min",
            "dose_child": "2-20 μg/kg/min",
            "max_dose": "50 μg/kg/min",
            "onset": 2,
            "duration": 5,
            "half_life": 2,
            "contraindications": ["嗜铬细胞瘤", "未纠正的快速心律失常"],
            "monitor": ["血压", "心率", "尿量"],
            "color": "#ff66cc",
            "formulation": "40mg/mL, 80mg/100mL, 160mg/100mL",
            "preparation": "按体重计算, 持续泵注"
        },
        "去甲肾上腺素": {
            "class": "血管活性",
            "indications": ["脓毒症休克", "严重低血压", "心源性休克"],
            "route": "IV infusion",
            "dose_adult": "0.01-0.5 μg/kg/min",
            "dose_child": "0.01-0.5 μg/kg/min",
            "max_dose": "1 μg/kg/min",
            "onset": 1,
            "duration": 2,
            "half_life": 1.5,
            "contraindications": ["严重低血容量未纠正"],
            "monitor": ["血压", "心率", "灌注"],
            "color": "#ff2266",
            "formulation": "1mg/mL, 4mg/250mL",
            "preparation": "持续泵注, 中心静脉通路优先"
        },
        "多巴酚丁胺": {
            "class": "血管活性",
            "indications": ["心力衰竭", "心源性休克", "低心排"],
            "route": "IV infusion",
            "dose_adult": "2-20 μg/kg/min",
            "dose_child": "2-20 μg/kg/min",
            "max_dose": "40 μg/kg/min",
            "onset": 2,
            "duration": 5,
            "half_life": 2,
            "contraindications": ["特发性肥厚性主动脉瓣下狭窄"],
            "monitor": ["血压", "心率", "ECG"],
            "color": "#ff88cc",
            "formulation": "250mg/20mL, 500mg/50mL",
            "preparation": "持续泵注"
        },
        "米力农": {
            "class": "血管活性",
            "indications": ["心力衰竭", "心源性休克", "低心排"],
            "route": "IV infusion",
            "dose_adult": "负荷25-50 μg/kg + 维持0.25-0.75 μg/kg/min",
            "dose_child": "负荷50 μg/kg + 维持0.5-1 μg/kg/min",
            "max_dose": "1 μg/kg/min",
            "onset": 5,
            "duration": 30,
            "half_life": 2.5,
            "contraindications": ["严重主动脉瓣/肺动脉瓣狭窄"],
            "monitor": ["血压", "心率", "ECG", "血小板"],
            "color": "#66ccff",
            "formulation": "1mg/mL, 10mg/10mL",
            "preparation": "负荷+维持泵注"
        },
        "加压素": {
            "class": "血管活性",
            "indications": ["心脏骤停", "血管舒张性休克"],
            "route": "IV/IO",
            "dose_adult": "40U IV push (替代肾上腺素)",
            "dose_child": "0.8U/kg IV (max 40U)",
            "max_dose": "40U",
            "onset": 1,
            "duration": 15,
            "half_life": 2,
            "contraindications": ["已知过敏"],
            "monitor": ["血压", "心率", "灌注"],
            "color": "#ff66aa",
            "formulation": "20U/mL, 40U/2mL",
            "preparation": "40U IV push"
        },
        "阿司匹林": {
            "class": "抗凝/溶栓",
            "indications": ["ACS", "胸痛(心肌梗死)", "卒中"],
            "route": "PO/PR",
            "dose_adult": "300-325mg 嚼服/口服",
            "dose_child": "禁用 (Reye综合征风险)",
            "max_dose": "325mg",
            "onset": 15,
            "duration": 240,
            "half_life": 15,
            "contraindications": ["过敏", "活动性出血", "严重肝病"],
            "monitor": ["出血", "血小板"],
            "color": "#ff8844",
            "formulation": "100mg, 300mg, 500mg 片剂",
            "preparation": "300mg 嚼服"
        },
        "替格瑞洛": {
            "class": "抗凝/溶栓",
            "indications": ["ACS", "PCI术后"],
            "route": "PO",
            "dose_adult": "负荷180mg, 维持90mg bid",
            "dose_child": "不推荐",
            "max_dose": "180mg 负荷",
            "onset": 30,
            "duration": 1440,
            "half_life": 7,
            "contraindications": ["活动性出血", "颅内出血史"],
            "monitor": ["出血", "血小板", "肝功"],
            "color": "#ffaa66",
            "formulation": "60mg, 90mg 片剂",
            "preparation": "负荷180mg, 维持90mg bid"
        },
        "氯吡格雷": {
            "class": "抗凝/溶栓",
            "indications": ["ACS", "PCI术后", "卒中预防"],
            "route": "PO",
            "dose_adult": "负荷300-600mg, 维持75mg qd",
            "dose_child": "不推荐",
            "max_dose": "600mg 负荷",
            "onset": 60,
            "duration": 1440,
            "half_life": 8,
            "contraindications": ["活动性出血", "严重肝病"],
            "monitor": ["出血", "血小板"],
            "color": "#ff9966",
            "formulation": "75mg, 300mg 片剂",
            "preparation": "负荷300-600mg, 维持75mg qd"
        },
        "肝素": {
            "class": "抗凝/溶栓",
            "indications": ["ACS", "深静脉血栓", "肺栓塞", "PCI"],
            "route": "IV/SC",
            "dose_adult": "负荷60-80 U/kg, 维持12-18 U/kg/h",
            "dose_child": "负荷50-75 U/kg, 维持15-20 U/kg/h",
            "max_dose": "负荷5000U",
            "onset": 5,
            "duration": 60,
            "half_life": 1.5,
            "contraindications": ["活动性出血", "严重血小板减少"],
            "monitor": ["aPTT", "血小板"],
            "color": "#ff8888",
            "formulation": "1000U/mL, 5000U/mL, 25000U/5mL",
            "preparation": "按体重计算负荷+维持泵注"
        },
        "依诺肝素": {
            "class": "抗凝/溶栓",
            "indications": ["ACS", "深静脉血栓预防/治疗"],
            "route": "SC",
            "dose_adult": "1mg/kg q12h 或 1.5mg/kg qd",
            "dose_child": "1mg/kg q12h",
            "max_dose": "100mg q12h",
            "onset": 30,
            "duration": 720,
            "half_life": 4.5,
            "contraindications": ["活动性出血", "严重血小板减少"],
            "monitor": ["出血", "血小板"],
            "color": "#ff9999",
            "formulation": "40mg/0.4mL, 60mg/0.6mL, 80mg/0.8mL, 100mg/mL",
            "preparation": "SC注射"
        },
        "阿替普酶": {
            "class": "抗凝/溶栓",
            "indications": ["STEMI", "急性缺血性卒中", "大面积肺栓塞"],
            "route": "IV",
            "dose_adult": "STEMI: 15mg负荷 + 0.75mg/kg over 30min + 0.5mg/kg over 60min",
            "dose_child": "不推荐",
            "max_dose": "100mg",
            "onset": 10,
            "duration": 90,
            "half_life": 5,
            "contraindications": ["出血性卒中", "颅内出血史", "严重高血压"],
            "monitor": ["出血", "血压", "ECG"],
            "color": "#ff4466",
            "formulation": "20mg, 50mg 粉针",
            "preparation": "STEMI: 15mg IV push + 50mg over 30min + 35mg over 60min"
        },
        "氯化钾": {
            "class": "电解质/补液",
            "indications": ["低钾血症", "心律失常预防"],
            "route": "IV infusion (中心静脉优先)",
            "dose_adult": "10-20 mEq/h, max 40 mEq/h",
            "dose_child": "0.5-1 mEq/kg/h",
            "max_dose": "40 mEq/h (外周静脉20 mEq/h)",
            "onset": 15,
            "duration": 60,
            "half_life": 30,
            "contraindications": ["高钾血症", "严重肾功能不全"],
            "monitor": ["血钾", "ECG", "尿量"],
            "color": "#cc66ff",
            "formulation": "20 mEq/10mL, 40 mEq/20mL",
            "preparation": "稀释后静脉滴注"
        },
        "氯化钙": {
            "class": "电解质/补液",
            "indications": ["低钙血症", "高钾血症", "钙通道阻滞剂过量"],
            "route": "IV",
            "dose_adult": "1-2g IV",
            "dose_child": "20mg/kg IV (0.2mL/kg)",
            "max_dose": "2g",
            "onset": 2,
            "duration": 30,
            "half_life": 10,
            "contraindications": ["高钙血症", "洋地黄中毒"],
            "monitor": ["血钙", "ECG"],
            "color": "#cc99ff",
            "formulation": "1g/10mL, 2g/20mL",
            "preparation": "缓慢IV推注"
        },
        "碳酸氢钠": {
            "class": "电解质/补液",
            "indications": ["严重酸中毒", "高钾血症", "三环类抗抑郁药过量"],
            "route": "IV",
            "dose_adult": "1 mEq/kg",
            "dose_child": "1 mEq/kg",
            "max_dose": "2 mEq/kg",
            "onset": 5,
            "duration": 30,
            "half_life": 15,
            "contraindications": ["代谢性碱中毒", "低钙血症"],
            "monitor": ["血气", "血钾", "血钙"],
            "color": "#aaffff",
            "formulation": "50 mEq/50mL, 100 mEq/100mL",
            "preparation": "缓慢IV推注"
        },
        "葡萄糖酸钙": {
            "class": "电解质/补液",
            "indications": ["低钙血症", "高钾血症", "镁中毒"],
            "route": "IV",
            "dose_adult": "1-2g IV",
            "dose_child": "100mg/kg IV",
            "max_dose": "2g",
            "onset": 3,
            "duration": 60,
            "half_life": 20,
            "contraindications": ["高钙血症", "洋地黄中毒"],
            "monitor": ["血钙", "ECG"],
            "color": "#aaccff",
            "formulation": "1g/10mL, 2g/20mL",
            "preparation": "缓慢IV推注"
        },
        "咪达唑仑": {
            "class": "镇静/镇痛",
            "indications": ["镇静", "麻醉诱导", "癫痫持续状态"],
            "route": "IV/IM/IN",
            "dose_adult": "1-2mg IV, 0.1-0.2mg/kg IM/IN",
            "dose_child": "0.05-0.15mg/kg IV, 0.2-0.3mg/kg IN",
            "max_dose": "10mg",
            "onset": 2,
            "duration": 60,
            "half_life": 3,
            "contraindications": ["严重呼吸抑制", "重症肌无力"],
            "monitor": ["呼吸", "血压", "心率", "镇静深度"],
            "color": "#ff99cc",
            "formulation": "1mg/mL, 5mg/mL, 10mg/10mL",
            "preparation": "IV: 1-2mg, 可重复; IN: 0.2mg/kg"
        },
        "芬太尼": {
            "class": "镇静/镇痛",
            "indications": ["急性疼痛", "镇静", "麻醉辅助"],
            "route": "IV/IM/IN",
            "dose_adult": "1-2 μg/kg IV",
            "dose_child": "1-2 μg/kg IV",
            "max_dose": "5 μg/kg",
            "onset": 2,
            "duration": 30,
            "half_life": 4,
            "contraindications": ["颅脑损伤", "呼吸抑制"],
            "monitor": ["呼吸", "心率", "镇静深度"],
            "color": "#ff6699",
            "formulation": "50 μg/mL, 100 μg/2mL, 250 μg/5mL",
            "preparation": "IV: 1-2 μg/kg 缓慢推注"
        },
        "吗啡": {
            "class": "镇静/镇痛",
            "indications": ["急性疼痛", "心源性肺水肿", "ACS疼痛"],
            "route": "IV/IM/PO",
            "dose_adult": "2-5mg IV, 可重复",
            "dose_child": "0.1-0.2mg/kg IV",
            "max_dose": "10mg",
            "onset": 3,
            "duration": 120,
            "half_life": 2.5,
            "contraindications": ["颅脑损伤", "呼吸抑制", "胰腺炎"],
            "monitor": ["呼吸", "血压", "镇静深度"],
            "color": "#ff7799",
            "formulation": "2mg/mL, 5mg/mL, 10mg/2mL",
            "preparation": "IV: 2-5mg 缓慢推注"
        },
        "丙泊酚": {
            "class": "镇静/镇痛",
            "indications": ["麻醉诱导", "镇静", "癫痫持续状态"],
            "route": "IV",
            "dose_adult": "1-2.5mg/kg诱导, 25-100 μg/kg/min维持",
            "dose_child": "2-4mg/kg诱导, 50-150 μg/kg/min维持",
            "max_dose": "4mg/kg 诱导",
            "onset": 1,
            "duration": 10,
            "half_life": 2,
            "contraindications": ["过敏(鸡蛋/大豆)", "儿童(<3岁)"],
            "monitor": ["呼吸", "血压", "心率", "BIS"],
            "color": "#ccddff",
            "formulation": "10mg/mL, 20mg/2mL, 50mg/50mL",
            "preparation": "诱导: 1-2.5mg/kg; 维持: 泵注"
        },
        "氯胺酮": {
            "class": "镇静/镇痛",
            "indications": ["快速序贯插管", "镇静", "疼痛", "难治性癫痫"],
            "route": "IV/IM/IN",
            "dose_adult": "1-2mg/kg IV, 4-5mg/kg IM, 9mg/kg IN",
            "dose_child": "1-2mg/kg IV, 4-5mg/kg IM",
            "max_dose": "5mg/kg IV",
            "onset": 1,
            "duration": 15,
            "half_life": 2,
            "contraindications": ["高血压(未控制)", "颅内高压"],
            "monitor": ["血压", "心率", "呼吸", "气道"],
            "color": "#ffaacc",
            "formulation": "10mg/mL, 50mg/mL, 100mg/10mL",
            "preparation": "IV: 1-2mg/kg 缓慢推注"
        },
        "呋塞米": {
            "class": "其他",
            "indications": ["急性心衰", "肺水肿", "高血压危象", "肾衰竭"],
            "route": "IV/PO",
            "dose_adult": "20-40mg IV, 可重复",
            "dose_child": "1mg/kg IV",
            "max_dose": "80mg IV",
            "onset": 5,
            "duration": 120,
            "half_life": 2,
            "contraindications": ["无尿症", "严重电解质紊乱"],
            "monitor": ["尿量", "电解质", "血压", "肌酐"],
            "color": "#ffcc66",
            "formulation": "20mg/2mL, 40mg/4mL, 100mg/10mL",
            "preparation": "20-40mg IV push"
        },
        "硝酸甘油": {
            "class": "其他",
            "indications": ["心绞痛", "急性冠脉综合征", "急性心力衰竭"],
            "route": "SL/IV/Transdermal",
            "dose_adult": "SL: 0.3-0.4mg q5min; IV: 5-200 μg/min",
            "dose_child": "IV: 0.5-5 μg/kg/min",
            "max_dose": "SL: 1.2mg; IV: 200 μg/min",
            "onset": 2,
            "duration": 20,
            "half_life": 3,
            "contraindications": ["低血压", "严重主动脉瓣狭窄", "已用PDE-5抑制剂"],
            "monitor": ["血压", "心率"],
            "color": "#66ffcc",
            "formulation": "0.4mg SL, 5mg/10mL IV, 10mg/50mL",
            "preparation": "SL 0.4mg; IV 5-200 μg/min泵注"
        },
        "硝普钠": {
            "class": "其他",
            "indications": ["高血压危象", "心源性休克", "急性心衰"],
            "route": "IV infusion",
            "dose_adult": "0.25-10 μg/kg/min",
            "dose_child": "0.5-5 μg/kg/min",
            "max_dose": "10 μg/kg/min",
            "onset": 1,
            "duration": 3,
            "half_life": 2,
            "contraindications": ["严重低血压", "颅内高压"],
            "monitor": ["血压", "心率", "硫氰酸浓度"],
            "color": "#66ffaa",
            "formulation": "50mg/2mL, 100mg/5mL",
            "preparation": "持续泵注, 避光"
        },
        "氨茶碱": {
            "class": "其他",
            "indications": ["严重哮喘", "COPD急性加重"],
            "route": "IV",
            "dose_adult": "负荷5-6mg/kg + 维持0.4-0.6mg/kg/h",
            "dose_child": "负荷5-6mg/kg + 维持0.6-0.9mg/kg/h",
            "max_dose": "负荷500mg",
            "onset": 5,
            "duration": 120,
            "half_life": 6,
            "contraindications": ["癫痫", "严重心律失常"],
            "monitor": ["茶碱浓度", "心率", "血压"],
            "color": "#88dd88",
            "formulation": "250mg/10mL, 500mg/20mL",
            "preparation": "负荷+维持泵注"
        },
        "纳洛酮": {
            "class": "其他",
            "indications": ["阿片类药物过量", "呼吸抑制"],
            "route": "IV/IM/IN",
            "dose_adult": "0.4-2mg IV, 可重复",
            "dose_child": "0.1mg/kg IV, 可重复",
            "max_dose": "10mg",
            "onset": 1,
            "duration": 30,
            "half_life": 1,
            "contraindications": ["已知过敏"],
            "monitor": ["呼吸", "意识", "心率"],
            "color": "#66ff88",
            "formulation": "0.4mg/mL, 1mg/mL, 4mg/10mL",
            "preparation": "0.4-2mg IV推注"
        }
    }

class DrugAdminSimulator:
    """药品管理模拟器 - 带PKAST药代动力学模拟 + 药物禁忌拦截"""
    
    def __init__(self, app=None):
        self.app = app
        self.medication_log = []
        self.active_drugs = {}
        self.concentration_history = {}
        self.code_reports = []  # ROSC 抢救复盘
        self._code_medications = []  # 抢救用药清单
    
    def set_app(self, app):
        self.app = app
    
    # ==================== V10.0.0: 药物禁忌拦截 ====================
    def _check_contraindications(self, drug_name):
        """检查药物禁忌 - 保命系统"""
        if self.app is None:
            return None
        
        # 获取当前状态
        ecg_rhythm = getattr(self.app, 'ecg_rhythm', '')
        sys_bp = getattr(self.app, 'sim_sys_bp', 120)
        
        # 硝酸甘油禁忌：STEMI + 低血压 (下壁心梗)
        if drug_name == "硝酸甘油":
            if "STEMI" in ecg_rhythm and sys_bp < 90:
                return {
                    "error": "⚠️ 安全拦截：疑似下壁心梗伴低血压，硝酸甘油禁忌！\n\n"
                             "🚨 禁忌原因：\n"
                             "• 下壁STEMI 合并 低血压（SBP < 90mmHg）\n"
                             "• 硝酸甘油可能导致右心室前负荷下降，加重休克\n\n"
                             "✅ 建议处理：\n"
                             "• 停用硝酸甘油\n"
                             "• 考虑补液或血管活性药物（如多巴胺）\n"
                             "• 评估右心室功能"
                }
        
        # 肾上腺素禁忌：严重高血压
        if drug_name == "肾上腺素" and sys_bp > 180:
            return {
                "error": "⚠️ 安全拦截：严重高血压（SBP > 180mmHg），肾上腺素慎用！\n\n"
                         "🚨 可能增加颅内压和出血风险\n\n"
                         "✅ 建议：考虑其他血管活性药物"
            }
        
        return None
    
    def administer(self, drug_name, dose, route, patient_weight=None):
        # ===== V10.0.0: 药物禁忌拦截 (最高优先级) =====
        contraindication = self._check_contraindications(drug_name)
        if contraindication:
            return contraindication
        
        drug_info = DrugDatabase.DRUGS.get(drug_name)
        if not drug_info:
            return {"error": f"未知药物: {drug_name}"}
        
        actual_dose = dose
        if patient_weight:
            if drug_name == "肾上腺素" and route in ["IV", "IO"]:
                actual_dose = 0.01 * patient_weight
            elif drug_name == "胺碘酮":
                actual_dose = min(300, 5 * patient_weight)
            elif drug_name == "腺苷":
                if patient_weight < 50:
                    actual_dose = 0.1 * patient_weight
            elif drug_name == "阿托品":
                actual_dose = max(0.1, min(0.5, 0.02 * patient_weight))
            elif drug_name == "硫酸镁":
                actual_dose = min(2000, 50 * patient_weight)
        
        onset = drug_info.get("onset", 2)
        duration = drug_info.get("duration", 30)
        half_life = drug_info.get("half_life", 2)
        
        peak_concentration = dose * 10 / (patient_weight or 70)
        effect_strength = min(1.0, peak_concentration / 100)
        
        record = {
            "drug": drug_name,
            "dose": actual_dose,
            "route": route,
            "time": datetime.now().strftime("%H:%M:%S"),
            "onset_min": onset,
            "duration_min": duration,
            "peak_concentration": peak_concentration,
            "effect_strength": effect_strength,
            "half_life": half_life,
            "indications": drug_info.get("indications", [])[:3],
            "monitor": drug_info.get("monitor", [])
        }
        self.medication_log.append(record)
        
        if drug_name not in self.concentration_history:
            self.concentration_history[drug_name] = []
        
        self.active_drugs[drug_name] = {
            "time": datetime.now(),
            "dose": actual_dose,
            "route": route,
            "concentration": peak_concentration,
            "half_life": half_life,
            "duration": duration,
            "drug_info": drug_info
        }
        
        # 记录给药到复盘系统
        if self.app:
            self._code_medications.append({
                "drug": drug_name,
                "dose": actual_dose,
                "route": route,
                "time": datetime.now().strftime("%H:%M:%S")
            })
        
        return record
    
    def get_active_effects(self):
        effects = {}
        for drug, info in self.active_drugs.items():
            elapsed = (datetime.now() - info["time"]).seconds / 60
            if elapsed > info["duration"]:
                continue
            remaining = 1.0 - (elapsed / info["duration"])
            decay = 0.5 ** (elapsed / info["half_life"])
            effect = remaining * decay * 0.8
            effects[drug] = {
                "effect_level": min(1.0, effect),
                "time_elapsed": elapsed,
                "remaining_min": max(0, info["duration"] - elapsed),
                "concentration": info["concentration"] * decay
            }
        return effects
    
    def get_concentration_data(self):
        data = {}
        for drug, info in self.active_drugs.items():
            elapsed = (datetime.now() - info["time"]).seconds / 60
            if elapsed > info["duration"] + 5:
                continue
            decay = 0.5 ** (elapsed / info["half_life"])
            conc = info["concentration"] * decay
            data[drug] = {
                "concentration": conc,
                "elapsed": elapsed,
                "duration": info["duration"],
                "color": info["drug_info"].get("color", "#ffffff"),
                "half_life": info["half_life"]
            }
        return data
    
    def get_interaction_risk(self, drugs):
        interactions = {
            ("胺碘酮", "利多卡因"): "QT延长风险增加",
            ("胺碘酮", "多巴胺"): "心律失常风险增加",
            ("肾上腺素", "多巴胺"): "高血压危象风险",
            ("多巴胺", "去甲肾上腺素"): "协同升压作用",
            ("阿托品", "咪达唑仑"): "镇静作用增强",
            ("芬太尼", "咪达唑仑"): "呼吸抑制协同作用",
            ("硫酸镁", "氯化钙"): "拮抗作用",
            ("硫酸镁", "葡萄糖酸钙"): "拮抗作用",
            ("肝素", "阿司匹林"): "出血风险增加",
            ("肝素", "替格瑞洛"): "出血风险增加",
            ("替格瑞洛", "阿司匹林"): "协同抗血小板",
            ("硝酸甘油", "西地那非"): "严重低血压风险",
            ("肾上腺素", "去甲肾上腺素"): "协同升压",
            ("氯胺酮", "咪达唑仑"): "镇静协同作用",
            ("丙泊酚", "芬太尼"): "呼吸抑制协同"
        }
        risks = []
        for i in range(len(drugs)):
            for j in range(i+1, len(drugs)):
                key = tuple(sorted([drugs[i], drugs[j]]))
                if key in interactions:
                    risks.append(f"{drugs[i]} + {drugs[j]}: {interactions[key]}")
        return risks

class DrugLibraryUI:
    """药品库用户界面"""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.simulator = None
        self.selected_drug = None
        self.window = None
    
    def set_simulator(self, simulator):
        self.simulator = simulator
    
    def open(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        
        self.window = Toplevel(self.parent)
        self.window.title("💊 药品库 - AHA/PALS标准抢救药物")
        self.window.geometry("950x750")
        self.window.configure(bg="#0a1a2a")
        self.window.grab_set()
        
        self.window.update_idletasks()
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        
        win_w = 950
        win_h = 750
        
        x = parent_x + parent_w + 10
        y = parent_y + 20
        
        if x + win_w > screen_w:
            x = parent_x + max(0, (parent_w - win_w) // 2)
            y = parent_y + max(0, (parent_h - win_h) // 2)
        
        x = max(0, min(x, screen_w - win_w))
        y = max(0, min(y, screen_h - win_h))
        
        self.window.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        main_frame = Frame(self.window, bg="#0a1a2a")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        Label(main_frame, text="💊 急救药品库 | AHA/PALS 2020标准", 
              font=("Arial", 18, "bold"), fg=self.app.COLOR_YELLOW, bg="#0a1a2a").pack(pady=5)
        Label(main_frame, text="对标AHA/ALS/PALS指南 · 行业首创PKAST药代动力学模拟", 
              font=("Arial", 10), fg="#88aacc", bg="#0a1a2a").pack(pady=2)
        
        cat_frame = Frame(main_frame, bg="#0a1a2a")
        cat_frame.pack(fill="x", pady=5)
        for cat in DrugDatabase.CATEGORIES.keys():
            btn = Button(cat_frame, text=cat, font=("Arial", 9),
                        bg="#1a3a4a", fg="white", relief="flat",
                        command=lambda c=cat: self._filter_by_category(c))
            btn.pack(side="left", padx=2, pady=2)
        Button(cat_frame, text="全部", font=("Arial", 9, "bold"),
               bg=self.app.COLOR_GREEN, fg="black", relief="flat",
               command=self._show_all_drugs).pack(side="left", padx=2, pady=2)
        
        content_frame = Frame(main_frame, bg="#0a1a2a")
        content_frame.pack(fill="both", expand=True, pady=5)
        
        left_frame = Frame(content_frame, bg="#0a1a2a")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        Label(left_frame, text="📋 药物列表", font=("Arial", 12, "bold"),
              fg=self.app.COLOR_BLUE, bg="#0a1a2a").pack(anchor="w")
        
        list_container = Frame(left_frame, bg="#1a2a3a")
        list_container.pack(fill="both", expand=True)
        
        self.drug_listbox = tk.Listbox(list_container, bg="#1a2a3a", fg="white",
                                       font=("Arial", 11), selectmode="single",
                                       highlightthickness=0, borderwidth=0,
                                       height=25)
        scrollbar = tk.Scrollbar(list_container, orient="vertical", 
                                command=self.drug_listbox.yview)
        self.drug_listbox.configure(yscrollcommand=scrollbar.set)
        self.drug_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.drug_listbox.bind("<<ListboxSelect>>", self._on_drug_select)
        
        right_frame = Frame(content_frame, bg="#0a1a2a", width=420)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        right_frame.pack_propagate(False)
        
        self.detail_frame = Frame(right_frame, bg="#1a2a3a", relief="ridge", bd=2)
        self.detail_frame.pack(fill="both", expand=True)
        
        self._show_all_drugs()
        self._show_empty_detail()
        
        bottom_frame = Frame(main_frame, bg="#0a1a2a")
        bottom_frame.pack(fill="x", pady=5)
        
        self.admin_btn = Button(bottom_frame, text="💉 给药", font=("Arial", 12, "bold"),
                               bg=self.app.COLOR_GREEN, fg="black",
                               command=self._administer_drug, state="disabled")
        self.admin_btn.pack(side="left", padx=5)
        
        Button(bottom_frame, text="📊 活跃药物效果", font=("Arial", 10),
               bg=self.app.COLOR_BLUE, fg="black",
               command=self._show_active_effects).pack(side="left", padx=5)
        
        Button(bottom_frame, text="📝 给药记录", font=("Arial", 10),
               bg=self.app.COLOR_YELLOW, fg="black",
               command=self._show_medication_log).pack(side="left", padx=5)
        
        Button(bottom_frame, text="📈 浓度曲线", font=("Arial", 10),
               bg="#ff66cc", fg="black",
               command=self._show_concentration_curve).pack(side="left", padx=5)
        
        Button(bottom_frame, text="✕ 关闭", font=("Arial", 12),
               bg=self.app.COLOR_RED_ALERT, fg="white",
               command=self._close).pack(side="right", padx=5)
        
        self.window.protocol("WM_DELETE_WINDOW", self._close)
    
    def _show_all_drugs(self):
        self.drug_listbox.delete(0, tk.END)
        for drug in sorted(DrugDatabase.DRUGS.keys()):
            self.drug_listbox.insert(tk.END, drug)
    
    def _filter_by_category(self, category):
        self.drug_listbox.delete(0, tk.END)
        drugs = DrugDatabase.CATEGORIES.get(category, [])
        for drug in sorted(drugs):
            if drug in DrugDatabase.DRUGS:
                self.drug_listbox.insert(tk.END, drug)
    
    def _on_drug_select(self, event):
        selection = self.drug_listbox.curselection()
        if selection:
            self.selected_drug = self.drug_listbox.get(selection[0])
            self._show_drug_detail(self.selected_drug)
            self.admin_btn.config(state="normal")
    
    def _show_empty_detail(self):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        Label(self.detail_frame, text="👈 请从左侧选择药物", 
              font=("Arial", 16), fg="#666", bg="#1a2a3a").pack(expand=True)
    
    def _show_drug_detail(self, drug_name):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        
        drug_info = DrugDatabase.DRUGS.get(drug_name)
        if not drug_info:
            return
        
        Label(self.detail_frame, text=f"💊 {drug_name}", 
              font=("Arial", 18, "bold"), fg=self.app.COLOR_YELLOW, bg="#1a2a3a").pack(anchor="w", padx=10, pady=5)
        
        color = drug_info.get("color", "#888")
        Label(self.detail_frame, text=f"分类: {drug_info.get('class', 'N/A')}", 
              font=("Arial", 11), fg=color, bg="#1a2a3a").pack(anchor="w", padx=10)
        
        Label(self.detail_frame, text="适应症:", font=("Arial", 11, "bold"),
              fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
        for idx in drug_info.get("indications", []):
            Label(self.detail_frame, text=f"  • {idx}", 
                  font=("Arial", 10), fg="#aaccff", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        Label(self.detail_frame, text="剂量方案:", font=("Arial", 11, "bold"),
              fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
        Label(self.detail_frame, text=f"成人: {drug_info.get('dose_adult', 'N/A')}", 
              font=("Arial", 10), fg="#88ff88", bg="#1a2a3a").pack(anchor="w", padx=20)
        Label(self.detail_frame, text=f"儿童: {drug_info.get('dose_child', 'N/A')}", 
              font=("Arial", 10), fg="#88ddff", bg="#1a2a3a").pack(anchor="w", padx=20)
        Label(self.detail_frame, text=f"最大剂量: {drug_info.get('max_dose', 'N/A')}", 
              font=("Arial", 10), fg="#ff8888", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        Label(self.detail_frame, text="药代动力学 (PKAST):", font=("Arial", 11, "bold"),
              fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
        pkinfo = f"起效: {drug_info.get('onset', 'N/A')}min | 持续: {drug_info.get('duration', 'N/A')}min | 半衰期: {drug_info.get('half_life', 'N/A')}min"
        Label(self.detail_frame, text=pkinfo, 
              font=("Arial", 10), fg="#ffcc66", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        if drug_info.get("contraindications"):
            Label(self.detail_frame, text="禁忌症:", font=("Arial", 11, "bold"),
                  fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
            for idx in drug_info.get("contraindications", []):
                Label(self.detail_frame, text=f"  ⚠ {idx}", 
                      font=("Arial", 10), fg="#ff6666", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        if drug_info.get("monitor"):
            Label(self.detail_frame, text="监测指标:", font=("Arial", 11, "bold"),
                  fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
            for idx in drug_info.get("monitor", []):
                Label(self.detail_frame, text=f"  📊 {idx}", 
                      font=("Arial", 10), fg="#66ccff", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        Label(self.detail_frame, text="制剂:", font=("Arial", 11, "bold"),
              fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
        Label(self.detail_frame, text=f"{drug_info.get('formulation', 'N/A')}", 
              font=("Arial", 10), fg="#cccccc", bg="#1a2a3a").pack(anchor="w", padx=20)
        
        Label(self.detail_frame, text="制备:", font=("Arial", 11, "bold"),
              fg="white", bg="#1a2a3a").pack(anchor="w", padx=10, pady=(10, 2))
        Label(self.detail_frame, text=f"{drug_info.get('preparation', 'N/A')}", 
              font=("Arial", 10), fg="#cccccc", bg="#1a2a3a").pack(anchor="w", padx=20)
    
    def _administer_drug(self):
        if not self.selected_drug:
            return
        
        if self.simulator is None:
            messagebox.showerror("错误", "模拟器未初始化")
            return
        
        patient_type = messagebox.askquestion("患者类型", "是否为儿童患者？\n(选择'是'将使用儿童剂量)")
        
        weight_str = simpledialog.askstring("患者体重", 
                                            "请输入患者体重 (kg):\n(用于儿童剂量计算和药代动力学模拟)")
        
        weight = None
        if weight_str:
            try:
                weight = float(weight_str)
                if weight < 1:
                    weight = 1
                elif weight > 300:
                    weight = 300
            except:
                weight = 70
        
        route = simpledialog.askstring("给药途径", 
                                       "请输入给药途径 (IV/IO/IM/IN/PO/SL):",
                                       initialvalue="IV")
        if not route:
            route = "IV"
        route = route.upper()
        if route not in ["IV", "IO", "IM", "IN", "PO", "SL", "PR"]:
            route = "IV"
        
        drug_info = DrugDatabase.DRUGS.get(self.selected_drug)
        if not drug_info:
            return
        
        if patient_type == "yes" and weight:
            if self.selected_drug == "肾上腺素" and route in ["IV", "IO"]:
                suggested_dose = 0.01 * weight
            elif self.selected_drug == "胺碘酮" and route in ["IV", "IO"]:
                suggested_dose = min(300, 5 * weight)
            else:
                suggested_dose = 1
        else:
            try:
                import re
                dose_str = drug_info.get("dose_adult", "N/A")
                numbers = re.findall(r'(\d+\.?\d*)', dose_str)
                suggested_dose = float(numbers[0]) if numbers else 1
            except:
                suggested_dose = 1
        
        dose_input = simpledialog.askstring("给药剂量", 
                                            f"请输入 {self.selected_drug} 的剂量:\n"
                                            f"建议: {suggested_dose}\n"
                                            f"参考: {drug_info.get('dose_adult', 'N/A')}")
        
        try:
            dose = float(dose_input) if dose_input else suggested_dose
        except:
            dose = suggested_dose
        
        result = self.simulator.administer(self.selected_drug, dose, route, weight)
        
        if "error" in result:
            messagebox.showerror("🚨 给药被拦截", result["error"])
            return
        
        msg = f"✅ 给药成功!\n\n"
        msg += f"💊 药物: {result['drug']}\n"
        msg += f"💉 剂量: {result['dose']}\n"
        msg += f"📌 途径: {result['route']}\n"
        msg += f"⏱ 起效时间: {result['onset_min']} 分钟\n"
        msg += f"⏳ 持续时间: {result['duration_min']} 分钟\n"
        msg += f"📊 峰值浓度: {result['peak_concentration']:.2f} (相对单位)\n"
        msg += f"💪 效应强度: {int(result['effect_strength'] * 100)}%\n\n"
        
        if result.get('monitor'):
            msg += "📋 监测指标:\n"
            for m in result['monitor']:
                msg += f"  • {m}\n"
        
        messagebox.showinfo("💉 给药记录", msg)
        
        active_drugs = list(self.simulator.active_drugs.keys())
        if len(active_drugs) > 1:
            risks = self.simulator.get_interaction_risk(active_drugs)
            if risks:
                risk_msg = "⚠️ 药物相互作用警告:\n\n"
                for r in risks:
                    risk_msg += f"• {r}\n"
                messagebox.showwarning("药物相互作用", risk_msg)
        
        self.app.event_logger.log_event("药物", f"给药: {self.selected_drug} {dose}{'mg' if route in ['IV','IO','IM','IN'] else ''} {route}", 
                                       {"drug": self.selected_drug, "dose": dose, "route": route, "weight": weight})
        self.app.update_drug_curve_data(self.simulator.get_concentration_data())
    
    def _show_active_effects(self):
        if self.simulator is None:
            return
        effects = self.simulator.get_active_effects()
        if not effects:
            messagebox.showinfo("活跃药物", "当前无活跃药物效应")
            return
        
        msg = "📊 当前活跃药物效应 (PKAST模拟):\n\n"
        for drug, info in effects.items():
            msg += f"💊 {drug}:\n"
            msg += f"  • 效应强度: {int(info['effect_level'] * 100)}%\n"
            msg += f"  • 已过时间: {info['time_elapsed']:.1f} 分钟\n"
            msg += f"  • 剩余时间: {info['remaining_min']:.1f} 分钟\n"
            msg += f"  • 当前浓度: {info['concentration']:.2f}\n\n"
        
        total_effect = sum([info['effect_level'] for info in effects.values()])
        msg += f"📈 总联合效应: {int(total_effect * 100)}%\n"
        msg += f"⚠️ 监测建议: 密切观察生命体征"
        
        messagebox.showinfo("活跃药物效应", msg)
    
    def _show_medication_log(self):
        if self.simulator is None:
            return
        log = self.simulator.medication_log
        if not log:
            messagebox.showinfo("给药记录", "暂无给药记录")
            return
        
        msg = "📝 给药记录:\n\n"
        for record in reversed(log[-20:]):
            msg += f"⏱ {record['time']} | {record['drug']}\n"
            msg += f"  💉 {record['dose']} | {record['route']}\n"
            msg += f"  💪 效应: {int(record['effect_strength'] * 100)}% | "
            msg += f"⏱ {record['onset_min']}min起效 | {record['duration_min']}min持续\n\n"
        
        messagebox.showinfo("给药记录", msg)
    
    def _show_concentration_curve(self):
        if self.simulator is None:
            return
        data = self.simulator.get_concentration_data()
        if not data:
            messagebox.showinfo("浓度曲线", "暂无药物浓度数据")
            return
        
        curve_win = Toplevel(self.window)
        curve_win.title("📈 血浆浓度-时间曲线图 (PKAST模拟)")
        curve_win.geometry("700x500")
        curve_win.configure(bg="#0a1a2a")
        curve_win.grab_set()
        
        parent_x = self.window.winfo_x()
        parent_y = self.window.winfo_y()
        parent_w = self.window.winfo_width()
        parent_h = self.window.winfo_height()
        screen_w = curve_win.winfo_screenwidth()
        screen_h = curve_win.winfo_screenheight()
        
        win_w, win_h = 700, 500
        x = parent_x + (parent_w - win_w) // 2
        y = parent_y + (parent_h - win_h) // 2
        x = max(0, min(x, screen_w - win_w))
        y = max(0, min(y, screen_h - win_h))
        curve_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        canvas = Canvas(curve_win, bg="#0a1a2a", highlightthickness=1, highlightbackground="#444")
        canvas.pack(fill="both", expand=True, padx=20, pady=20)
        
        margin = 60
        curve_win.update_idletasks()
        plot_w = canvas.winfo_width() - 2 * margin - 40
        plot_h = canvas.winfo_height() - 2 * margin - 40
        
        if plot_w < 100:
            plot_w = 500
        if plot_h < 100:
            plot_h = 350
        
        canvas.create_line(margin, margin, margin, margin + plot_h, fill="white", width=2)
        canvas.create_line(margin, margin + plot_h, margin + plot_w, margin + plot_h, fill="white", width=2)
        
        canvas.create_text(margin + plot_w // 2, margin + plot_h + 30, 
                          text="时间 (分钟)", fill="#aaa", font=("Arial", 12))
        canvas.create_text(margin - 40, margin + plot_h // 2, 
                          text="浓度", fill="#aaa", font=("Arial", 12), angle=90)
        
        max_conc = max([d["concentration"] for d in data.values()]) if data else 1
        max_conc = max(max_conc, 0.1)
        max_time = max([d["elapsed"] + d["duration"] for d in data.values()]) if data else 10
        max_time = max(max_time, 5)
        
        for i in range(6):
            y_pos = margin + plot_h - (i / 5) * plot_h
            canvas.create_line(margin, y_pos, margin + plot_w, y_pos, fill="#1a2a3a", width=1)
            canvas.create_text(margin - 10, y_pos, text=f"{i/5 * max_conc:.1f}", fill="#666", font=("Arial", 8))
        
        for i in range(6):
            x_pos = margin + (i / 5) * plot_w
            canvas.create_line(x_pos, margin, x_pos, margin + plot_h, fill="#1a2a3a", width=1)
            canvas.create_text(x_pos, margin + plot_h + 15, text=f"{i/5 * max_time:.1f}", fill="#666", font=("Arial", 8))
        
        for drug, info in data.items():
            color = info.get("color", "#ffffff")
            half_life = info.get("half_life", 2)
            duration = info.get("duration", 30)
            elapsed = info.get("elapsed", 0)
            current_conc = info.get("concentration", 0)
            
            points = []
            num_points = 50
            for i in range(num_points + 1):
                t = (i / num_points) * (duration + 2)
                if t <= duration:
                    if t < 0.5:
                        conc = current_conc * (t / 0.5) * 1.2
                    else:
                        conc = current_conc * (0.5 ** ((t - 0.5) / half_life))
                else:
                    conc = current_conc * (0.5 ** ((duration - 0.5 + (t - duration)) / half_life)) * 0.3
                
                x = margin + (t / max_time) * plot_w
                y = margin + plot_h - (conc / max_conc) * plot_h
                points.append((x, y))
            
            if len(points) > 1:
                canvas.create_line(points, fill=color, width=2.5, smooth=True)
            
            label_x = margin + (elapsed / max_time) * plot_w
            label_y = margin + plot_h - (current_conc / max_conc) * plot_h
            label_y = max(margin + 10, min(margin + plot_h - 10, label_y))
            canvas.create_text(label_x + 10, label_y - 10, text=drug, fill=color, 
                              font=("Arial", 10, "bold"), anchor="w")
            
            if current_conc > 0.01:
                canvas.create_text(margin + plot_w - 10, margin + plot_h - 20 - len(points) * 2,
                                  text=f"{drug}: {current_conc:.2f}", fill=color, 
                                  font=("Arial", 9), anchor="e")
        
        legend_y = margin + 10
        for drug, info in data.items():
            color = info.get("color", "#ffffff")
            canvas.create_rectangle(margin + plot_w - 120, legend_y - 8,
                                   margin + plot_w - 100, legend_y + 8, fill=color)
            canvas.create_text(margin + plot_w - 95, legend_y, text=drug, 
                              fill=color, font=("Arial", 9), anchor="w")
            legend_y += 18
        
        canvas.create_text(margin + plot_w // 2, margin - 30,
                          text="💊 血浆浓度-时间曲线图", fill=self.app.COLOR_YELLOW,
                          font=("Arial", 14, "bold"))
        
        Button(curve_win, text="关闭", font=("Arial", 12),
               bg=self.app.COLOR_RED_ALERT, fg="white",
               command=curve_win.destroy).pack(pady=10)
        
        self.app.event_logger.log_event("操作", "查看浓度曲线图")
    
    def _close(self):
        if self.window:
            self.window.destroy()
            self.window = None

# ==================== V10.0.0: ECG Lab 集成 (TK版本) ====================

class ECG_Canvas_Channel(tk.Canvas):
    """单个ECG波形绘制通道 - TK版本"""
    def __init__(self, parent, channel_idx=0, width=300, height=120, **kwargs):
        super().__init__(parent, width=width, height=height, bg="#0A1A30", highlightthickness=1, highlightbackground="#1A3352", **kwargs)
        self.channel_idx = channel_idx
        self.data_x = []
        self.data_y = []
        self.scroll_offset = 0
        self.pixel_step = 3
        self.buffer_size = 600
        
        # 颜色方案
        self.colors = ["#00FF88", "#FF6B6B", "#4ECDC4", "#FFD93D"]
        self.color = self.colors[channel_idx % len(self.colors)]
        
        self.label_text = f"CH{channel_idx+1}"
        self.info_text = ""
        
        # 绑定尺寸变化
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event):
        self.draw()
    
    def set_label(self, text):
        self.label_text = text
    
    def set_info(self, text):
        self.info_text = text
    
    def set_color(self, color):
        self.color = color
    
    def add_point(self, y_val):
        self.scroll_offset += self.pixel_step
        self.data_x.append(self.scroll_offset)
        self.data_y.append(y_val)
        
        if len(self.data_x) > self.buffer_size:
            self.data_x = self.data_x[-self.buffer_size:]
            self.data_y = self.data_y[-self.buffer_size:]
        
        self.draw()
    
    def clear(self):
        self.data_x = []
        self.data_y = []
        self.scroll_offset = 0
        self.draw()

    def draw(self):
        self.delete("waveform")
        self.delete("labels")
        
        w = self.winfo_width() or 300
        h = self.winfo_height() or 120
        mid_y = h // 2
        
        # 网格
        for i in range(1, 5):
            y = h * i // 5
            self.create_line(0, y, w, y, fill="#1A3352", width=0.5, tags="grid")
        self.create_line(0, mid_y, w, mid_y, fill="#334155", width=1, tags="grid")
        
        # 波形
        if len(self.data_x) < 2:
            # 显示标签
            self.create_text(8, 14, text=self.label_text, fill="#E7ECEF", 
                           font=("Arial", 9), anchor="nw", tags="labels")
            if self.info_text:
                self.create_text(8, h-8, text=self.info_text, fill="#8B939C",
                               font=("Arial", 8), anchor="sw", tags="labels")
            return
        
        n = len(self.data_x)
        x_min = self.data_x[0]
        x_max = self.data_x[-1]
        if x_max <= x_min:
            return
        
        amp = h * 0.35
        points = []
        for i in range(n):
            px = int((self.data_x[i] - x_min) / (x_max - x_min) * w)
            py = int(mid_y - self.data_y[i] * amp)
            py = max(5, min(h-5, py))
            points.append((px, py))
        
        if len(points) > 1:
            self.create_line(points, fill=self.color, width=1.5, smooth=True, tags="waveform")
        
        # 标签
        self.create_text(8, 14, text=self.label_text, fill="#E7ECEF", 
                       font=("Arial", 9), anchor="nw", tags="labels")
        if self.info_text:
            self.create_text(8, h-8, text=self.info_text, fill="#8B939C",
                           font=("Arial", 8), anchor="sw", tags="labels")

class ECG_Lab_TK(Toplevel):
    """ECG Lab - 独立波形对比工作台 (TK版本)"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.parent = parent
        self.app = app
        self.title("ECG Lab — 波形对比工作台 v1.0.0")
        self.geometry("900x650")
        self.configure(bg="#0A1628")
        self.grab_set()
        
        # 内部状态
        self.num_channels = 2
        self.display_mode = "parallel"  # parallel | overlay
        self.playing = False
        self.speed = 1.0
        self.engines = []
        self.canvases = []
        self.overlay_canvases = []
        
        # 定时器
        self.timer_id = None
        
        self._build_ui()
        self._init_channels(2)
        
        self.protocol("WM_DELETE_WINDOW", self._close)
    
    def _build_ui(self):
        main_frame = Frame(self, bg="#0A1628")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 标题
        title_frame = Frame(main_frame, bg="#0F2440")
        title_frame.pack(fill="x", pady=(0, 10))
        Label(title_frame, text="🧬 ECG Lab — 波形对比工作台", 
              font=("Arial", 16, "bold"), fg="#00FF88", bg="#0F2440").pack(side="left", padx=10, pady=8)
        Label(title_frame, text="同步滚动 · 波形鉴别训练", 
              font=("Arial", 10), fg="#8B939C", bg="#0F2440").pack(side="left", padx=10)
        
        # 控制栏
        control_frame = Frame(main_frame, bg="#0F2440")
        control_frame.pack(fill="x", pady=5)
        
        self.btn_play = Button(control_frame, text="▶ 播放", font=("Arial", 11, "bold"),
                              bg="#0466C8", fg="white", command=self._toggle_play)
        self.btn_play.pack(side="left", padx=5)
        
        Button(control_frame, text="↺ 重置", font=("Arial", 11),
               bg="#334155", fg="white", command=self._reset).pack(side="left", padx=5)
        
        Label(control_frame, text="速度:", fg="#E7ECEF", bg="#0F2440").pack(side="left", padx=(15, 5))
        self.speed_combo = ttk.Combobox(control_frame, values=["0.5×", "1×", "2×"], width=5)
        self.speed_combo.current(1)
        self.speed_combo.bind("<<ComboboxSelected>>", self._on_speed_change)
        self.speed_combo.pack(side="left", padx=5)
        
        Label(control_frame, text="模式:", fg="#E7ECEF", bg="#0F2440").pack(side="left", padx=(15, 5))
        self.mode_combo = ttk.Combobox(control_frame, values=["并列", "重叠"], width=6)
        self.mode_combo.current(0)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        self.mode_combo.pack(side="left", padx=5)
        
        Label(control_frame, text="通道:", fg="#E7ECEF", bg="#0F2440").pack(side="left", padx=(15, 5))
        self.ch_combo = ttk.Combobox(control_frame, values=["2", "3", "4"], width=4)
        self.ch_combo.current(0)
        self.ch_combo.bind("<<ComboboxSelected>>", self._on_channel_change)
        self.ch_combo.pack(side="left", padx=5)
        
        Button(control_frame, text="📷 截图", font=("Arial", 10),
               bg="#6BCF7F", fg="#0A1628", command=self._export_png).pack(side="right", padx=5)
        
        # 波形显示区域
        self.display_frame = Frame(main_frame, bg="#0A1628")
        self.display_frame.pack(fill="both", expand=True, pady=5)
        
        # 波形选择面板 (底部)
        selector_frame = Frame(main_frame, bg="#0F2440")
        selector_frame.pack(fill="x", pady=5)
        
        self.rhythm_selectors = []
        self.info_labels = []
        for i in range(4):
            group = Frame(selector_frame, bg="#0F2440", relief="ridge", bd=1)
            group.pack(side="left", padx=5, pady=5, fill="x", expand=True)
            
            Label(group, text=f"通道 {i+1}", fg="#E7ECEF", bg="#0F2440",
                  font=("Arial", 9, "bold")).pack(anchor="w", padx=5)
            
            combo = ttk.Combobox(group, state="readonly", width=18)
            combo.pack(padx=5, pady=2, fill="x")
            # 填充波形选项
            rhythms = ECGGene_Lab.get_rhythm_list()
            values_list = []
            for key in rhythms:
                info = ECGGene_Lab.get_rhythm_info(key)
                values_list.append(f"{info['name']} [{info['default_hr']}bpm]")
            combo["values"] = tuple(values_list)
            combo.current(0)
            combo.bind("<<ComboboxSelected>>", lambda e, idx=i: self._on_rhythm_change(idx))
            
            info_label = Label(group, text="HR: — | QRS: —", fg="#8B939C", 
                             bg="#0F2440", font=("Arial", 8))
            info_label.pack(anchor="w", padx=5, pady=2)
            
            self.rhythm_selectors.append(combo)
            self.info_labels.append(info_label)
            
            if i >= 2:
                group.pack_forget()
        
        # 状态栏
        self.status_label = Label(main_frame, text="就绪 — 选择波形并点击 ▶ 播放", 
                                 fg="#8B939C", bg="#0A1628", font=("Arial", 9))
        self.status_label.pack(fill="x", pady=2)
    
    def _get_rhythm_key(self, combo_idx):
        """从组合框获取波形键值"""
        combo = self.rhythm_selectors[combo_idx]
        text = combo.get()
        # 从显示文本中提取键值
        rhythm_map = {
            "窦性心律": "normal",
            "窦性心动过缓": "sinus_brady",
            "窦性心动过速": "sinus_tachy",
            "房颤": "af",
            "室颤": "vf",
            "室速": "vt",
            "室上速": "svt",
            "单形性室速": "mpvt",
            "多形性室速": "spvt",
            "尖端扭转型": "tdp",
            "心肌梗死": "stem",
            "心肌缺血": "ischemia",
            "心碎综合征": "takotsubo",
            "交界性逸搏心律": "junctional",
            "停搏": "asystole"
        }
        for display, key in rhythm_map.items():
            if display in text:
                return key
        return "normal"
    
    def _init_channels(self, n):
        """初始化 n 个通道"""
        self.num_channels = n
        
        # 清除旧画布
        for c in self.canvases:
            c.destroy()
        self.canvases.clear()
        self.engines.clear()
        self.overlay_canvases.clear()
        
        # 清除显示区域
        for widget in self.display_frame.winfo_children():
            widget.destroy()
        
        if self.display_mode == "parallel":
            # 并列模式
            for i in range(n):
                key = self._get_rhythm_key(i)
                info = ECGGene_Lab.get_rhythm_info(key)
                engine = ECGGene_Lab(hr=info["default_hr"], rhythm=key)
                self.engines.append(engine)
                
                canvas = ECG_Canvas_Channel(self.display_frame, channel_idx=i)
                canvas.set_label(f"CH{i+1}: {info['name']}")
                canvas.set_info(f"HR: {info['default_hr']} bpm  |  QRS: {info['qrs_width']}")
                canvas.pack(fill="both", expand=True, pady=1)
                self.canvases.append(canvas)
        else:
            # 重叠模式 - 只支持2通道
            for i in range(min(2, n)):
                key = self._get_rhythm_key(i)
                info = ECGGene_Lab.get_rhythm_info(key)
                engine = ECGGene_Lab(hr=info["default_hr"], rhythm=key)
                self.engines.append(engine)
                
                canvas = ECG_Canvas_Channel(self.display_frame, channel_idx=i)
                canvas.set_label(f"CH{i+1}: {info['name']}")
                canvas.set_info(f"HR: {info['default_hr']} bpm")
                # 重叠模式下使用半透明叠加
                if i == 1:
                    canvas.set_color("#FF6B6B")
                canvas.pack(fill="both", expand=True, pady=1)
                self.canvases.append(canvas)
                self.overlay_canvases.append(canvas)
        
        # 更新选择器可见性
        for i in range(4):
            group = self.rhythm_selectors[i].master
            if i < n:
                group.pack(side="left", padx=5, pady=5, fill="x", expand=True)
            else:
                group.pack_forget()
        
        # 更新信息标签
        for i in range(n):
            self._update_info_label(i)
    
    def _on_rhythm_change(self, channel):
        key = self._get_rhythm_key(channel)
        info = ECGGene_Lab.get_rhythm_info(key)
        if channel < len(self.engines):
            self.engines[channel].set_rhythm(key)
            self.engines[channel].set_hr(info["default_hr"])
            self._update_info_label(channel)
            if channel < len(self.canvases):
                self.canvases[channel].set_label(f"CH{channel+1}: {info['name']}")
                self.canvases[channel].set_info(
                    f"HR: {info['default_hr']} bpm  |  QRS: {info['qrs_width']}")
                self.canvases[channel].clear()
    
    def _update_info_label(self, channel):
        if channel < len(self.info_labels) and channel < len(self.engines):
            key = self._get_rhythm_key(channel)
            info = ECGGene_Lab.get_rhythm_info(key)
            self.info_labels[channel].config(
                text=f"HR: {info['default_hr']} bpm  |  QRS: {info['qrs_width']}  |  {info['desc']}")
    
    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self.btn_play.config(text="⏸ 暂停", bg="#FF6B6B")
            self._tick_loop()
        else:
            self.btn_play.config(text="▶ 播放", bg="#0466C8")
            if self.timer_id:
                self.after_cancel(self.timer_id)
                self.timer_id = None
    
    def _tick_loop(self):
        if not self.playing:
            return
        
        # 取点
        points_per_tick = max(1, int(self.speed))
        for _ in range(points_per_tick):
            for i, engine in enumerate(self.engines):
                if i < len(self.canvases):
                    val = engine.next()
                    self.canvases[i].add_point(val)
        
        self.timer_id = self.after(int(40 / self.speed), self._tick_loop)
    
    def _reset(self):
        was_playing = self.playing
        if self.playing:
            self._toggle_play()
        
        for i, engine in enumerate(self.engines):
            key = self._get_rhythm_key(i)
            info = ECGGene_Lab.get_rhythm_info(key)
            engine.t = 0.0
            engine.set_rhythm(key)
            engine.set_hr(info["default_hr"])
            if i < len(self.canvases):
                self.canvases[i].clear()
        
        if was_playing:
            self._toggle_play()
    
    def _on_speed_change(self, event):
        speeds = [0.5, 1.0, 2.0]
        self.speed = speeds[self.speed_combo.current()]
        if self.playing:
            if self.timer_id:
                self.after_cancel(self.timer_id)
                self.timer_id = None
            self._tick_loop()
    
    def _on_mode_change(self, event):
        mode = "parallel" if self.mode_combo.current() == 0 else "overlay"
        self.display_mode = mode
        if mode == "overlay" and self.num_channels > 2:
            self.ch_combo.current(0)
            self._init_channels(2)
        else:
            self._init_channels(self.num_channels)
    
    def _on_channel_change(self, event):
        n = self.ch_combo.current() + 2
        if n != self.num_channels:
            self._init_channels(n)
    
    def _export_png(self):
        try:
            from PIL import ImageGrab
            import tkinter as tk
            # 获取显示区域截图
            x = self.display_frame.winfo_rootx()
            y = self.display_frame.winfo_rooty()
            w = self.display_frame.winfo_width()
            h = self.display_frame.winfo_height()
            if w > 0 and h > 0:
                img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
                filename = f"ECG_Lab_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                img.save(filename)
                self.status_label.config(text=f"✅ 已导出: {filename}")
            else:
                self.status_label.config(text="⚠️ 无法截图，请展开窗口")
        except Exception as e:
            self.status_label.config(text=f"⚠️ 截图失败: {e}")
    
    def _close(self):
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None
        self.destroy()

# ==================== ECG Lab 引擎 (独立版本) ====================

class ECGGene_Lab:
    """ECG 波形生成引擎 - 用于ECG Lab"""
    
    RHYTHM_META = {
        "normal":           {"name": "窦性心律",         "category": "正常",   "default_hr": 72,  "qrs_width": "窄(80ms)", "desc": "正常窦性心律，P-QRS-T 完整"},
        "sinus_brady":      {"name": "窦性心动过缓",      "category": "正常",   "default_hr": 45,  "qrs_width": "窄(80ms)", "desc": "心率 < 60 bpm，波形正常"},
        "sinus_tachy":      {"name": "窦性心动过速",      "category": "正常",   "default_hr": 130, "qrs_width": "窄(80ms)", "desc": "心率 > 100 bpm，波形正常"},
        "af":               {"name": "房颤(AF)",         "category": "心律失常", "default_hr": 120, "qrs_width": "窄(80ms)", "desc": "P波消失，RR间期绝对不等"},
        "vf":               {"name": "室颤(VF)",         "category": "致命心律失常", "default_hr": 230, "qrs_width": "无",     "desc": "无组织电活动，不规则颤动波"},
        "vt":               {"name": "室速(VT)",         "category": "心律失常", "default_hr": 180, "qrs_width": "宽(160ms)", "desc": "宽QRS心动过速，房室分离"},
        "svt":              {"name": "室上速(SVT)",       "category": "心律失常", "default_hr": 180, "qrs_width": "窄(80ms)", "desc": "窄QRS心动过速，突发突止"},
        "mpvt":             {"name": "单形性室速(MPVT)",    "category": "心律失常", "default_hr": 170, "qrs_width": "宽(160ms)", "desc": "QRS形态固定一致，宽大畸形"},
        "spvt":             {"name": "多形性室速(SPVT)",    "category": "致命心律失常", "default_hr": 200, "qrs_width": "宽(变化)", "desc": "QRS形态逐搏变化，多种形态交替"},
        "tdp":              {"name": "尖端扭转型(TdP)",     "category": "致命心律失常", "default_hr": 220, "qrs_width": "宽(变化)", "desc": "QRS波峰围绕基线扭转，振幅正弦变化"},
        "stem":             {"name": "心肌梗死(STEMI)",    "category": "缺血",   "default_hr": 85,  "qrs_width": "窄(80ms)", "desc": "ST段弓背向上抬高 > 0.2mV"},
        "ischemia":         {"name": "心肌缺血",          "category": "缺血",   "default_hr": 80,  "qrs_width": "窄(80ms)", "desc": "ST段水平或下斜型压低"},
        "takotsubo":        {"name": "心碎综合征(Takotsubo)", "category": "心肌病", "default_hr": 90, "qrs_width": "窄(80ms)", "desc": "深倒置T波，ST段抬高，QT延长"},
        "junctional":       {"name": "交界性逸搏心律",      "category": "心律失常", "default_hr": 50,  "qrs_width": "窄(80ms)", "desc": "逆行P波，窄QRS波"},
        "asystole":         {"name": "停搏(Asystole)",    "category": "致命心律失常", "default_hr": 0, "qrs_width": "无",     "desc": "无心电活动，等电位线"},
    }
    
    def __init__(self, hr=72, rhythm="normal"):
        self.hr = hr
        self.t = 0.0
        self.dt = 0.04
        self.rhythm = rhythm
        self.r_peak_detected = False
        self.r_peak_timer = 0
        self._tdp_amp = 1.0
        self._spvt_count = 0
    
    def set_rhythm(self, rhythm):
        self.rhythm = rhythm
        self.t = 0.0
        self._tdp_amp = 1.0
        self._spvt_count = 0
    
    def set_hr(self, hr):
        self.hr = max(0, min(600, hr))
    
    def next(self):
        if self.hr == 0:
            return random.gauss(0, 0.01)
        
        self.t += self.dt
        period = 60.0 / self.hr if self.hr > 0 else 1.0
        phase = self.t % period
        val = 0.0
        
        # 窦性 / 正常波形
        if self.rhythm in ("normal", "sinus_brady", "sinus_tachy"):
            if phase < 0.12:
                val = 0.25 * math.sin(math.pi * phase / 0.12)
            elif phase < 0.20:
                t_qrs = phase - 0.12
                if t_qrs < 0.04:
                    val = -1.0 * (t_qrs / 0.04)
                elif t_qrs < 0.08:
                    val = -1.0 + 3.0 * ((t_qrs - 0.04) / 0.04)
                elif t_qrs < 0.12:
                    val = 2.0 - 3.0 * ((t_qrs - 0.08) / 0.04)
                else:
                    val = -1.0 * (1 - (t_qrs - 0.12) / 0.08)
            elif phase < 0.40:
                val = 0.3 * math.sin(math.pi * (phase - 0.20) / 0.20)
            self.r_peak_detected = (0.12 < phase < 0.20)
        
        # 室颤 VF (V11.31: 完全杂乱无规律)
        elif self.rhythm == "vf":
            f1 = 4 + 8 * random.random()
            f2 = 8 + 15 * random.random()
            f3 = 15 + 20 * random.random()
            amp_mod = 0.3 + 0.7 * abs(math.sin(0.7 * self.t + random.random()))
            val = amp_mod * (
                0.5 * math.sin(2 * math.pi * f1 * self.t) +
                0.35 * math.sin(2 * math.pi * f2 * self.t + random.random() * math.pi) +
                0.15 * math.sin(2 * math.pi * f3 * self.t + random.random() * 2 * math.pi)
            )
            val += random.gauss(0, 0.08)
            val = max(-1.0, min(1.0, val))
            self.r_peak_detected = False
        
        # 房颤 AF
        elif self.rhythm == "af":
            if phase < 0.08:
                val = 0.6 * math.sin(math.pi * phase / 0.08)
            elif phase < 0.16:
                t_qrs = phase - 0.08
                if t_qrs < 0.03:
                    val = -0.5 * (t_qrs / 0.03)
                elif t_qrs < 0.06:
                    val = -0.5 + 1.5 * ((t_qrs - 0.03) / 0.03)
                else:
                    val = 1.0 - 1.5 * ((t_qrs - 0.06) / 0.03)
            self.r_peak_detected = (0.08 < phase < 0.16)
        
        # 心肌缺血/梗死
        elif self.rhythm in ("stem", "ischemia"):
            if phase < 0.12:
                val = 0.25 * math.sin(math.pi * phase / 0.12)
            elif phase < 0.20:
                t_qrs = phase - 0.12
                if t_qrs < 0.04:
                    val = -1.0 * (t_qrs / 0.04)
                elif t_qrs < 0.08:
                    val = -1.0 + 3.0 * ((t_qrs - 0.04) / 0.04)
                elif t_qrs < 0.12:
                    val = 2.0 - 3.0 * ((t_qrs - 0.08) / 0.04)
                else:
                    val = -1.0 * (1 - (t_qrs - 0.12) / 0.08)
            elif phase < 0.40:
                val = 0.3 * math.sin(math.pi * (phase - 0.20) / 0.20)
            st_elevation = 0.5 if self.rhythm == "stem" else -0.15
            if 0.20 <= phase < 0.40:
                val += st_elevation * min(1.0, (phase - 0.20) / 0.05)
            self.r_peak_detected = (0.12 < phase < 0.20)
        
        # 室速 VT
        elif self.rhythm == "vt":
            if phase < 0.20:
                t_qrs = phase - 0.02
                if t_qrs < 0:
                    val = 0.0
                elif t_qrs < 0.04:
                    val = -1.5 * (t_qrs / 0.04)
                elif t_qrs < 0.08:
                    val = -1.5 + 4.0 * ((t_qrs - 0.04) / 0.04)
                elif t_qrs < 0.12:
                    val = 2.5 - 4.0 * ((t_qrs - 0.08) / 0.04)
                elif t_qrs < 0.18:
                    val = -1.5 * (1 - (t_qrs - 0.12) / 0.06)
                else:
                    val = 0.0
            self.r_peak_detected = (0.04 < phase < 0.16)
        
        # 室上速 SVT
        elif self.rhythm == "svt":
            if phase < 0.10:
                val = 0.15 * math.sin(math.pi * phase / 0.10)
            elif phase < 0.18:
                t_qrs = phase - 0.10
                if t_qrs < 0.03:
                    val = -1.0 * (t_qrs / 0.03)
                elif t_qrs < 0.06:
                    val = -1.0 + 3.0 * ((t_qrs - 0.03) / 0.03)
                elif t_qrs < 0.08:
                    val = 2.0 - 3.0 * ((t_qrs - 0.06) / 0.02)
            elif phase < 0.30:
                val = 0.25 * math.sin(math.pi * (phase - 0.18) / 0.12)
            self.r_peak_detected = (0.10 < phase < 0.18)
        
        # 单形性室速 MPVT
        elif self.rhythm == "mpvt":
            if phase < 0.25:
                t_qrs = phase - 0.02
                if t_qrs < 0:
                    val = 0.0
                elif t_qrs < 0.05:
                    val = -1.8 * (t_qrs / 0.05)
                elif t_qrs < 0.10:
                    val = -1.8 + 4.5 * ((t_qrs - 0.05) / 0.05)
                elif t_qrs < 0.15:
                    val = 2.7 - 4.5 * ((t_qrs - 0.10) / 0.05)
                elif t_qrs < 0.23:
                    val = -1.8 * (1 - (t_qrs - 0.15) / 0.08)
                else:
                    val = 0.0
            self.r_peak_detected = (0.05 < phase < 0.18)
        
        # 多形性室速 SPVT
        elif self.rhythm == "spvt":
            self._spvt_count = (self._spvt_count + 1) % 100
            morph_index = self._spvt_count // 20
            morph_amp = [0.8, 1.3, 0.6, 1.0, 1.5][morph_index % 5]
            morph_width = [0.12, 0.08, 0.16, 0.10, 0.14][morph_index % 5]
            if phase < 0.25:
                t_qrs = phase - 0.02
                if t_qrs < 0:
                    val = 0.0
                elif t_qrs < morph_width * 0.25:
                    val = -1.5 * morph_amp * (t_qrs / (morph_width * 0.25))
                elif t_qrs < morph_width * 0.5:
                    val = morph_amp * (-1.5 + 4.0 * ((t_qrs - morph_width * 0.25) / (morph_width * 0.25)))
                elif t_qrs < morph_width * 0.75:
                    val = morph_amp * (2.5 - 4.0 * ((t_qrs - morph_width * 0.5) / (morph_width * 0.25)))
                elif t_qrs < morph_width:
                    val = morph_amp * (-1.5 * (1 - (t_qrs - morph_width * 0.75) / (morph_width * 0.25)))
                else:
                    val = 0.0
            self.r_peak_detected = (0.04 < phase < 0.20)
        
        # 尖端扭转型 TdP
        elif self.rhythm == "tdp":
            envelope_period = 4.0
            self._tdp_amp = 0.3 + 0.7 * abs(math.sin(2 * math.pi * self.t / envelope_period))
            if phase < 0.22:
                t_qrs = phase - 0.01
                if t_qrs < 0:
                    val = 0.0
                elif t_qrs < 0.04:
                    val = self._tdp_amp * (-1.5 * (t_qrs / 0.04))
                elif t_qrs < 0.08:
                    val = self._tdp_amp * (-1.5 + 4.0 * ((t_qrs - 0.04) / 0.04))
                elif t_qrs < 0.12:
                    val = self._tdp_amp * (2.5 - 4.0 * ((t_qrs - 0.08) / 0.04))
                elif t_qrs < 0.21:
                    val = self._tdp_amp * (-1.5 * (1 - (t_qrs - 0.12) / 0.09))
                else:
                    val = 0.0
            self.r_peak_detected = (0.04 < phase < 0.16)
        
        # 心碎综合征 Takotsubo
        elif self.rhythm == "takotsubo":
            if phase < 0.12:
                val = 0.25 * math.sin(math.pi * phase / 0.12)
            elif phase < 0.20:
                t_qrs = phase - 0.12
                if t_qrs < 0.04:
                    val = -1.0 * (t_qrs / 0.04)
                elif t_qrs < 0.08:
                    val = -1.0 + 3.0 * ((t_qrs - 0.04) / 0.04)
                elif t_qrs < 0.12:
                    val = 2.0 - 3.0 * ((t_qrs - 0.08) / 0.04)
                else:
                    val = -1.0 * (1 - (t_qrs - 0.12) / 0.08)
            elif phase < 0.50:
                t_t = phase - 0.20
                st_elev = 0.3 * min(1.0, (phase - 0.20) / 0.04)
                t_inv = -0.8 * math.sin(math.pi * t_t / 0.30)
                if t_t < 0.30:
                    val = st_elev + t_inv
                else:
                    val = t_inv * (1 - (t_t - 0.30) / 0.20)
            self.r_peak_detected = (0.12 < phase < 0.20)
        
        # 交界性逸搏心律
        elif self.rhythm == "junctional":
            if phase < 0.16:
                t_qrs = phase - 0.02
                if t_qrs < 0:
                    val = 0.0
                elif t_qrs < 0.04:
                    val = -0.8 * (t_qrs / 0.04)
                elif t_qrs < 0.08:
                    val = -0.8 + 2.0 * ((t_qrs - 0.04) / 0.04)
                elif t_qrs < 0.14:
                    val = 1.2 - 2.0 * ((t_qrs - 0.08) / 0.06)
            elif phase < 0.30:
                val = 0.2 * math.sin(math.pi * (phase - 0.16) / 0.14)
            self.r_peak_detected = (0.04 < phase < 0.14)
        
        # 停搏 (V11.31: 严格等电位线)
        elif self.rhythm == "asystole":
            val = 0.0
            self.r_peak_detected = False
        
        # 基线漂移 + 噪声
        baseline = 0.03 * math.sin(0.08 * self.t)
        noise = random.gauss(0, 0.015)
        # V11.31: 停搏不叠加基线漂移和噪声
        if self.rhythm == "asystole":
            return val
        return val + baseline + noise
    
    def get_r_peak(self):
        return self.r_peak_detected
    
    @classmethod
    def get_rhythm_list(cls):
        return list(cls.RHYTHM_META.keys())
    
    @classmethod
    def get_rhythm_name(cls, key):
        return cls.RHYTHM_META.get(key, {}).get("name", key)
    
    @classmethod
    def get_rhythm_info(cls, key):
        meta = cls.RHYTHM_META.get(key, {})
        return {
            "name": meta.get("name", key),
            "category": meta.get("category", ""),
            "default_hr": meta.get("default_hr", 72),
            "qrs_width": meta.get("qrs_width", ""),
            "desc": meta.get("desc", ""),
        }

# ==================== 心率上下限映射 ====================

def get_hr_limits(rhythm):
    """返回 (下限, 上限)"""
    limits = {
        "normal": (60, 100),
        "窦性心动过缓": (30, 59),
        "窦性心动过速": (101, 180),
        "心肌缺血": (50, 130),
        "心肌梗死(STEMI)": (60, 150),
        "心肌梗死(NSTEMI)": (60, 150),
        "室颤(VF)": (260, 330),
        "室颤(VF儿童)": (180, 260),
        "房颤(AF)": (80, 180),
        "室速(VT)": (100, 250),
        "室上速(SVT)": (150, 250),
        "交界性心率": (40, 100),
        "停搏(asystole)": (0, 0),
        "起搏心律": (50, 120),
    }
    return limits.get(rhythm, (60, 100))

HR_LIMITS = get_hr_limits

# ==================== ECG波形生成器 (主引擎) ====================

class ECGGene:
    def __init__(self, hr=72, rhythm="normal"):
        self.hr = hr
        self.t = 0.0
        self.dt = 0.04
        self.rhythm = rhythm
        self.r_peak_detected = False
        self.r_peak_timer = 0
        
        self.p_amp = 0.25
        self.q_amp = -0.3
        self.r_amp = 1.5
        self.s_amp = -0.5
        self.t_amp = 0.35
        self.u_amp = 0.05
        
        self.qt_interval = 0.40
        self.qrs_duration = 0.10
        self.pr_interval = 0.16
        
        self.st_elevation = 0.0
        self.st_depression = 0.0
        self.st_ischemic = False
        
        self.af_f_wave_amp = 0.15
        self.af_f_wave_freq = 8.0
        
        self.respiratory_arrhythmia = 0.05
        
        self._stemi_elevation = 0.0
        self._nstemi_depression = 0.0
        self._stemi_phase = 0.0
        
        # 除颤动画状态
        self.shock_animation = False
        self.shock_phase = 0
        self.shock_timer = 0
        self.shock_noise_amplitude = 1.0
        
        # ===== V10.0.0: 导联系数 =====
        self.lead_coeff = 1.0  # II=1.0, I=0.8, III=1.1
        self.lead_deep_q = False  # III导联深Q波

    def set_rhythm(self, rhythm):
        self.rhythm = rhythm
        self.t = 0.0
        self.st_elevation = 0.0
        self.st_depression = 0.0
        self.st_ischemic = False
        self._stemi_elevation = 0.0
        self._nstemi_depression = 0.0
        self._stemi_phase = 0.0

    def set_hr(self, hr):
        limits = get_hr_limits(self.rhythm)
        if limits[0] == 0 and limits[1] == 0:
            self.hr = 0
        else:
            self.hr = max(limits[0], min(limits[1], hr))
        if self.hr > 0:
            rr_interval = 60.0 / self.hr
            self.qt_interval = 0.40 * math.sqrt(rr_interval / 1.0)
            self.qt_interval = max(0.28, min(0.52, self.qt_interval))

    def set_st_elevation(self, elevation_mv):
        self.st_elevation = max(0.0, min(0.8, elevation_mv))
        self.st_depression = 0.0
        self.st_ischemic = elevation_mv > 0.1

    def set_st_depression(self, depression_mv):
        self.st_depression = max(0.0, min(0.5, depression_mv))
        self.st_elevation = 0.0
        self.st_ischemic = depression_mv > 0.05
    
    def trigger_shock_animation(self):
        self.shock_animation = True
        self.shock_phase = 1
        self.shock_timer = 0
        self.shock_noise_amplitude = 1.0

    def _update_shock_animation(self):
        if not self.shock_animation:
            return
        self.shock_timer += 1
        if self.shock_phase == 1:
            if self.shock_timer < 15:
                self.shock_noise_amplitude = 1.0 - (self.shock_timer / 15) * 0.3
            else:
                self.shock_phase = 2
                self.shock_timer = 0
                self.shock_noise_amplitude = 0.7
        elif self.shock_phase == 2:
            if self.shock_timer < 20:
                progress = self.shock_timer / 20
                self.shock_noise_amplitude = 0.7 + progress * 0.8
            else:
                self.shock_animation = False
                self.shock_phase = 0
                self.shock_timer = 0
                self.shock_noise_amplitude = 1.0

    def _update_stemi_values(self):
        if self.rhythm == "心肌梗死(STEMI)":
            if self._stemi_elevation == 0.0:
                self._stemi_elevation = 0.3 + 0.3 * random.random()
            self._stemi_phase += 0.002
            variation = 0.08 * math.sin(self._stemi_phase * 2 * math.pi / 10.0)
            current_elevation = max(0.2, min(0.8, self._stemi_elevation + variation))
            self.set_st_elevation(current_elevation)
        elif self.rhythm == "心肌梗死(NSTEMI)":
            if self._nstemi_depression == 0.0:
                self._nstemi_depression = 0.15 + 0.15 * random.random()
            self._stemi_phase += 0.002
            variation = 0.05 * math.sin(self._stemi_phase * 2 * math.pi / 8.0)
            current_depression = max(0.05, min(0.5, self._nstemi_depression + variation))
            self.set_st_depression(current_depression)
            self.t_amp = -0.25

    def set_lead(self, lead):
        """设置导联: I, II, III"""
        if lead == "I":
            self.lead_coeff = 0.8
            self.lead_deep_q = False
        elif lead == "II":
            self.lead_coeff = 1.0
            self.lead_deep_q = False
        elif lead == "III":
            self.lead_coeff = 1.1
            self.lead_deep_q = True
        else:
            self.lead_coeff = 1.0
            self.lead_deep_q = False

    def next(self):
        # 更新除颤动画
        if self.shock_animation:
            self._update_shock_animation()
        
        if self.hr == 0 and not self.shock_animation:
            return random.gauss(0, 0.005)
        
        self.t += self.dt
        period = 60.0 / self.hr if self.hr > 0 else 1.0
        phase = self.t % period
        val = 0.0
        
        resp_phase = 2 * math.pi * self.t / 4.0
        hr_variation = 1.0 + self.respiratory_arrhythmia * math.sin(resp_phase)
        effective_hr = self.hr * hr_variation
        effective_period = 60.0 / effective_hr if effective_hr > 0 else period
        effective_phase = self.t % effective_period
        
        use_phase = effective_phase if self.rhythm in ["normal", "窦性心动过缓", "窦性心动过速"] else phase
        t_norm = use_phase / effective_period
        
        # 除颤动画
        if self.shock_animation and self.shock_phase == 1:
            noise = random.gauss(0, 0.8 * self.shock_noise_amplitude)
            high_freq = 0.5 * math.sin(2 * math.pi * 25 * self.t) * self.shock_noise_amplitude
            return noise + high_freq
        
        if self.shock_animation and self.shock_phase == 2:
            amp_boost = self.shock_noise_amplitude
            r_boost = 0.8 * math.exp(-((t_norm - 0.2) ** 2) / 0.01) * amp_boost
            
            if t_norm < 0.12:
                p_phase = t_norm / 0.12
                p_val = self.p_amp * math.sin(math.pi * p_phase) * amp_boost * self.lead_coeff
                p_val = p_val * (1 - math.exp(-10 * p_phase))
                val += p_val
            elif t_norm < 0.22:
                qrs_phase = (t_norm - 0.12) / 0.10
                if qrs_phase < 0.15:
                    q_val = self.q_amp * (qrs_phase / 0.15) * amp_boost * self.lead_coeff
                    if self.lead_deep_q:
                        q_val *= 1.5
                    val += q_val
                elif qrs_phase < 0.55:
                    r_phase = (qrs_phase - 0.15) / 0.40
                    r_val = self.r_amp * math.sin(math.pi * r_phase) * amp_boost * 1.5 * self.lead_coeff
                    r_val = r_val * (1 - math.exp(-8 * r_phase)) * (1 - math.exp(-8 * (1 - r_phase)))
                    val += r_val + r_boost * 0.5
                elif qrs_phase < 0.85:
                    s_phase = (qrs_phase - 0.55) / 0.30
                    s_val = self.s_amp * math.sin(math.pi * s_phase) * amp_boost * self.lead_coeff
                    s_val = s_val * (1 - math.exp(-6 * s_phase)) * (1 - math.exp(-6 * (1 - s_phase)))
                    val += s_val
                else:
                    terminal_phase = (qrs_phase - 0.85) / 0.15
                    val += -0.1 * terminal_phase * (1 - terminal_phase) * amp_boost * self.lead_coeff
            elif t_norm < 0.55:
                st_t_phase = (t_norm - 0.22) / 0.33
                if st_t_phase < 0.30:
                    st_phase = st_t_phase / 0.30
                    st_shift = self.st_elevation - self.st_depression
                    st_val = st_shift * (1 - math.exp(-5 * st_phase)) * amp_boost * self.lead_coeff
                    val += st_val
                else:
                    t_phase = (st_t_phase - 0.30) / 0.70
                    t_val = self.t_amp * math.sin(math.pi * t_phase) * amp_boost * 1.3 * self.lead_coeff
                    t_val = t_val * (1 - math.exp(-6 * t_phase)) * (1 - math.exp(-6 * (1 - t_phase)))
                    val += t_val
            else:
                val += 0.0
            
            if 0.12 < t_norm < 0.22:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False
            
            baseline = 0.02 * math.sin(0.2 * self.t) + 0.01 * math.sin(0.05 * self.t)
            noise = random.gauss(0, 0.01)
            return val + baseline + noise
        
        # 正常波形
        if self.rhythm in ["normal", "窦性心动过缓", "窦性心动过速", "心肌缺血", "心肌梗死(STEMI)", "心肌梗死(NSTEMI)"]:
            if self.rhythm in ["心肌梗死(STEMI)", "心肌梗死(NSTEMI)"]:
                self._update_stemi_values()
            
            if t_norm < 0.12:
                p_phase = t_norm / 0.12
                p_val = self.p_amp * math.sin(math.pi * p_phase) * self.lead_coeff
                p_val = p_val * (1 - math.exp(-10 * p_phase))
                val += p_val
            elif t_norm < 0.22:
                qrs_phase = (t_norm - 0.12) / 0.10
                if qrs_phase < 0.15:
                    q_val = self.q_amp * (qrs_phase / 0.15) * self.lead_coeff
                    if self.lead_deep_q:
                        q_val *= 1.5
                    val += q_val
                elif qrs_phase < 0.55:
                    r_phase = (qrs_phase - 0.15) / 0.40
                    r_val = self.r_amp * math.sin(math.pi * r_phase) * self.lead_coeff
                    r_val = r_val * (1 - math.exp(-8 * r_phase)) * (1 - math.exp(-8 * (1 - r_phase)))
                    val += r_val
                    if 0.25 < qrs_phase < 0.45:
                        self.r_peak_detected = True
                        self.r_peak_timer = 12
                elif qrs_phase < 0.85:
                    s_phase = (qrs_phase - 0.55) / 0.30
                    s_val = self.s_amp * math.sin(math.pi * s_phase) * self.lead_coeff
                    s_val = s_val * (1 - math.exp(-6 * s_phase)) * (1 - math.exp(-6 * (1 - s_phase)))
                    val += s_val
                else:
                    terminal_phase = (qrs_phase - 0.85) / 0.15
                    val += -0.1 * terminal_phase * (1 - terminal_phase) * self.lead_coeff
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False
            elif t_norm < 0.55:
                st_t_phase = (t_norm - 0.22) / 0.33
                if st_t_phase < 0.30:
                    st_phase = st_t_phase / 0.30
                    st_shift = self.st_elevation - self.st_depression
                    st_val = st_shift * (1 - math.exp(-5 * st_phase)) * self.lead_coeff
                    if self.st_ischemic:
                        st_val += 0.05 * math.sin(math.pi * st_phase)
                    val += st_val
                else:
                    t_phase = (st_t_phase - 0.30) / 0.70
                    t_val = self.t_amp * math.sin(math.pi * t_phase) * self.lead_coeff
                    t_val = t_val * (1 - math.exp(-6 * t_phase)) * (1 - math.exp(-6 * (1 - t_phase)))
                    if self.st_ischemic and t_phase > 0.3:
                        t_val *= 1.5
                    val += t_val
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False
            elif t_norm < 0.65:
                u_phase = (t_norm - 0.55) / 0.10
                u_val = self.u_amp * math.sin(math.pi * u_phase) * self.lead_coeff
                u_val = u_val * (1 - math.exp(-8 * u_phase)) * (1 - math.exp(-8 * (1 - u_phase)))
                val += u_val
            else:
                val += 0.0
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False

        elif self.rhythm == "房颤(AF)":
            f_wave = self.af_f_wave_amp * math.sin(2 * math.pi * self.af_f_wave_freq * self.t)
            f_wave += 0.05 * math.sin(2 * math.pi * 2 * self.af_f_wave_freq * self.t)
            f_wave += 0.03 * math.sin(2 * math.pi * 3 * self.af_f_wave_freq * self.t)
            f_wave *= (0.5 + 0.5 * math.sin(2 * math.pi * 0.5 * self.t))
            if phase < 0.08:
                val = 0.5 * math.sin(math.pi * phase / 0.08) * self.lead_coeff
            elif phase < 0.16:
                t_qrs = phase - 0.08
                if t_qrs < 0.03:
                    val = -0.6 * (t_qrs / 0.03) * self.lead_coeff
                elif t_qrs < 0.06:
                    val = -0.6 + 1.8 * ((t_qrs - 0.03) / 0.03) * self.lead_coeff
                else:
                    val = 1.2 - 1.8 * ((t_qrs - 0.06) / 0.03) * self.lead_coeff
            else:
                val = 0.0
            if 0.08 < phase < 0.16:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False
            val += f_wave * 0.8 * self.lead_coeff

        elif self.rhythm == "室颤(VF)":
            vf_rate = 260 + 70 * random.random()
            self.hr = int(vf_rate)
            val = random.gauss(0, 0.6) + 0.3 * math.sin(2 * math.pi * (vf_rate/60) * self.t)
            val = max(-1.2, min(1.2, val))
            self.r_peak_detected = False

        elif self.rhythm == "室颤(VF儿童)":
            vf_rate = 180 + 80 * random.random()
            self.hr = int(vf_rate)
            val = random.gauss(0, 0.7) + 0.3 * math.sin(2 * math.pi * (vf_rate/60) * self.t)
            val = max(-1.2, min(1.2, val))
            self.r_peak_detected = False

        elif self.rhythm == "室速(VT)":
            if phase < 0.15:
                val = -0.3 * (phase / 0.15) * self.lead_coeff
            elif phase < 0.45:
                t_qrs = phase - 0.15
                if t_qrs < 0.10:
                    val = -0.3 + 2.0 * (t_qrs / 0.10) * self.lead_coeff
                elif t_qrs < 0.25:
                    val = 1.7 - 2.5 * ((t_qrs - 0.10) / 0.15) * self.lead_coeff
                else:
                    val = -0.8 * (1 - (t_qrs - 0.25) / 0.20) * self.lead_coeff
            elif phase < 0.65:
                t_t = phase - 0.45
                val = 0.4 * math.sin(math.pi * t_t / 0.20) * self.lead_coeff
            else:
                val = 0.0
            if 0.15 < phase < 0.45:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False

        elif self.rhythm == "室上速(SVT)":
            if phase < 0.10:
                val = 0.3 * math.sin(math.pi * phase / 0.10) * self.lead_coeff
            elif phase < 0.18:
                t_qrs = phase - 0.10
                if t_qrs < 0.03:
                    val = -0.4 * (t_qrs / 0.03) * self.lead_coeff
                elif t_qrs < 0.06:
                    val = -0.4 + 1.5 * ((t_qrs - 0.03) / 0.03) * self.lead_coeff
                else:
                    val = 1.1 - 1.5 * ((t_qrs - 0.06) / 0.03) * self.lead_coeff
            elif phase < 0.40:
                t_t = phase - 0.18
                val = 0.35 * math.sin(math.pi * t_t / 0.22) * self.lead_coeff
            else:
                val = 0.0
            if 0.10 < phase < 0.18:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False

        elif self.rhythm == "交界性心率":
            if phase < 0.12:
                val = 0.2 * math.sin(math.pi * phase / 0.12) * self.lead_coeff
            elif phase < 0.20:
                t_qrs = phase - 0.12
                if t_qrs < 0.04:
                    val = -0.4 * (t_qrs / 0.04) * self.lead_coeff
                elif t_qrs < 0.08:
                    val = -0.4 + 1.6 * ((t_qrs - 0.04) / 0.04) * self.lead_coeff
                else:
                    val = 1.2 - 1.6 * ((t_qrs - 0.08) / 0.04) * self.lead_coeff
            elif phase < 0.45:
                t_t = phase - 0.20
                val = 0.3 * math.sin(math.pi * t_t / 0.25) * self.lead_coeff
            else:
                val = 0.0
            if 0.12 < phase < 0.20:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False

        elif self.rhythm == "停搏(asystole)":
            val = random.gauss(0, 0.005)
            self.r_peak_detected = False

        elif self.rhythm == "起搏心律":
            if phase < 0.02:
                val = 0.6 * math.sin(math.pi * phase / 0.02) * self.lead_coeff
            elif phase < 0.10:
                val = 0.1 * math.sin(math.pi * (phase - 0.02) / 0.08) * self.lead_coeff
            elif phase < 0.22:
                t_qrs = phase - 0.10
                if t_qrs < 0.04:
                    val = -0.5 * (t_qrs / 0.04) * self.lead_coeff
                elif t_qrs < 0.08:
                    val = -0.5 + 1.8 * ((t_qrs - 0.04) / 0.04) * self.lead_coeff
                else:
                    val = 1.3 - 1.8 * ((t_qrs - 0.08) / 0.04) * self.lead_coeff
            elif phase < 0.50:
                t_t = phase - 0.22
                val = 0.3 * math.sin(math.pi * t_t / 0.28) * self.lead_coeff
            else:
                val = 0.0
            if 0.10 < phase < 0.22:
                self.r_peak_detected = True
                self.r_peak_timer = 10
            else:
                if self.r_peak_timer > 0:
                    self.r_peak_timer -= 1
                else:
                    self.r_peak_detected = False

        baseline = 0.02 * math.sin(0.2 * self.t) + 0.01 * math.sin(0.05 * self.t)
        noise = random.gauss(0, 0.015)
        return val + baseline + noise

    def get_r_peak(self):
        return self.r_peak_detected
    
    def is_in_shock_animation(self):
        return self.shock_animation
    
    def get_shock_phase(self):
        return self.shock_phase

# ==================== SPO2/呼吸生成器 ====================

class ParameterGene:
    def __init__(self, type="spo2", value=98):
        self.type = type
        self.value = value
        self.t = 0.0
        self.dt = 0.04

    def next(self):
        if self.value == 0:
            return 0.0
        self.t += self.dt
        if self.type == "spo2":
            phase = self.t % 0.8
            if phase < 0.1:
                val = 1.0 * (phase / 0.1)
            else:
                val = 1.0 * math.exp(-(phase - 0.1) / 0.3)
            return val + random.gauss(0, 0.02)
        else:
            breathing_rate = 12 + (self.value - 12) * 0.1
            val = 0.8 * math.sin(2 * math.pi * self.t / (60.0 / breathing_rate))
            return val + random.gauss(0, 0.02)

    def set_value(self, val):
        self.value = val

# ==================== 动态阻抗生成器 (V11.00) ====================

class ImpedanceGenerator:
    """动态阻抗生成模块 - 模拟电极片贴敷质量变化
    
    特性:
    - 基线阻抗: 40-80Ω (正常贴敷)
    - 电极片干燥: 随时间缓慢爬升 (50→130Ω)
    - 接触不良: 瞬时跳变到 200Ω+ 或 999Ω (电极脱落)
    - 用户操作: 贴/拔/按压电极触发阻抗突变
    """
    
    def __init__(self):
        # 基线配置
        self.base_impedance = random.uniform(40, 80)  # 正常基线 40-80Ω
        self.current = self.base_impedance
        
        # 电极片老化/干燥模拟
        self.dry_timer = 0.0          # 累计干燥时间(秒)
        self.dry_threshold = random.uniform(30, 120)  # 开始干燥的阈值(秒)
        self.dry_rate = random.uniform(0.3, 0.8)      # 干燥速率 (Ω/秒)
        self.dry_max = 130.0          # 干燥最大阻抗值
        
        # 接触不良状态
        self.poor_contact = False
        self.contact_prob = 0.002     # 每秒随机触发接触不良的概率
        self.poor_contact_value = 0.0 # 接触不良时的目标阻抗
        
        # 电极脱落状态
        self.pads_detached = False
        self.detach_value = 999.0
        
        # 按压改善
        self.press_active = False
        self.press_timer = 0.0
        self.press_duration = 15.0    # 按压效果持续15秒
        
        # 历史记录
        self.peak_impedance = self.current
        self.intervention_count = 0   # 用户干预次数
    
    def update(self, dt=1.0):
        """每个时间步更新阻抗值 (dt: 秒)"""
        
        # 电极脱落状态: 保持999Ω
        if self.pads_detached:
            self.current = self.detach_value
            self.peak_impedance = max(self.peak_impedance, self.current)
            return self.current
        
        # 按压改善状态: 临时降低阻抗
        if self.press_active:
            self.press_timer -= dt
            if self.press_timer <= 0:
                self.press_active = False
                # 按压结束后恢复到正常基线
                self.current = self.base_impedance + min(self.dry_timer * self.dry_rate, self.dry_max - self.base_impedance)
            else:
                # 按压期间阻抗大幅降低
                target = self.base_impedance * 0.6
                self.current += (target - self.current) * 0.3
            self.peak_impedance = max(self.peak_impedance, self.current)
            return self.current
        
        # 接触不良状态: 维持高阻抗
        if self.poor_contact:
            # 接触不良期间阻抗围绕目标值波动
            noise = random.gauss(0, 5)
            self.current = self.poor_contact_value + noise
            self.current = max(self.base_impedance, min(999, self.current))
            self.peak_impedance = max(self.peak_impedance, self.current)
            return self.current
        
        # 正常状态下的阻抗演变
        self.dry_timer += dt
        
        # 随机触发接触不良
        if self.dry_timer > self.dry_threshold and random.random() < self.contact_prob:
            self.trigger_poor_contact()
            return self.current
        
        # 干燥效应: 超过阈值后缓慢爬升
        dry_effect = 0.0
        if self.dry_timer > self.dry_threshold:
            dry_effect = (self.dry_timer - self.dry_threshold) * self.dry_rate
            dry_effect = min(dry_effect, self.dry_max - self.base_impedance)
        
        # 添加微小噪声
        noise = random.gauss(0, 0.5)
        self.current = self.base_impedance + dry_effect + noise
        self.current = max(30, min(999, self.current))
        
        self.peak_impedance = max(self.peak_impedance, self.current)
        return self.current
    
    def trigger_poor_contact(self):
        """触发接触不良: 阻抗跳变到200-500Ω"""
        self.poor_contact = True
        self.poor_contact_value = random.uniform(200, 500)
        self.current = self.poor_contact_value
    
    def resolve_poor_contact(self):
        """解除接触不良状态"""
        self.poor_contact = False
        self.poor_contact_value = 0.0
        self.current = self.base_impedance + min(self.dry_timer * self.dry_rate, self.dry_max - self.base_impedance)
    
    def simulate_pad_attach(self):
        """模拟贴上电极片: 阻抗回归正常基线"""
        self.pads_detached = False
        self.poor_contact = False
        self.press_active = False
        # 重置干燥计时器 (新电极片)
        self.dry_timer = 0.0
        self.dry_threshold = random.uniform(30, 120)
        self.base_impedance = random.uniform(40, 80)
        self.current = self.base_impedance
        self.intervention_count += 1
    
    def simulate_pad_detach(self):
        """模拟拔掉电极片: 阻抗跳到999Ω"""
        self.pads_detached = True
        self.poor_contact = False
        self.press_active = False
        self.current = self.detach_value
        self.intervention_count += 1
    
    def simulate_press_electrode(self):
        """模拟用力按压电极: 阻抗大幅降低"""
        if self.pads_detached:
            # 如果电极已脱落，按压无效
            return False
        self.press_active = True
        self.press_timer = self.press_duration
        self.poor_contact = False
        self.intervention_count += 1
        return True
    
    def get_current(self):
        """获取当前阻抗值"""
        return self.current
    
    def get_status(self):
        """获取阻抗状态摘要"""
        if self.pads_detached:
            return "电极脱落", "danger"
        if self.poor_contact:
            return "接触不良", "warning"
        if self.current > 200:
            return "阻抗过高", "danger"
        if self.current > 150:
            return "阻抗偏高", "warning"
        if self.current > 100:
            return "阻抗正常偏高", "caution"
        return "正常", "normal"
    
    def get_dry_progress(self):
        """获取干燥进度百分比"""
        if self.dry_timer <= self.dry_threshold:
            return 0.0
        progress = (self.dry_timer - self.dry_threshold) * self.dry_rate / (self.dry_max - self.base_impedance)
        return min(1.0, max(0.0, progress))
    
    def reset(self):
        """重置所有状态"""
        self.__init__()

# ==================== 事件记录类 (V10.0.0: 增加抢救复盘) ====================

class EventLogger:
    def __init__(self):
        self.events = []
        self.test_history = []
        self.code_reports = []  # V10.0.0: 抢救复盘报告
        self.shock_attempts = 0  # V11.00: 电击尝试计数
    
    def log_event(self, event_type, description, details=None):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": event_type,
            "description": description,
            "details": details or {}
        }
        self.events.append(entry)
        return entry
    
    def log_impedance_event(self, event_type, description, impedance_value, details=None):
        """V11.00: 记录阻抗/电极贴敷质量相关事件"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": event_type,
            "description": description,
            "impedance": round(impedance_value, 1),
            "electrode_quality": self._classify_impedance(impedance_value),
            "details": details or {}
        }
        self.events.append(entry)
        return entry
    
    def log_shock_blocked(self, shock_number, impedance_value, reason):
        """V11.00: 记录除颤被拦截事件"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "type": "安全拦截",
            "description": f"第{shock_number}次尝试除颤失败，原因为{reason}",
            "impedance": round(impedance_value, 1),
            "electrode_quality": self._classify_impedance(impedance_value),
            "shock_blocked": True,
            "details": {"shock_number": shock_number, "impedance": impedance_value, "reason": reason}
        }
        self.events.append(entry)
        return entry
    
    def _classify_impedance(self, imp):
        """V11.00: 阻抗分类"""
        if imp >= 999:
            return "电极脱落"
        if imp > 200:
            return "阻抗过大/接触不良"
        if imp > 150:
            return "阻抗偏高"
        if imp > 100:
            return "阻抗正常偏高"
        return "正常"
    
    def log_test(self, test_type, test_name, result, details=None):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "test_type": test_type,
            "test_name": test_name,
            "result": result,
            "details": details or {}
        }
        self.test_history.append(entry)
        return entry
    
    def log_code_report(self, report):
        """记录抢救复盘报告"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "report": report
        }
        self.code_reports.append(entry)
        return entry
    
    def get_code_reports(self):
        return self.code_reports
    
    def get_events(self):
        return self.events
    
    def get_test_history(self):
        return self.test_history
    
    def clear(self):
        self.events = []
        self.test_history = []
        self.code_reports = []

# ==================== 主模拟器 (V11.00) ====================

class MindrayD3DefibSim:
    def __init__(self, root):
        self.root = root
        self.root.title("Mindray BeneHeart D3 Sim v11.31 - 临床安全与复盘系统")
        self.root.attributes("-fullscreen", False)
        self.root.configure(bg="#f0f0f0")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        # ---- 核心状态 ----
        self.power_on = False
        self.mode_list = ["Off", "Monitor", "Pacer", "Manual Defib", "AED"]
        self.mode_idx = 0
        self.mode = self.mode_list[self.mode_idx]

        # ---- 导联与线路 ----
        self.lead_connected = False
        self.lead_alarm = False
        self.lead_alarm_visible = False
        self.line_connected = False
        self.alarm_active = False
        self.alarm_visible = False
        
        # ===== V10.0.0: 导联切换 =====
        self.current_lead = "II"  # I, II, III
        self.lead_cycle = ["II", "I", "III"]
        self.lead_idx = 0
        
        # ===== V10.0.0: ECG Pause (冻结) =====
        self.ecg_paused = False
        
        # ===== V10.0.0: 导联接触不良干扰 =====
        self.lead_drift = False
        self.lead_drift_timer = 0
        self.ecg_load_fault_prob = 0.02  # CHECK ECG LOAD 故障概率 (0.00-1.00)

        # ---- AED 电极片 ----
        self.aed_pads_connected = False

        # ---- 同步模式 ----
        self.sync_mode = False
        self.sync_pending = False
        self.sync_delay_task = None
        self.sync_flash_state = False

        # ---- 报警列表 ----
        self.sim_alarm_list = []
        self.sim_alarm_index = 0
        self.sim_alarm_visible = False
        self.shock_operation_flash_count = 0

        # ---- ROSC状态 ----
        self.rosc_active = False
        self.rosc_flash_state = False
        self.rosc_timer = 0
        
        # ===== V10.0.0: ROSC 抢救复盘数据 =====
        self.rosc_time_seconds = None  # 首次电击到ROSC的时间
        self.first_shock_timestamp = None  # 第一次电击时间
        self.total_shocks = 0
        self.code_medications = []  # 抢救用药清单

        # ---- 能量 ----
        self.energy_levels = [1,2,3,4,5,6,7,8,9,10,15,20,30,50,70,100,150,170,200,250,300,360]
        self.energy_idx = self.energy_levels.index(200)
        self.energy = self.energy_levels[self.energy_idx]

        self.charge_time_map = {
            1:0.5, 2:0.55, 3:0.6, 4:0.65, 5:0.7, 6:0.75, 7:0.8, 8:0.85, 9:0.9, 10:0.95,
            15:1.2, 20:1.45, 30:1.3, 50:1.5, 70:1.7,
            100:2.0, 150:2.2, 170:2.4, 200:2.5, 250:3.0, 300:5.0, 360:7.2
        }

        # ---- 状态标志 ----
        self.is_charged = False
        self.is_charging = False
        self.shock_enabled = False
        self._auto_disarming = False
        self._aed_energy_backup = None
        
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self._auto_charge_total = 0

        self.shock_count = 0
        # ===== V11.00: 动态阻抗系统 (替代硬编码 self.impedance = 52) =====
        self.impedance_gen = ImpedanceGenerator()  # 动态阻抗生成器
        self.impedance = self.impedance_gen.get_current()  # 兼容旧代码的阻抗访问
        self.impedance_high_warning = False  # 阻抗过高警告标志
        self._impedance_warning_shown = False  # 防止重复弹出警告
        self.timer_sec = 0
        self.co2_val = 43
        self.spo2_val = 98
        self.resp_rate = 16
        self.nibp_result = None
        self.show_nibp = False
        self.menu_open = False
        
        self.menu_selection = 0
        self.menu_options = []
        self.menu_scroll_offset = 0  # 菜单滚动偏移

        self.sim_menu_open = False
        self.sim_menu_selection = 0
        self.sim_menu_options = []

        self.pacer_mode = "经皮"
        self.pacer_current = 50
        self.pacer_rate = 72
        self.pacer_pulse_width = 20
        self.pacer_active = False
        self.pacer_demand_mode = False

        self.aed_analyzing = False
        self.aed_analysis_result = None
        self.aed_child_mode = False
        self.child_age = 5.0

        self.self_test_running = False
        self.self_test_step = 0
        self.self_test_steps = []
        self.self_test_result = {}
        self.key_test_index = 0
        self.key_test_targets = []
        self.is_auto_self_test = False
        self._self_test_buttons = []
        self._key_flash_count = 0
        self._key_test_active = False
        self._key_test_timeout_id = None
        self._current_test_start_time = None
        self._current_test_type = None
        self._key_test_phase = "idle"

        self._cable_test_in_progress = False
        self._cable_test_energy_done = False

        self._user_test_energies = [360, 200]
        self._user_test_current_energy = 0
        self._user_test_waiting = False

        self.charging_task_id = None
        self.auto_disarm_task = None
        self.charge_progress = 0
        self.flash_task = None
        self.alarm_flash_task = None
        self.shock_message_task = None
        self.shock_clear_task = None
        self._auto_task_id = None
        self._auto_charge_task_id = None

        self.post_shock_phase = 0
        self.post_shock_timer = 0
        self.post_shock_amplitude = 1.0
        self.post_shock_rhythm_original = None
        self.post_shock_hr_original = 72
        self._post_shock_last_rhythm = None
        
        self.vf_conversion_attempts = 0
        self.vf_is_child = False
        self.vf_initial_energy = 0
        self.vf_current_energy = 0

        self.ecg_rhythm = "normal"
        self.ecg_gene = ECGGene(hr=72, rhythm="normal")
        self.ecg_gene.set_lead("II")  # V10.0.0: 默认导联II
        self.ecg_data = []
        self.ecg_task_id = None
        self.timer_task_id = None

        self.spo2_gene = ParameterGene(type="spo2", value=98)
        self.spo2_data = []
        self.spo2_task_id = None

        self.resp_gene = ParameterGene(type="resp", value=16)
        self.resp_data = []
        self.resp_task_id = None

        self.sim_hr = 72
        self.sim_spo2 = 98
        self.sim_resp = 16
        self.sim_sys_bp = 120
        self.sim_dia_bp = 80
        self.sim_gender = "男"
        self.sim_age = 45
        self.sim_history = []
        self.sim_past_history = []

        self.event_logger = EventLogger()
        self.event_win_open = False

        self.drug_library_ui = None
        self.drug_curve_data = {}
        
        # ===== V10.0.0: Drug Simulator =====
        self.drug_simulator = DrugAdminSimulator(app=self)
        self.drug_library_ui = DrugLibraryUI(self.root, self)
        self.drug_library_ui.set_simulator(self.drug_simulator)

        self.COLOR_BODY = "#f0f0f0"
        self.COLOR_SCREEN_BG = "#000000"
        self.COLOR_TEXT_WHITE = "#ffffff"
        self.COLOR_TEXT_BLACK = "#000000"
        self.COLOR_TEXT_ORANGE = "#ff9900"
        self.COLOR_GREEN = "#36d036"
        self.COLOR_YELLOW = "#f9e047"
        self.COLOR_ORANGE_BTN = "#ff8822"
        self.COLOR_ORANGE_HIGHLIGHT = "#ff8800"
        self.COLOR_GRAY_LIGHT = "#b8c0c8"
        self.COLOR_RED_ALERT = "#ff2222"
        self.COLOR_ALARM_YELLOW = "#ffdd00"
        self.COLOR_BLUE = "#00aaff"
        self.COLOR_RESP = "#ffcc00"
        self.COLOR_SYNC = "#ffff00"
        self.COLOR_PACER = "#00ccff"
        self.COLOR_ROSC = "#00ff88"

        try:
            self.build_ui()
            self.mode_canvas.bind("<MouseWheel>", self.knob_mouse_wheel)
            self.mode_canvas.bind("<Button-1>", self.knob_click)
            self.ecg_task_id = self.root.after(40, self.update_ecg_loop)
            self.spo2_task_id = self.root.after(40, self.update_spo2_loop)
            self.resp_task_id = self.root.after(40, self.update_resp_loop)
            self.timer_task_id = self.root.after(1000, self.update_timer)
            self.update_alarm_flash()
            self.set_mode("Off")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("启动错误", str(e))

    # ==================== 药物浓度曲线更新 ====================
    
    def update_drug_curve_data(self, data):
        self.drug_curve_data = data
        self.draw_drug_curve()
    
    def draw_drug_curve(self):
        if not self.power_on or not self.drug_curve_data:
            self.screen_canvas.delete("drug_curve_area")
            self.screen_canvas.delete("drug_curve_legend")
            return
        
        cw = self.canvas_w
        ch = self.canvas_h
        
        curve_x1 = int(cw * 0.09)
        curve_x2 = int(cw * 0.75)
        curve_y1 = int(ch * 0.62)
        curve_y2 = int(ch * 0.85)
        
        self.screen_canvas.delete("drug_curve_area")
        self.screen_canvas.delete("drug_curve_legend")
        
        self.screen_canvas.create_rectangle(curve_x1, curve_y1, curve_x2, curve_y2,
                                           fill="#0a1a2a", outline="#444",
                                           tags="drug_curve_area")
        self.screen_canvas.create_text(curve_x1 + 10, curve_y1 + 5,
                                       text="💊 血浆浓度曲线", fill="#88ccff",
                                       font=("Arial", 9), anchor="nw",
                                       tags="drug_curve_area")
        
        margin = 30
        plot_w = curve_x2 - curve_x1 - 2 * margin
        plot_h = curve_y2 - curve_y1 - 2 * margin - 15
        
        if plot_w < 50 or plot_h < 30 or not self.drug_curve_data:
            return
        
        max_conc = max([d.get("concentration", 0) for d in self.drug_curve_data.values()]) if self.drug_curve_data else 1
        max_conc = max(max_conc, 0.1)
        max_time = max([d.get("elapsed", 0) + d.get("duration", 0) for d in self.drug_curve_data.values()]) if self.drug_curve_data else 5
        max_time = max(max_time, 2)
        
        ax_x1 = curve_x1 + margin
        ax_y1 = curve_y1 + margin + 15
        ax_x2 = curve_x2 - margin
        ax_y2 = curve_y2 - margin
        
        self.screen_canvas.create_line(ax_x1, ax_y1, ax_x1, ax_y2, fill="#888", width=1, tags="drug_curve_area")
        self.screen_canvas.create_line(ax_x1, ax_y2, ax_x2, ax_y2, fill="#888", width=1, tags="drug_curve_area")
        
        for i in range(4):
            y_pos = ax_y1 + (i / 3) * (ax_y2 - ax_y1)
            self.screen_canvas.create_line(ax_x1, y_pos, ax_x2, y_pos, fill="#1a2a3a", width=1, tags="drug_curve_area")
            self.screen_canvas.create_text(ax_x1 - 5, y_pos, text=f"{((3-i)/3) * max_conc:.1f}", 
                                          fill="#666", font=("Arial", 7), anchor="e", tags="drug_curve_area")
        
        for i in range(4):
            x_pos = ax_x1 + (i / 3) * (ax_x2 - ax_x1)
            self.screen_canvas.create_line(x_pos, ax_y1, x_pos, ax_y2, fill="#1a2a3a", width=1, tags="drug_curve_area")
            self.screen_canvas.create_text(x_pos, ax_y2 + 5, text=f"{i/3 * max_time:.1f}", 
                                          fill="#666", font=("Arial", 7), tags="drug_curve_area")
        
        legend_x = ax_x2 - 80
        legend_y = ax_y1 + 10
        
        for drug, info in self.drug_curve_data.items():
            color = info.get("color", "#ffffff")
            half_life = info.get("half_life", 2)
            duration = info.get("duration", 30)
            elapsed = info.get("elapsed", 0)
            current_conc = info.get("concentration", 0)
            
            points = []
            num_points = 30
            for i in range(num_points + 1):
                t = (i / num_points) * min(duration + 2, max_time)
                if t <= duration:
                    if t < 0.5:
                        conc = current_conc * (t / 0.5) * 1.2
                    else:
                        conc = current_conc * (0.5 ** ((t - 0.5) / half_life))
                else:
                    conc = current_conc * (0.5 ** ((duration - 0.5 + (t - duration)) / half_life)) * 0.3
                
                x = ax_x1 + (t / max_time) * (ax_x2 - ax_x1)
                y = ax_y2 - (conc / max_conc) * (ax_y2 - ax_y1)
                y = max(ax_y1, min(ax_y2, y))
                points.append((x, y))
            
            if len(points) > 1:
                self.screen_canvas.create_line(points, fill=color, width=2, smooth=True, tags="drug_curve_area")
            
            self.screen_canvas.create_rectangle(legend_x, legend_y - 3, legend_x + 10, legend_y + 7, 
                                               fill=color, tags="drug_curve_legend")
            self.screen_canvas.create_text(legend_x + 14, legend_y + 2, text=f"{drug} {current_conc:.2f}", 
                                          fill=color, font=("Arial", 7), anchor="w", tags="drug_curve_legend")
            legend_y += 14

    # ==================== 儿童能量管理 ====================
    
    def get_weight(self, age):
        if 3.0 <= age <= 6.0:
            return 2 * age + 8
        elif 6.0 < age <= 12.0:
            return 3 * age + 7
        elif 12.0 < age <= 17.0:
            return 4 * age + 5
        else:
            return None

    def get_child_energy_range(self, age):
        weight = self.get_weight(age)
        if weight is None:
            return (50, 100)
        min_energy = max(20, weight * 2)
        max_energy = min(200, weight * 4)
        min_energy = round(min_energy / 5) * 5
        max_energy = round(max_energy / 5) * 5
        return (int(min_energy), int(max_energy))

    def get_available_child_energies(self, age):
        min_e, max_e = self.get_child_energy_range(age)
        available = [e for e in self.energy_levels if min_e <= e <= max_e]
        if not available:
            available = [min_e, max_e]
        return available

    def get_child_energy_sequence(self, age):
        available = self.get_available_child_energies(age)
        if not available:
            return [50, 70, 100]
        available.sort()
        return available

    def get_energy_for_attempt(self, age, attempt):
        weight = self.get_weight(age)
        if weight is None:
            return 100
        if attempt == 0:
            energy = weight * 2
        else:
            energy = weight * 4
        energy = max(20, min(200, energy))
        energy = round(energy / 5) * 5
        available = self.get_available_child_energies(age)
        if available:
            closest = min(available, key=lambda x: abs(x - energy))
            return closest
        return int(energy)

    # ==================== V10.0.0: 导联切换 ====================
    
    def cycle_lead(self):
        """循环切换导联 I → II → III → I"""
        if self._is_in_self_test():
            return
        self.lead_idx = (self.lead_idx + 1) % len(self.lead_cycle)
        self.current_lead = self.lead_cycle[self.lead_idx]
        self.ecg_gene.set_lead(self.current_lead)
        self.event_logger.log_event("导联", f"切换至 {self.current_lead}")
        self.draw_screen_static()
    
    # ===== V10.0.0: ECG Pause (冻结) =====
    
    def toggle_ecg_pause(self):
        """切换ECG冻结/恢复"""
        if self._is_in_self_test():
            return
        self.ecg_paused = not self.ecg_paused
        if not self.ecg_paused:
            # 解除冻结时清除旧波形数据，避免显示混乱
            self.ecg_data = []
        status = "冻结" if self.ecg_paused else "解除"
        self.event_logger.log_event("ECG", f"波形{status}")
        self.draw_screen_static()
    
    # ===== V10.0.0: 导联接触不良干扰触发 =====
    
    def trigger_lead_drift(self):
        """触发导联干扰"""
        if not self.lead_connected:
            return
        self.lead_drift = True
        self.lead_drift_timer = 30  # 持续约1.2秒
        if "lead_drift" not in self.sim_alarm_list:
            self.sim_alarm_list.append("lead_drift")
        self.event_logger.log_event("干扰", "导联接触不良")
        self.draw_screen_static()
    
    def clear_lead_drift(self):
        """清除导联干扰"""
        self.lead_drift = False
        self.lead_drift_timer = 0
        if "lead_drift" in self.sim_alarm_list:
            self.sim_alarm_list.remove("lead_drift")
        self.draw_screen_static()

    # ==================== VF转复系统 ====================

    def attempt_vf_conversion(self, energy):
        base_success_rate = 0.70
        
        if self.vf_is_child:
            base_success_rate = 0.85
        
        if energy < 50:
            success_rate = base_success_rate * 0.6
        elif energy < 100:
            success_rate = base_success_rate * 0.8
        elif energy <= 150:
            success_rate = base_success_rate * 0.95
        elif energy <= 200:
            success_rate = base_success_rate * 1.0
        else:
            success_rate = base_success_rate * 0.9
        
        attempt_factor = 1.0 - (self.vf_conversion_attempts * 0.05)
        if self.vf_conversion_attempts > 0:
            attempt_factor = max(0.7, attempt_factor)
        success_rate = success_rate * attempt_factor
        
        converted = random.random() < success_rate
        
        if converted:
            rhythms = ["normal", "normal", "normal", "窦性心动过缓", "窦性心动过速"]
            new_rhythm = random.choice(rhythms)
            new_hr = random.randint(60, 100)
            return True, new_rhythm, success_rate
        else:
            if random.random() < 0.3:
                new_rhythm = "室速(VT)"
                new_hr = random.randint(120, 200)
            else:
                new_rhythm = self.ecg_rhythm
                new_hr = self.sim_hr
            return False, new_rhythm, success_rate

    # ==================== 能量控制 ====================

    def energy_plus(self):
        if self.self_test_running:
            if hasattr(self, '_key_test_energy_plus') and self._key_test_energy_plus():
                return
        if not self.power_on:
            return
        try:
            if self.mode != "Manual Defib":
                messagebox.showinfo("提示", "仅在Manual Defib模式下可调节能量")
                return
            
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                if not available:
                    return
                current_idx = -1
                for i, e in enumerate(available):
                    if e == self.energy:
                        current_idx = i
                        break
                if current_idx >= 0 and current_idx < len(available) - 1:
                    self.energy = available[current_idx + 1]
                    self.energy_idx = self.energy_levels.index(self.energy)
                    self.refresh_text()
                    self.draw_screen_static()
                    self.event_logger.log_event("操作", f"儿童Manual能量调整为 {self.energy}J")
                else:
                    messagebox.showinfo("提示", f"已达到儿童最高能量 {self.energy}J")
                return
            
            if self.is_charged or self.is_charging:
                self.cancel_charge()
            self.shock_count = 0
            self.energy_idx = (self.energy_idx + 1) % len(self.energy_levels)
            self.energy = self.energy_levels[self.energy_idx]
            self.refresh_text()
            self.event_logger.log_event("操作", f"能量调整为 {self.energy}J")
        except Exception:
            traceback.print_exc()

    def energy_minus(self):
        if self.self_test_running:
            if hasattr(self, '_key_test_energy_minus') and self._key_test_energy_minus():
                return
        if not self.power_on:
            return
        try:
            if self.mode != "Manual Defib":
                messagebox.showinfo("提示", "仅在Manual Defib模式下可调节能量")
                return
            
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                if not available:
                    return
                current_idx = -1
                for i, e in enumerate(available):
                    if e == self.energy:
                        current_idx = i
                        break
                if current_idx > 0:
                    self.energy = available[current_idx - 1]
                    self.energy_idx = self.energy_levels.index(self.energy)
                    self.refresh_text()
                    self.draw_screen_static()
                    self.event_logger.log_event("操作", f"儿童Manual能量调整为 {self.energy}J")
                else:
                    messagebox.showinfo("提示", f"已达到儿童最低能量 {self.energy}J")
                return
            
            if self.is_charged or self.is_charging:
                self.cancel_charge()
            self.shock_count = 0
            self.energy_idx = (self.energy_idx - 1) % len(self.energy_levels)
            self.energy = self.energy_levels[self.energy_idx]
            self.refresh_text()
            self.event_logger.log_event("操作", f"能量调整为 {self.energy}J")
        except Exception:
            traceback.print_exc()

    # ==================== 治疗放电 ====================

    def do_shock_sync(self):
        if self._auto_disarming:
            print("[安全] 自动放电中，禁止手动Shock")
            return

        SHOCKABLE_RHYTHMS = ["室颤(VF)", "室颤(VF儿童)", "室速(VT)", "房颤(AF)"]
        is_shockable = self.ecg_rhythm in SHOCKABLE_RHYTHMS
        
        if not self._is_self_test_mode():
            if not is_shockable:
                print(f"[安全] 当前心律 '{self.ecg_rhythm}' 不适合电击除颤，已阻止放电")
                self.screen_canvas.delete("shock_message")
                self.shock_msg = self.screen_canvas.create_text(
                    self.canvas_w // 2, self.canvas_h // 2,
                    text=f"⚠️ 当前心律 '{self.ecg_rhythm}' 不适合电击！",
                    fill=self.COLOR_RED_ALERT,
                    font=("Arial", 20, "bold"),
                    tags="shock_message"
                )
                self.root.after(2000, lambda: self.screen_canvas.delete("shock_message"))
                return

        if self.is_charged and self.is_charging:
            print("[错误] 非法状态：is_charged 和 is_charging 同时为 True，强制重置")
            self.cancel_charge()
            return
        if self.is_charged and self._auto_disarming:
            print("[安全] 自动放电中，禁止手动 Shock")
            return

        # ===== V11.00: 放电前阻抗二次校验 (安全锁) =====
        current_imp = self.impedance_gen.get_current()
        self.impedance = current_imp  # 同步
        if current_imp > 200:
            self._cancel_charge_due_to_impedance(current_imp, "放电")
            return

        try:
            if not self.power_on or not self.line_connected or not self.is_charged:
                return
            if self.auto_disarm_task:
                self.root.after_cancel(self.auto_disarm_task)
                self.auto_disarm_task = None

            if sound_charged:
                sound_charged.stop()
            if sound_shock:
                sound_shock.play()

            self.stop_shock_flash()

            box_x1 = int(self.canvas_w * 0.09)
            box_y1 = int(self.canvas_h * 0.38)
            box_x2 = int(self.canvas_w * 0.75)
            box_y2 = int(self.canvas_h * 0.62)

            self.screen_canvas.delete("box_content")
            self.screen_canvas.delete("dynamic_imp")
            self.screen_canvas.delete("dynamic_alarm")
            self.screen_canvas.delete("shock_message")
            self.screen_canvas.delete("sync_box")

            self.shock_clear_task = self.root.after(50, lambda: self._show_shock_message(box_x1, box_y1, box_x2, box_y2))

            energy = self.energy
            self.shock_count += 1
            self.total_shocks += 1  # V10.0.0: 统计总电击次数
            
            # ===== V10.0.0: 记录第一次电击时间 =====
            if self.first_shock_timestamp is None:
                self.first_shock_timestamp = self.timer_sec
            
            # 触发除颤动画
            self.ecg_gene.trigger_shock_animation()
            
            # 清除ROSC状态
            self.rosc_active = False
            
            if is_shockable and self.ecg_rhythm in ["室颤(VF)", "室颤(VF儿童)", "室速(VT)"]:
                self.vf_is_child = (self.ecg_rhythm == "室颤(VF儿童)" or self.aed_child_mode)
                self.vf_conversion_attempts += 1
                self.vf_current_energy = energy
                
                if self.vf_conversion_attempts == 1:
                    self.vf_initial_energy = energy
                
                converted, new_rhythm, success_rate = self.attempt_vf_conversion(energy)
                
                if converted:
                    self.ecg_rhythm = new_rhythm
                    self.ecg_gene.set_rhythm(new_rhythm)
                    new_hr = random.randint(60, 100)
                    self.sim_hr = new_hr
                    self.ecg_gene.set_hr(new_hr)
                    self.vf_conversion_attempts = 0
                    
                    # 启动ROSC
                    self.rosc_active = True
                    self.rosc_timer = 0
                    if sound_rosc:
                        sound_rosc.play()
                    
                    # ===== V10.0.0: 记录ROSC时间 =====
                    if self.first_shock_timestamp is not None:
                        self.rosc_time_seconds = self.timer_sec - self.first_shock_timestamp
                    
                    # 生成抢救复盘报告
                    self._generate_code_report(converted=True, energy=energy)
                    
                    self.event_logger.log_event("治疗", f"VF转复成功: {new_rhythm}, HR {new_hr}bpm, 能量{energy}J")
                    print(f"[VF转复] 成功! 能量{energy}J → {new_rhythm}, HR {new_hr}bpm")
                else:
                    self.ecg_rhythm = new_rhythm
                    self.ecg_gene.set_rhythm(new_rhythm)
                    self.ecg_gene.set_hr(self.sim_hr)
                    
                    self.event_logger.log_event("治疗", f"VF转复失败: 仍为{new_rhythm}, 能量{energy}J, 尝试{self.vf_conversion_attempts}次")
                    print(f"[VF转复] 失败! 能量{energy}J, 尝试{self.vf_conversion_attempts}次")
                    
                    if self.aed_child_mode or self.vf_is_child:
                        available = self.get_available_child_energies(self.child_age)
                        if available and self.energy < max(available):
                            next_e = min([e for e in available if e > self.energy], default=self.energy)
                            self.screen_canvas.create_text(
                                self.canvas_w // 2, self.canvas_h // 2 + 80,
                                text=f"⚠️ 建议增加能量至 {next_e}J",
                                fill=self.COLOR_YELLOW,
                                font=("Arial", 14),
                                tags="shock_message"
                            )
                    else:
                        next_energy = min(200, energy * 1.5)
                        next_energy = round(next_energy / 10) * 10
                        self.screen_canvas.create_text(
                            self.canvas_w // 2, self.canvas_h // 2 + 80,
                            text=f"⚠️ 建议增加能量至 {next_energy}J",
                            fill=self.COLOR_YELLOW,
                            font=("Arial", 14),
                            tags="shock_message"
                        )
            else:
                self.event_logger.log_event("治疗", f"电击 {energy}J (Shock #{self.shock_count})")

            self.is_charged = False
            self.shock_enabled = False
            self.charge_btn.config(text="")
            self.charge_progress = 0
            self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x1, self.bar_y2)
            self.screen_canvas.itemconfig(self.charge_tip, text="")

            self.exit_sync_mode(redraw=False)
            self.trigger_post_shock_sequence()
            self.shock_message_task = self.root.after(3000, self.restore_after_shock)

        except Exception:
            traceback.print_exc()

    # ===== V10.0.0: 抢救复盘报告生成 =====
    
    def _generate_code_report(self, converted=True, energy=None):
        """生成抢救复盘报告"""
        report = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_shocks": self.total_shocks,
            "rosc_time_seconds": self.rosc_time_seconds,
            "rosc_time_formatted": f"{self.rosc_time_seconds // 60}分{self.rosc_time_seconds % 60}秒" if self.rosc_time_seconds else "未记录",
            "energy_used": energy,
            "vf_attempts": self.vf_conversion_attempts,
            "rhythm_initial": self.ecg_rhythm,
            "rhythm_final": self.ecg_rhythm if converted else "未转复",
            "patient_age": self.sim_age,
            "patient_gender": self.sim_gender,
            "medications": self.drug_simulator._code_medications if hasattr(self.drug_simulator, '_code_medications') else [],
            "outcome": "ROSC" if converted else "未转复"
        }
        
        # 记录到EventLogger
        self.event_logger.log_code_report(report)
        
        # 显示抢救简报
        self._show_code_report(report)
    
    def _show_code_report(self, report):
        """显示抢救简报"""
        msg = "📋 抢救简报 (Code Summary)\n"
        msg += "=" * 40 + "\n\n"
        msg += f"🕐 时间: {report['timestamp']}\n"
        msg += f"📅 日期: {report['date']}\n\n"
        msg += f"⚡ 总电击次数: {report['total_shocks']}\n"
        msg += f"💊 转复尝试: {report['vf_attempts']} 次\n"
        msg += f"⏱ 首次电击到ROSC: {report['rosc_time_formatted']}\n"
        msg += f"📈 初始心律: {report['rhythm_initial']}\n"
        msg += f"📈 最终心律: {report['rhythm_final']}\n"
        msg += f"👤 患者: {report['patient_gender']} {report['patient_age']}岁\n"
        msg += f"📊 结局: {'✅ ROSC' if report['outcome'] == 'ROSC' else '❌ 未转复'}\n\n"
        
        if report['medications']:
            msg += "💉 用药清单:\n"
            for med in report['medications']:
                msg += f"  • {med['drug']} {med['dose']} {med['route']} @ {med['time']}\n"
        else:
            msg += "💉 用药清单: 无\n"
        
        msg += "\n" + "=" * 40
        msg += "\n📝 复盘建议:\n"
        if report['outcome'] == 'ROSC':
            msg += "✅ 自主循环恢复成功，建议继续监测生命体征\n"
            if report['rosc_time_seconds'] and report['rosc_time_seconds'] > 120:
                msg += "⚠️ 恢复时间较长 (>2分钟)，建议回顾除颤流程\n"
        else:
            msg += "⚠️ 未转复，建议检查:\n"
            msg += "  • 电极片位置是否正确\n"
            msg += "  • 能量是否足够 (建议增加能量)\n"
            msg += "  • 是否给予肾上腺素\n"
        
        messagebox.showinfo("📋 抢救复盘报告", msg)

    def _show_rosc_indicator(self):
        """显示ROSC指示器"""
        if not self.rosc_active:
            return
        
        cw = self.canvas_w
        ch = self.canvas_h
        
        self.rosc_flash_state = not self.rosc_flash_state
        color = self.COLOR_ROSC if self.rosc_flash_state else self.COLOR_YELLOW
        
        x = cw // 2
        y = ch // 2 + 120
        
        self.screen_canvas.delete("rosc_indicator")
        
        self.screen_canvas.create_rectangle(x - 120, y - 25, x + 120, y + 25,
                                           fill="#0a1a2a", outline=color, width=3,
                                           tags="rosc_indicator")
        self.screen_canvas.create_text(x, y,
                                       text="❤️ 自主循环恢复 ROSC ❤️",
                                       fill=color,
                                       font=("Arial", 18, "bold"),
                                       tags="rosc_indicator")
        
        self.rosc_timer += 1
        if self.rosc_timer < 60:
            self.root.after(250, self._show_rosc_indicator)
        else:
            self.rosc_active = False
            self.screen_canvas.delete("rosc_indicator")

    # ==================== 儿童模式切换 ====================

    def toggle_aed_child(self):
        if self._is_in_self_test():
            return
        
        if self.mode not in ["Monitor", "Manual Defib", "AED"]:
            messagebox.showinfo("提示", "请在监护、Manual Defib或AED模式下设置儿童模式")
            return
        
        if not self.aed_child_mode:
            age_str = simpledialog.askstring("儿童年龄", 
                                            "请输入儿童年龄（3-17岁，支持半岁如10.5）:\n\n"
                                            "AHA儿童除颤指南:\n"
                                            "• 首次: 2J/kg\n"
                                            "• 后续: 4J/kg\n"
                                            "• 能量范围: 20-200J\n\n"
                                            "3-6岁: 体重 ≈ 2×年龄+8 kg\n"
                                            "6-12岁: 体重 ≈ 3×年龄+7 kg\n"
                                            "12-17岁: 体重 ≈ 4×年龄+5 kg",
                                            parent=self.root)
            if age_str:
                try:
                    age = float(age_str.replace('，', '.'))
                    if 3.0 <= age <= 17.0:
                        self.aed_child_mode = True
                        self.child_age = age
                        self.vf_is_child = True
                        
                        available = self.get_available_child_energies(age)
                        if available:
                            self.energy = available[0]
                        else:
                            self.energy = 50
                        self.energy_idx = self.energy_levels.index(min(self.energy, max(self.energy_levels)))
                        
                        energy_range = self.get_child_energy_range(age)
                        energy_sequence = self.get_child_energy_sequence(age)
                        weight = self.get_weight(age)
                        
                        self.event_logger.log_event("儿童模式", f"启用: {age}岁, {weight:.1f}kg, 范围{energy_range[0]}-{energy_range[1]}J")
                        
                        msg = (f"年龄: {age} 岁\n"
                               f"体重: ≈{weight:.1f} kg\n"
                               f"能量范围: {energy_range[0]} - {energy_range[1]} J\n"
                               f"可用挡位: {energy_sequence}\n"
                               f"当前能量: {self.energy}J (首次: 2J/kg)\n\n"
                               "📋 AHA除颤流程:\n"
                               "1️⃣ 首次: 2J/kg\n"
                               "2️⃣ 未转复: 4J/kg\n"
                               "3️⃣ 再未转复: 继续4J/kg\n"
                               "⚠️ 最大不超过200J")
                        
                        if self.mode == "AED":
                            msg += "\n\n⚠️ AED模式下能量自动设定，不可调节"
                        
                        messagebox.showinfo("儿童模式 - AHA标准", msg)
                        self.draw_screen_static()
                    else:
                        messagebox.showwarning("错误", "年龄必须在3-17岁之间")
                except ValueError:
                    messagebox.showwarning("错误", "请输入有效数字（如10.5）")
            else:
                messagebox.showwarning("错误", "请输入有效年龄")
        else:
            self.aed_child_mode = False
            self.vf_is_child = False
            self.vf_conversion_attempts = 0
            if self.mode == "Manual Defib":
                self.energy = 200
                self.energy_idx = self.energy_levels.index(200)
            else:
                self.energy = 200
                self.energy_idx = self.energy_levels.index(200)
            self.event_logger.log_event("儿童模式", "切换为成人模式")
            messagebox.showinfo("成人模式", "已切换为成人模式")
            self.draw_screen_static()

    # ==================== 屏幕绘制 ====================

    def draw_screen_static(self):
        self.screen_canvas.delete("all")
        cw = self.canvas_w
        ch = self.canvas_h
        if not self.power_on:
            self.screen_canvas.config(bg=self.COLOR_SCREEN_BG)
            return
        self.screen_canvas.config(bg=self.COLOR_SCREEN_BG)

        self.screen_canvas.create_text(int(cw*0.05), int(ch*0.05),
                                       text=datetime.now().strftime("%H:%M:%S"),
                                       fill="#ccc", font=("Arial",11))
        self.screen_canvas.create_rectangle(int(cw*0.85), int(ch*0.02), int(cw*0.95), int(ch*0.08),
                                            fill=self.COLOR_GREEN)
        self.screen_canvas.create_text(int(cw*0.90), int(ch*0.05), text="BAT", fill="black", font=("Arial",10))

        if self.mode in ["Manual Defib", "AED"]:
            if self.aed_child_mode:
                self.screen_canvas.create_text(int(cw*0.95), int(ch*0.02),
                                               text="CHR",
                                               fill=self.COLOR_YELLOW, font=("Arial",12,"bold"), anchor="ne")
            else:
                self.screen_canvas.create_text(int(cw*0.95), int(ch*0.02),
                                               text="ADU",
                                               fill=self.COLOR_YELLOW, font=("Arial",12,"bold"), anchor="ne")

        mins = self.timer_sec // 60
        secs = self.timer_sec % 60
        self.timer_text = self.screen_canvas.create_text(int(cw*0.05), int(ch*0.92),
                                                         text=f"{mins:02d}:{secs:02d}",
                                                         fill="white", font=("Arial",28,"bold"))

        # ===== V10.0.0: 导联显示 =====
        ii_x1, ii_y1, ii_x2, ii_y2 = int(cw*0.02), int(ch*0.1), int(cw*0.08), int(ch*0.18)
        self.screen_canvas.create_rectangle(ii_x1, ii_y1, ii_x2, ii_y2, fill="#555")
        self.screen_canvas.create_text((ii_x1+ii_x2)//2, (ii_y1+ii_y2)//2, 
                                       text=self.current_lead, fill="white", font=("Arial",20))

        self.ecg_area_y1 = int(ch*0.08)
        self.ecg_area_y2 = int(ch*0.32)
        ecg_x1 = int(cw*0.09)
        ecg_x2 = int(cw*0.75)
        self.screen_canvas.create_rectangle(ecg_x1, self.ecg_area_y1, ecg_x2, self.ecg_area_y2, outline="#444")
        self.ecg_line = self.screen_canvas.create_line(ecg_x1, (self.ecg_area_y1+self.ecg_area_y2)//2,
                                                       ecg_x1, (self.ecg_area_y1+self.ecg_area_y2)//2,
                                                       fill=self.COLOR_GREEN, width=2)
        self.ecg_x1 = ecg_x1
        self.ecg_x2 = ecg_x2

        # ===== V10.0.0: ECG Pause 指示 =====
        if self.ecg_paused:
            pause_color = self.COLOR_YELLOW if (time.time() * 2) % 2 < 1 else self.COLOR_RED_ALERT
            self.screen_canvas.create_text(ecg_x2 - 10, self.ecg_area_y1 + 10,
                                           text="< PAUSED >",
                                           fill=pause_color,
                                           font=("Arial", 10, "bold"),
                                           anchor="ne",
                                           tags="pause_indicator")

        if not self.lead_connected:
            hr_text = "---"
        else:
            hr_text = str(self.sim_hr) if self.sim_hr > 0 else "0"
        self.screen_canvas.create_text(int(cw*0.82), int(ch*0.10), text="ECG", fill="#ccc", font=("Arial",11))
        self.hr_display = self.screen_canvas.create_text(int(cw*0.82), int(ch*0.16), text=hr_text,
                                                         fill="white", font=("Arial",32,"bold"))
        self.screen_canvas.create_text(int(cw*0.88), int(ch*0.11), text="bpm", fill="#ccc", font=("Arial",10))

        spo2_x1 = int(cw*0.78)
        spo2_y1 = int(ch*0.22)
        spo2_x2 = int(cw*0.92)
        spo2_y2 = int(ch*0.38)
        self.screen_canvas.create_rectangle(spo2_x1, spo2_y1, spo2_x2, spo2_y2, outline="#444", fill="#0a1a2a")
        if not self.lead_connected or self.sim_hr == 0:
            spo2_text = "---"
        else:
            spo2_text = str(self.sim_spo2)
        self.spo2_value_text = self.screen_canvas.create_text((spo2_x1+spo2_x2)//2, spo2_y1+int(ch*0.04),
                                                              text=spo2_text, fill=self.COLOR_BLUE,
                                                              font=("Arial",28,"bold"))
        self.screen_canvas.create_text((spo2_x1+spo2_x2)//2, spo2_y2-int(ch*0.02),
                                       text="SPO₂", fill="#ccc", font=("Arial",9))
        self.spo2_area_y1 = spo2_y1 + int(ch*0.10)
        self.spo2_area_y2 = spo2_y2 - int(ch*0.02)
        self.spo2_line = self.screen_canvas.create_line(spo2_x1+5, (self.spo2_area_y1+self.spo2_area_y2)//2,
                                                        spo2_x1+5, (self.spo2_area_y1+self.spo2_area_y2)//2,
                                                        fill=self.COLOR_BLUE, width=2)

        resp_x1 = int(cw*0.78)
        resp_y1 = int(ch*0.40)
        resp_x2 = int(cw*0.92)
        resp_y2 = int(ch*0.56)
        self.screen_canvas.create_rectangle(resp_x1, resp_y1, resp_x2, resp_y2, outline="#444", fill="#0a1a2a")
        if self.show_nibp and self.nibp_result and self.mode == "Monitor":
            self.screen_canvas.create_text((resp_x1+resp_x2)//2, resp_y1+int(ch*0.02),
                                           text="NIBP", fill="#ccc", font=("Arial",9))
            self.nibp_text = self.screen_canvas.create_text((resp_x1+resp_x2)//2, (resp_y1+resp_y2)//2,
                                                            text=self.nibp_result, fill="white",
                                                            font=("Arial",16,"bold"))
        else:
            if self.mode == "Monitor":
                if not self.lead_connected or self.sim_hr == 0:
                    resp_text = "---"
                else:
                    resp_text = f"Resp {self.sim_resp}"
                self.screen_canvas.create_text((resp_x1+resp_x2)//2, resp_y1+int(ch*0.02),
                                               text=resp_text, fill=self.COLOR_RESP, font=("Arial",9))
                self.resp_area_y1 = resp_y1 + int(ch*0.10)
                self.resp_area_y2 = resp_y2 - int(ch*0.02)
                self.resp_line = self.screen_canvas.create_line(resp_x1+5, (self.resp_area_y1+self.resp_area_y2)//2,
                                                                resp_x1+5, (self.resp_area_y1+self.resp_area_y2)//2,
                                                                fill=self.COLOR_RESP, width=2)
            else:
                self.screen_canvas.create_text((resp_x1+resp_x2)//2, (resp_y1+resp_y2)//2,
                                               text="--", fill="#555", font=("Arial",16,"bold"))

        co2_x1 = int(cw*0.78)
        co2_y1 = int(ch*0.58)
        co2_x2 = int(cw*0.92)
        co2_y2 = int(ch*0.72)
        self.screen_canvas.create_rectangle(co2_x1, co2_y1, co2_x2, co2_y2, outline="#444", fill="#0a1a2a")
        if not self.lead_connected or self.sim_hr == 0:
            co2_text = "---"
        else:
            co2_text = str(self.co2_val)
        self.co2_value_text = self.screen_canvas.create_text((co2_x1+co2_x2)//2, co2_y1+int(ch*0.04),
                                                             text=co2_text, fill="white",
                                                             font=("Arial",28,"bold"))
        self.screen_canvas.create_text((co2_x1+co2_x2)//2, co2_y2-int(ch*0.02),
                                       text="kPa", fill="#ccc", font=("Arial",9))

        if self.mode == "Pacer":
            self.draw_pacer_mode(cw, ch)
        elif self.mode == "Manual Defib":
            self.draw_defib_mode(cw, ch, mode_name="Manual")
        elif self.mode == "AED":
            self.draw_aed_mode(cw, ch)

        self.draw_menu_area(cw, ch)
        self.draw_sim_menu_area(cw, ch)
        
        if self.drug_curve_data:
            self.draw_drug_curve()
        
        if self.rosc_active:
            self._show_rosc_indicator()
        
        self.redraw_dynamic_elements()

    def draw_defib_mode(self, cw, ch, mode_name="Manual"):
        box_x1 = int(cw*0.09)
        box_y1 = int(ch*0.38)
        box_x2 = int(cw*0.75)
        box_y2 = int(ch*0.62)
        self.screen_canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill="#f8f8f8")
        
        # ===== V10.0.0: 显示导联信息 =====
        self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.03),
                                       text=f"{mode_name} | 导联: {self.current_lead}", 
                                       fill="#222", font=("Arial",10))
        
        if self.aed_child_mode:
            energy_range = self.get_child_energy_range(self.child_age)
            available = self.get_available_child_energies(self.child_age)
            self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.07),
                                           text=f"👶 {self.child_age:.1f}岁 | 挡位: {available} J",
                                           fill="#0066cc", font=("Arial",11))
            if self.vf_conversion_attempts > 0:
                self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.10),
                                               text=f"⚡ 转复尝试: {self.vf_conversion_attempts}次",
                                               fill="#cc6600", font=("Arial",10))
        
        self.screen_canvas.create_text((box_x1+box_x2)//2, box_y1+int(ch*0.03),
                                       text="Select Energy: (J)", fill="#222", font=("Arial",15,"bold"),
                                       tags="box_content")
        self.energy_text = self.screen_canvas.create_text((box_x1+box_x2)//2, box_y1+int(ch*0.09),
                                                          text=f"{self.energy}", fill=self.COLOR_TEXT_ORANGE,
                                                          font=("Arial",52,"bold"), tags="box_content")

        # ===== V11.31: 阻抗显示在框内右上方，确保不超框 =====
        dot_x = box_x2 - int(cw*0.04)
        dot_y = box_y1 + int(ch*0.04)
        self.imp_dot_x = dot_x
        self.imp_dot_y = dot_y
        self.imp_text_x = dot_x
        self.imp_text_y = dot_y + int(ch*0.032)

        energy_x = (box_x1+box_x2)//2 + int(cw*0.05)
        sync_width = int(cw*0.06)
        sync_height = int(ch*0.04)
        sync_x1 = energy_x + 10
        sync_y1 = box_y1 + int(ch*0.06)
        sync_x2 = sync_x1 + sync_width
        sync_y2 = sync_y1 + sync_height
        if self.sync_mode and self.sync_flash_state:
            self.screen_canvas.create_rectangle(sync_x1, sync_y1, sync_x2, sync_y2,
                                                fill=self.COLOR_GREEN, outline="white", width=1,
                                                tags="sync_box")
            self.screen_canvas.create_text((sync_x1+sync_x2)//2, (sync_y1+sync_y2)//2,
                                           text="同步", fill="white", font=("Arial",10,"bold"),
                                           tags="sync_box")

        self.shock_cnt_text = self.screen_canvas.create_text(box_x2-10, box_y2-30,
                                                             text=f"Energy: {self.energy}J",
                                                             fill="#222", font=("Arial",12), anchor="se",
                                                             tags="box_content")
        self.shock_cnt_text2 = self.screen_canvas.create_text(box_x2-10, box_y2-10,
                                                              text=f"Shocks: {self.shock_count}",
                                                              fill="#222", font=("Arial",12), anchor="se",
                                                              tags="box_content")

        bar_x1 = box_x1 + int(cw*0.15)
        bar_x2 = box_x2 - int(cw*0.15)
        bar_y1 = box_y2 - int(ch*0.06)
        bar_y2 = box_y2 - int(ch*0.04)
        self.bar_bg = self.screen_canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, fill="#aaa", tags="box_content")
        self.bar_fill = self.screen_canvas.create_rectangle(bar_x1, bar_y1, bar_x1, bar_y2, fill=self.COLOR_YELLOW, tags="box_content")
        self.charge_tip = self.screen_canvas.create_text((bar_x1+bar_x2)//2, bar_y2+int(ch*0.015),
                                                         text="", fill="#000", font=("Arial",12,"bold"),
                                                         tags="box_content")
        self.bar_x1, self.bar_x2, self.bar_y1, self.bar_y2 = bar_x1, bar_x2, bar_y1, bar_y2

        sync_x1_btn = int(cw*0.55)
        sync_y1_btn = box_y2 + int(ch*0.01)
        sync_x2_btn = int(cw*0.70)
        sync_y2_btn = sync_y1_btn + int(ch*0.05)
        self.screen_canvas.create_rectangle(sync_x1_btn, sync_y1_btn, sync_x2_btn, sync_y2_btn,
                                            fill=self.COLOR_SYNC if self.sync_mode else self.COLOR_YELLOW)
        sync_text = "Exit Sync" if self.sync_mode else "Enter Sync"
        self.sync_text_id = self.screen_canvas.create_text((sync_x1_btn+sync_x2_btn)//2, (sync_y1_btn+sync_y2_btn)//2,
                                                           text=sync_text, fill="#000", font=("Arial",10))
        self.screen_canvas.tag_bind(self.sync_text_id, "<Button-1>", lambda e: self.toggle_sync_mode())

    def draw_aed_mode(self, cw, ch):
        box_x1 = int(cw*0.09)
        box_y1 = int(ch*0.38)
        box_x2 = int(cw*0.75)
        box_y2 = int(ch*0.62)
        self.screen_canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill="#f8f8f8")
        self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.03),
                                       text=f"AED | 导联: {self.current_lead}", fill="#222", font=("Arial",10))
        
        # ===== V11.31: 阻抗显示在框内右上方 (与Manual Defib一致) =====
        dot_x = box_x2 - int(cw*0.04)
        dot_y = box_y1 + int(ch*0.04)
        self.imp_dot_x = dot_x
        self.imp_dot_y = dot_y
        self.imp_text_x = dot_x
        self.imp_text_y = dot_y + int(ch*0.032)
        
        if self.aed_child_mode:
            energy_range = self.get_child_energy_range(self.child_age)
            available = self.get_available_child_energies(self.child_age)
            self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.07),
                                           text=f"👶 {self.child_age:.1f}岁 | 能量: {self.energy}J",
                                           fill="#0066cc", font=("Arial",11))
            if self.vf_conversion_attempts > 0:
                self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.10),
                                               text=f"⚡ 转复尝试: {self.vf_conversion_attempts}次",
                                               fill="#cc6600", font=("Arial",10))

        if self.aed_analyzing:
            self.screen_canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2,
                                           text="正在分析，请勿接触病人", fill="#000",
                                           font=("Arial", 18, "bold"))
        elif self.aed_analysis_result:
            self.screen_canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2 - int(ch*0.04),
                                           text=self.aed_analysis_result, fill=self.COLOR_RED_ALERT,
                                           font=("Arial", 20, "bold"))
            self.screen_canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2 + int(ch*0.04),
                                           text=f"能量: {self.energy}J", fill="#222",
                                           font=("Arial", 14))
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                self.screen_canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2 + int(ch*0.08),
                                               text=f"自动设定", fill="#666",
                                               font=("Arial", 11))
        else:
            self.screen_canvas.create_text((box_x1+box_x2)//2, (box_y1+box_y2)//2,
                                           text="按 '分析' 键开始分析", fill="#222",
                                           font=("Arial", 16))

        btn_width = int(cw*0.10)
        btn_height = int(ch*0.04)
        btn_x1 = box_x1 + int((box_x2-box_x1)/2) - btn_width//2
        btn_y1 = box_y2 + int(ch*0.01)
        btn_x2 = btn_x1 + btn_width
        btn_y2 = btn_y1 + btn_height

        self.analysis_btn_rect = self.screen_canvas.create_rectangle(btn_x1, btn_y1, btn_x2, btn_y2,
                                                                     fill=self.COLOR_GREEN, tags="analysis_btn")
        self.screen_canvas.create_text((btn_x1+btn_x2)//2, (btn_y1+btn_y2)//2,
                                       text="分析", fill="#000", font=("Arial",12,"bold"), tags="analysis_btn")
        self.screen_canvas.tag_bind("analysis_btn", "<Button-1>", lambda e: self.start_aed_analysis())

    # ==================== 构建UI ====================

    def build_ui(self):
        w, h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        canvas_w = int(w * 0.75)
        canvas_h = int(h * 0.75)
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        main_frame = tk.Frame(self.root, bg=self.COLOR_BODY)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)
        main_frame.columnconfigure(0, weight=3)
        main_frame.columnconfigure(1, weight=1)

        screen_container = tk.Frame(main_frame, bg=self.COLOR_BODY)
        screen_container.grid(row=0, column=0, sticky="nsew", padx=6)

        tk.Label(screen_container, text="mindray", font=("Arial", 30, "bold"),
                 fg="black", bg=self.COLOR_BODY, anchor="w").pack(anchor="nw")

        self.model_label = tk.Label(screen_container, text="BeneHeart D3 v11.31",
                                    font=("Arial", 16), fg="black", bg=self.COLOR_BODY)
        self.model_label.place(x=w*0.70, y=0)

        self.screen_canvas = Canvas(screen_container, width=canvas_w, height=canvas_h,
                                    bg=self.COLOR_SCREEN_BG, highlightthickness=3,
                                    highlightbackground="#555")
        self.screen_canvas.pack(pady=12)
        self.draw_screen_static()

        self.mode_label = tk.Label(screen_container, text="Off", font=("Arial", 18, "bold"),
                                   fg="black", bg=self.COLOR_BODY)
        self.mode_label.place(x=20, y=60)

        softkey_frame = tk.Frame(screen_container, bg=self.COLOR_BODY)
        softkey_frame.pack(fill="x", pady=10)
        soft_btns = [("NIBP", self.soft_nibp), ("Alarm Pause", self.soft_alarm),
                     ("Event", self.soft_event), ("药品库", self.soft_drug_library),
                     ("Menu", self.soft_menu), ("SIM", self.soft_sim),
                     ("ECG Lab", self.soft_ecg_lab)]  # V10.0.0: 新增ECG Lab按钮
        for idx, (txt, cmd) in enumerate(soft_btns):
            tk.Button(softkey_frame, text=txt, font=("Arial", 12), width=14, height=2,
                      bg=self.COLOR_GRAY_LIGHT, fg="black", command=cmd).grid(row=0, column=idx, padx=6)

        nav_knob = Canvas(screen_container, width=140, height=140, bg=self.COLOR_BODY, highlightthickness=0)
        nav_knob.pack(pady=12)
        nav_knob.create_oval(12,12,128,128, fill="#778899", outline="#aaa", width=2)

        panel_container = tk.Frame(main_frame, bg=self.COLOR_BODY)
        panel_container.grid(row=0, column=1, sticky="nsew", padx=6)

        mode_frame = tk.Frame(panel_container, bg=self.COLOR_BODY)
        mode_frame.pack(pady=12)
        self.mode_canvas = Canvas(mode_frame, width=240, height=240, bg=self.COLOR_BODY, highlightthickness=0)
        self.mode_canvas.pack()
        self.draw_mode_knob()
        mode_text_pos = [("Manual Defib", 0, 170), ("监护", 0, 16),
                         ("关", 100, 4), ("起搏", 182, 16), ("AED", 182, 170)]
        for txt, x, y in mode_text_pos:
            tk.Label(mode_frame, text=txt, font=("Arial", 10, "bold"), fg="black", bg=self.COLOR_BODY).place(x=x, y=y)

        energy_ctrl_frame = tk.Frame(panel_container, bg=self.COLOR_BODY)
        energy_ctrl_frame.pack(pady=8)
        tk.Label(energy_ctrl_frame, text="Energy Select", font=("Arial",14,"bold"),
                 fg="black", bg=self.COLOR_BODY).grid(row=0, column=0, columnspan=2, pady=4)
        self.energy_plus_btn = tk.Button(energy_ctrl_frame, text="+", width=4, height=2, font=("Arial",14),
                                         bg=self.COLOR_GRAY_LIGHT, fg="black", command=self.energy_plus)
        self.energy_plus_btn.grid(row=1, column=1, padx=4)
        self.energy_minus_btn = tk.Button(energy_ctrl_frame, text="-", width=4, height=2, font=("Arial",14),
                                          bg=self.COLOR_GRAY_LIGHT, fg="black", command=self.energy_minus)
        self.energy_minus_btn.grid(row=1, column=0, padx=4)

        self.pacer_panel = tk.LabelFrame(panel_container, text="起搏控制", font=("Arial",12,"bold"),
                                         bg=self.COLOR_BODY, fg="black")
        self.pacer_panel.pack_forget()
        
        mode_pacer_frame = tk.Frame(self.pacer_panel, bg=self.COLOR_BODY)
        mode_pacer_frame.pack(pady=5)
        tk.Label(mode_pacer_frame, text="模式:", font=("Arial",11), fg="black", bg=self.COLOR_BODY).pack(side="left", padx=5)
        self.pacer_mode_var = StringVar(value="经皮")
        pacer_modes = ["经皮", "按需"]
        for i, mode in enumerate(pacer_modes):
            tk.Radiobutton(mode_pacer_frame, text=mode, variable=self.pacer_mode_var,
                           value=mode, bg=self.COLOR_BODY, fg="black",
                           selectcolor="#ccc", command=self.update_pacer_mode).pack(side="left", padx=5)

        current_frame = tk.Frame(self.pacer_panel, bg=self.COLOR_BODY)
        current_frame.pack(fill="x", pady=3)
        tk.Label(current_frame, text="电流(mA):", font=("Arial",11), fg="black", bg=self.COLOR_BODY).pack(side="left", padx=5)
        self.pacer_current_scale = Scale(current_frame, from_=0, to=200, orient="horizontal",
                                         length=120, bg=self.COLOR_BODY, fg="black",
                                         troughcolor="#ccc", highlightthickness=0)
        self.pacer_current_scale.set(50)
        self.pacer_current_scale.pack(side="left", padx=5)
        self.pacer_current_label = tk.Label(current_frame, text="50", font=("Arial",11,"bold"),
                                            fg="black", bg=self.COLOR_BODY, width=5)
        self.pacer_current_label.pack(side="left", padx=5)
        self.pacer_current_scale.config(command=lambda v: self.pacer_current_label.config(text=str(int(float(v)))))

        rate_frame = tk.Frame(self.pacer_panel, bg=self.COLOR_BODY)
        rate_frame.pack(fill="x", pady=3)
        tk.Label(rate_frame, text="频率(/min):", font=("Arial",11), fg="black", bg=self.COLOR_BODY).pack(side="left", padx=5)
        self.pacer_rate_scale = Scale(rate_frame, from_=30, to=180, orient="horizontal",
                                      length=120, bg=self.COLOR_BODY, fg="black",
                                      troughcolor="#ccc", highlightthickness=0)
        self.pacer_rate_scale.set(72)
        self.pacer_rate_scale.pack(side="left", padx=5)
        self.pacer_rate_label = tk.Label(rate_frame, text="72", font=("Arial",11,"bold"),
                                         fg="black", bg=self.COLOR_BODY, width=5)
        self.pacer_rate_label.pack(side="left", padx=5)
        self.pacer_rate_scale.config(command=lambda v: self.pacer_rate_label.config(text=str(int(float(v)))))

        pulse_frame = tk.Frame(self.pacer_panel, bg=self.COLOR_BODY)
        pulse_frame.pack(fill="x", pady=3)
        tk.Label(pulse_frame, text="脉宽(ms):", font=("Arial",11), fg="black", bg=self.COLOR_BODY).pack(side="left", padx=5)
        self.pacer_pulse_scale = Scale(pulse_frame, from_=5, to=40, orient="horizontal",
                                       length=120, bg=self.COLOR_BODY, fg="black",
                                       troughcolor="#ccc", highlightthickness=0)
        self.pacer_pulse_scale.set(20)
        self.pacer_pulse_scale.pack(side="left", padx=5)
        self.pacer_pulse_label = tk.Label(pulse_frame, text="20", font=("Arial",11,"bold"),
                                          fg="black", bg=self.COLOR_BODY, width=5)
        self.pacer_pulse_label.pack(side="left", padx=5)
        self.pacer_pulse_scale.config(command=lambda v: self.pacer_pulse_label.config(text=str(int(float(v)))))

        btn_pacer_frame = tk.Frame(self.pacer_panel, bg=self.COLOR_BODY)
        btn_pacer_frame.pack(pady=5)
        self.pacer_btn = tk.Button(btn_pacer_frame, text="启动起搏", width=12,
                                   bg=self.COLOR_GREEN, fg="black",
                                   command=self.toggle_pacer)
        self.pacer_btn.pack(side="left", padx=5)
        self.pacer_status_label = tk.Label(btn_pacer_frame, text="待机", font=("Arial",12,"bold"),
                                           fg="black", bg=self.COLOR_BODY)
        self.pacer_status_label.pack(side="left", padx=10)

        charge_frame = tk.Frame(panel_container, bg=self.COLOR_BODY)
        charge_frame.pack(pady=18)
        tk.Label(charge_frame, text="2 Charge", font=("Arial",16,"bold"), fg="black",
                 bg=self.COLOR_BODY, anchor="w", width=8).grid(row=0, column=0, sticky="w", padx=(0,10))
        self.charge_btn = tk.Button(charge_frame, text="", width=6, height=2,
                                    bg=self.COLOR_YELLOW, command=self.do_charge, state="disabled")
        self.charge_btn.grid(row=0, column=1, padx=10)

        shock_frame = tk.Frame(panel_container, bg=self.COLOR_BODY)
        shock_frame.pack(pady=18)
        tk.Label(shock_frame, text="3 Shock", font=("Arial",16,"bold"), fg="black",
                 bg=self.COLOR_BODY, anchor="w", width=8).grid(row=0, column=0, sticky="w", padx=(0,10))

        self.shock_canvas = Canvas(shock_frame, width=80, height=80, highlightthickness=0, bg=self.COLOR_BODY)
        self.shock_canvas.grid(row=0, column=1, padx=10)
        self.shock_circle = self.shock_canvas.create_oval(5,5,75,75, fill=self.COLOR_ORANGE_BTN, outline='')
        self.shock_text = self.shock_canvas.create_text(40,40, text="⚡", font=("Arial",36), fill="white")
        self.shock_enabled = False

    def draw_mode_knob(self):
        self.mode_canvas.delete("all")
        cx, cy = 120, 120
        radius_outer = 100
        radius_inner = 80

        self.mode_canvas.create_oval(cx-radius_outer, cy-radius_outer,
                                     cx+radius_outer, cy+radius_outer,
                                     fill="#556677", outline="#8899aa", width=3)
        self.mode_canvas.create_oval(cx-radius_inner, cy-radius_inner,
                                     cx+radius_inner, cy+radius_inner,
                                     fill="#3a4a5a", outline="#667788", width=2)

        angle_map = {0: -90, 1: -135, 2: -45, 3: 180, 4: 0}
        dot_radius = 10
        
        for i in range(5):
            angle = angle_map[i]
            rad = math.radians(angle)
            x = cx + radius_inner * math.cos(rad)
            y = cy + radius_inner * math.sin(rad)
            if i == self.mode_idx:
                self.mode_canvas.create_oval(x-dot_radius*1.5, y-dot_radius*1.5,
                                             x+dot_radius*1.5, y+dot_radius*1.5,
                                             fill=self.COLOR_ORANGE_HIGHLIGHT, 
                                             outline="#ffcc44", width=2)
                self.mode_canvas.create_oval(x-3, y-3, x+3, y+3, fill="white")
            else:
                self.mode_canvas.create_oval(x-dot_radius, y-dot_radius,
                                             x+dot_radius, y+dot_radius,
                                             fill="#8899aa", outline="#aabbcc")

        self.mode_canvas.create_oval(cx-15, cy-15, cx+15, cy+15, fill="#2a3a4a", outline="#88aacc", width=2)
        self.mode_canvas.create_text(cx, cy, text="D3", fill="#88ddff", font=("Arial", 12, "bold"))
        
        angle_selected = angle_map[self.mode_idx]
        rad_selected = math.radians(angle_selected)
        bar_start_r = 18
        bar_end_r = radius_inner - 5
        x1 = cx + bar_start_r * math.cos(rad_selected)
        y1 = cy + bar_start_r * math.sin(rad_selected)
        x2 = cx + bar_end_r * math.cos(rad_selected)
        y2 = cy + bar_end_r * math.sin(rad_selected)
        
        bar_width = 6
        perp_x = -math.sin(rad_selected)
        perp_y = math.cos(rad_selected)
        
        points = [
            x1 + bar_width/2 * perp_x, y1 + bar_width/2 * perp_y,
            x2 + bar_width/2 * perp_x, y2 + bar_width/2 * perp_y,
            x2 - bar_width/2 * perp_x, y2 - bar_width/2 * perp_y,
            x1 - bar_width/2 * perp_x, y1 - bar_width/2 * perp_y,
        ]
        self.mode_canvas.create_polygon(points, fill=self.COLOR_ORANGE_HIGHLIGHT, 
                                        outline="#ffcc44", width=1)

    # ==================== 起搏模式 ====================

    def update_pacer_mode(self):
        self.pacer_mode = self.pacer_mode_var.get()
        self.pacer_demand_mode = (self.pacer_mode == "按需")

    def toggle_pacer(self):
        if self.mode != "Pacer":
            messagebox.showinfo("提示", "请先切换到起搏模式")
            return
        if not self.lead_connected:
            messagebox.showinfo("提示", "请先连接心导联")
            return
        self.pacer_active = not self.pacer_active
        if self.pacer_active:
            self.pacer_btn.config(text="停止起搏", bg=self.COLOR_RED_ALERT, fg="white")
            self.pacer_status_label.config(text="起搏中", fg=self.COLOR_GREEN)
            self.pacer_current = self.pacer_current_scale.get()
            self.pacer_rate = self.pacer_rate_scale.get()
            self.pacer_pulse_width = self.pacer_pulse_scale.get()
            self.event_logger.log_event("起搏", f"启动起搏 {self.pacer_current}mA, {self.pacer_rate}/min")
        else:
            self.pacer_btn.config(text="启动起搏", bg=self.COLOR_GREEN, fg="black")
            self.pacer_status_label.config(text="待机", fg="black")
            self.event_logger.log_event("起搏", "停止起搏")

    def draw_pacer_mode(self, cw, ch):
        if self.pacer_active:
            self.pacer_current = self.pacer_current_scale.get()
            self.pacer_rate = self.pacer_rate_scale.get()
            self.pacer_pulse_width = self.pacer_pulse_scale.get()

        box_x1 = int(cw*0.09)
        box_y1 = int(ch*0.38)
        box_x2 = int(cw*0.75)
        box_y2 = int(ch*0.62)
        self.screen_canvas.create_rectangle(box_x1, box_y1, box_x2, box_y2, fill="#f8f8f8")
        self.screen_canvas.create_text(box_x1+int(cw*0.04), box_y1+int(ch*0.03),
                                       text=f"起搏 | 导联: {self.current_lead}", fill="#222", font=("Arial",11,"bold"))
        
        status = "起搏中" if self.pacer_active else "待机"
        status_color = self.COLOR_GREEN if self.pacer_active else "#888"
        self.screen_canvas.create_text((box_x1+box_x2)//2, box_y1+int(ch*0.05),
                                       text=f"状态: {status}", fill=status_color, font=("Arial",16,"bold"))
        
        params = [
            (f"模式: {self.pacer_mode}", box_x1+int(cw*0.05), box_y1+int(ch*0.12)),
            (f"电流: {self.pacer_current} mA", box_x1+int(cw*0.05), box_y1+int(ch*0.18)),
            (f"频率: {self.pacer_rate} /min", box_x1+int(cw*0.05), box_y1+int(ch*0.24)),
            (f"脉宽: {self.pacer_pulse_width} ms", box_x1+int(cw*0.05), box_y1+int(ch*0.30)),
        ]
        for text, x, y in params:
            self.screen_canvas.create_text(x, y, text=text, fill="#222", font=("Arial",14), anchor="w")
        
        if self.pacer_active:
            color = self.COLOR_GREEN if (time.time()*2) % 2 < 1 else self.COLOR_YELLOW
            self.screen_canvas.create_oval(box_x2-40, box_y1+int(ch*0.02), 
                                          box_x2-10, box_y1+int(ch*0.08), 
                                          fill=color, outline="")
            self.screen_canvas.create_text((box_x2-25), box_y1+int(ch*0.10),
                                          text="PACING", fill="#222", font=("Arial",9,"bold"))
        
        wave_y = box_y1 + int(ch*0.40)
        wave_x1 = box_x1 + int(cw*0.05)
        wave_x2 = box_x2 - int(cw*0.05)
        self.screen_canvas.create_line(wave_x1, wave_y, wave_x2, wave_y, fill="#888", width=1)
        
        if self.pacer_active:
            num_pulses = 8
            spacing = (wave_x2 - wave_x1) / num_pulses
            for i in range(num_pulses):
                x = wave_x1 + i * spacing + spacing/2
                self.screen_canvas.create_line(x-3, wave_y-12, x, wave_y-20, fill=self.COLOR_PACER, width=2)
                self.screen_canvas.create_line(x, wave_y-20, x+3, wave_y-12, fill=self.COLOR_PACER, width=2)
                self.screen_canvas.create_line(x-8, wave_y, x-4, wave_y-8, fill=self.COLOR_GREEN, width=1.5)
                self.screen_canvas.create_line(x-4, wave_y-8, x, wave_y-18, fill=self.COLOR_GREEN, width=1.5)
                self.screen_canvas.create_line(x, wave_y-18, x+4, wave_y-8, fill=self.COLOR_GREEN, width=1.5)
                self.screen_canvas.create_line(x+4, wave_y-8, x+8, wave_y, fill=self.COLOR_GREEN, width=1.5)
        else:
            self.screen_canvas.create_text((wave_x1+wave_x2)//2, wave_y,
                                          text="-- 起搏待机 --", fill="#888", font=("Arial",14))

    # ==================== 软按键 ====================

    def soft_nibp(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_nibp') and self._key_test_nibp():
                return
        if self._is_in_self_test():
            return
        if not self.power_on or self.mode != "Monitor":
            return
        self.show_nibp = True
        sys = random.randint(110, 140)
        dia = random.randint(60, 90)
        mean = random.randint(75, 100)
        self.nibp_result = f"{sys}/{dia}({mean})"
        self.event_logger.log_event("操作", f"NIBP测量: {self.nibp_result}")
        self.draw_screen_static()

    def soft_alarm(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_alarm') and self._key_test_alarm():
                return
        if self._is_in_self_test():
            return
        if not self.power_on:
            return
        self.alarm_active = False
        self.lead_alarm = False
        self.sim_alarm_list = []
        # V10.0.0: 清除导联干扰
        self.clear_lead_drift()
        self.screen_canvas.delete("dynamic_alarm")
        self.screen_canvas.delete("sim_alarm")
        self.event_logger.log_event("操作", "报警暂停")
        self.draw_screen_static()

    def soft_menu(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_menu') and self._key_test_menu():
                return
        if self._is_in_self_test():
            return
        if not self.power_on:
            return
        self.menu_open = not self.menu_open
        if self.menu_open:
            self.menu_selection = 0
            self.menu_scroll_offset = 0
        self.draw_screen_static()

    def soft_sim(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_sim') and self._key_test_sim():
                return
        if self._is_in_self_test():
            return
        if not self.power_on:
            return
        if self.menu_open:
            self.menu_open = False
        self.sim_menu_open = not self.sim_menu_open
        if self.sim_menu_open:
            self.sim_menu_selection = 0
        self.draw_screen_static()

    # ==================== V11.00: 电极操作 ====================
    def _sim_electrode_attach(self):
        """模拟贴上电极片: 阻抗回归正常"""
        self.impedance_gen.simulate_pad_attach()
        self.impedance = self.impedance_gen.get_current()
        self._impedance_warning_shown = False
        self.impedance_high_warning = False
        self.screen_canvas.delete("impedance_critical")
        self.event_logger.log_impedance_event(
            "电极操作", "贴上新电极片，阻抗恢复正常",
            self.impedance
        )
        self.sim_menu_open = False
        self.draw_screen_static()
        print(f"[电极操作] 贴上电极片，阻抗恢复至 {self.impedance:.0f}Ω")

    def _sim_electrode_detach(self):
        """模拟拔掉电极片: 阻抗跳到999Ω"""
        self.impedance_gen.simulate_pad_detach()
        self.impedance = self.impedance_gen.get_current()
        self._show_impedance_critical_warning()
        self.event_logger.log_impedance_event(
            "电极操作", "电极片脱落，阻抗升至999Ω",
            self.impedance
        )
        self.sim_menu_open = False
        self.draw_screen_static()
        print(f"[电极操作] 拔掉电极片，阻抗跳至 {self.impedance:.0f}Ω")

    def _sim_electrode_press(self):
        """模拟用力按压电极: 阻抗临时降低"""
        success = self.impedance_gen.simulate_press_electrode()
        self.impedance = self.impedance_gen.get_current()
        if success:
            self._impedance_warning_shown = False
            self.impedance_high_warning = False
            self.screen_canvas.delete("impedance_critical")
            self.event_logger.log_impedance_event(
                "电极操作", "用力按压电极，阻抗暂时降低",
                self.impedance
            )
            self.sim_menu_open = False
            self.draw_screen_static()
            print(f"[电极操作] 按压电极，阻抗降至 {self.impedance:.0f}Ω，持续{self.impedance_gen.press_duration:.0f}秒")
        else:
            print("[电极操作] 电极已脱落，按压无效")

    def _sim_electrode_trigger_poor(self):
        """手动触发接触不良"""
        self.impedance_gen.trigger_poor_contact()
        self.impedance = self.impedance_gen.get_current()
        self.event_logger.log_impedance_event(
            "电极操作", f"触发接触不良，阻抗升至{self.impedance:.0f}Ω",
            self.impedance
        )
        self.sim_menu_open = False
        self.draw_screen_static()
        print(f"[电极操作] 触发接触不良，阻抗跳至 {self.impedance:.0f}Ω")

    def soft_event(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_event') and self._key_test_event():
                return
        if self._is_in_self_test():
            return
        if self.event_win_open:
            return
        self.event_win_open = True
        event_win = Toplevel(self.root)
        event_win.title("Event - 事件记录与自检回顾")
        event_win.geometry("700x650")
        event_win.configure(bg="#2a3a4a")
        event_win.grab_set()
        Label(event_win, text="📋 Event 事件中心", font=("Arial", 18, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=5)
        
        # 标签页
        notebook = ttk.Notebook(event_win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 事件记录页
        events_frame = Frame(notebook, bg="#2a3a4a")
        notebook.add(events_frame, text="📝 事件记录")
        
        # 自检回顾页
        test_frame = Frame(notebook, bg="#2a3a4a")
        notebook.add(test_frame, text="🔬 自检回顾")
        
        # ===== V10.0.0: 抢救简报页 =====
        code_frame = Frame(notebook, bg="#2a3a4a")
        notebook.add(code_frame, text="📋 抢救简报")
        
        # 事件记录内容
        canvas_frame = Frame(events_frame, bg="#2a3a4a")
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        canvas = Canvas(canvas_frame, bg="#2a3a4a", highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#2a3a4a")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def show_events():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            Label(scrollable_frame, text="📝 事件记录", font=("Arial", 16, "bold"),
                  fg=self.COLOR_GREEN, bg="#2a3a4a").pack(pady=5)
            events = self.event_logger.get_events()
            if not events:
                Label(scrollable_frame, text="暂无事件记录", fg="#888", bg="#2a3a4a",
                      font=("Arial", 14)).pack(pady=20)
                return
            for evt in reversed(events[-50:]):
                frame = Frame(scrollable_frame, bg="#1a2a3a", relief="ridge", bd=1)
                frame.pack(fill="x", pady=2, padx=5)
                time_label = Label(frame, text=f"[{evt['timestamp']}]", fg="#888",
                                  bg="#1a2a3a", font=("Arial", 9))
                time_label.pack(side="left", padx=3)
                type_label = Label(frame, text=f"{evt['type']}", fg=self.COLOR_YELLOW,
                                  bg="#1a2a3a", font=("Arial", 9, "bold"))
                type_label.pack(side="left", padx=3)
                desc_label = Label(frame, text=evt['description'], fg="white",
                                  bg="#1a2a3a", font=("Arial", 9))
                desc_label.pack(side="left", padx=3)
        
        def show_test_history():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            Label(scrollable_frame, text="🔬 自检历史回顾", font=("Arial", 16, "bold"),
                  fg=self.COLOR_GREEN, bg="#2a3a4a").pack(pady=5)
            history = self.event_logger.get_test_history()
            if not history:
                Label(scrollable_frame, text="暂无自检记录", fg="#888", bg="#2a3a4a",
                      font=("Arial", 14)).pack(pady=20)
                return
            for test in reversed(history[-50:]):
                frame = Frame(scrollable_frame, bg="#1a2a3a", relief="ridge", bd=1)
                frame.pack(fill="x", pady=2, padx=5)
                time_label = Label(frame, text=f"[{test['timestamp']}]", fg="#888",
                                  bg="#1a2a3a", font=("Arial", 9))
                time_label.pack(side="left", padx=3)
                type_label = Label(frame, text=f"{test['test_type']}", 
                                  fg=self.COLOR_YELLOW, bg="#1a2a3a", font=("Arial", 9, "bold"))
                type_label.pack(side="left", padx=3)
                name_label = Label(frame, text=f"{test['test_name']}", fg="white",
                                  bg="#1a2a3a", font=("Arial", 9))
                name_label.pack(side="left", padx=3)
                result_color = self.COLOR_GREEN if test['result'] == "通过" else self.COLOR_RED_ALERT
                result_label = Label(frame, text=f"{test['result']}", fg=result_color,
                                    bg="#1a2a3a", font=("Arial", 9, "bold"))
                result_label.pack(side="left", padx=5)
        
        # ===== V10.0.0: 抢救简报 =====
        def show_code_reports():
            for widget in code_frame.winfo_children():
                if widget != notebook:
                    widget.destroy()
            Label(code_frame, text="📋 抢救简报 (Code Summary)", font=("Arial", 16, "bold"),
                  fg=self.COLOR_GREEN, bg="#2a3a4a").pack(pady=5)
            
            reports = self.event_logger.get_code_reports()
            if not reports:
                Label(code_frame, text="暂无抢救记录", fg="#888", bg="#2a3a4a",
                      font=("Arial", 14)).pack(pady=20)
                return
            
            # 统计摘要
            total_codes = len(reports)
            rosc_count = sum(1 for r in reports if r.get('report', {}).get('outcome') == 'ROSC')
            
            summary_frame = Frame(code_frame, bg="#1a2a3a", relief="ridge", bd=2)
            summary_frame.pack(fill="x", pady=10, padx=10)
            Label(summary_frame, text=f"📊 统计: 总抢救 {total_codes} 次 | ROSC {rosc_count} 次 ({rosc_count/total_codes*100:.0f}%)",
                  fg=self.COLOR_YELLOW, bg="#1a2a3a", font=("Arial", 12, "bold")).pack(pady=5)
            
            # 详细报告列表
            for rep in reversed(reports):
                report = rep.get('report', {})
                frame = Frame(code_frame, bg="#1a2a3a", relief="ridge", bd=1)
                frame.pack(fill="x", pady=3, padx=10)
                
                # 标题
                outcome_color = self.COLOR_GREEN if report.get('outcome') == 'ROSC' else self.COLOR_RED_ALERT
                Label(frame, text=f"[{rep['timestamp']}] {report.get('rhythm_initial', 'N/A')} → {report.get('rhythm_final', 'N/A')}",
                      fg=self.COLOR_YELLOW, bg="#1a2a3a", font=("Arial", 10, "bold")).pack(anchor="w", padx=5)
                
                detail_text = (f"⚡ {report.get('total_shocks', 0)}次电击 | "
                              f"⏱ ROSC: {report.get('rosc_time_formatted', 'N/A')} | "
                              f"💊 {len(report.get('medications', []))}种药物 | "
                              f"📊 {report.get('outcome', 'N/A')}")
                Label(frame, text=detail_text, fg="#ccc", bg="#1a2a3a", 
                      font=("Arial", 9)).pack(anchor="w", padx=5, pady=2)
                
                # 查看详情按钮
                Button(frame, text="查看详情", font=("Arial", 8),
                       bg=self.COLOR_BLUE, fg="black",
                       command=lambda r=report: self._show_report_detail(r)).pack(anchor="e", padx=5, pady=2)
        
        # 切换标签页时更新内容
        notebook.bind("<<NotebookTabChanged>>", lambda e: {
            0: show_events,
            1: show_test_history,
            2: show_code_reports
        }[notebook.index(notebook.select())]())
        
        # 初始显示
        show_events()
        show_test_history()
        show_code_reports()
        
        def on_close_event():
            self.event_win_open = False
            event_win.destroy()
        event_win.protocol("WM_DELETE_WINDOW", on_close_event)
    
    def _show_report_detail(self, report):
        """显示单份抢救简报详情"""
        msg = "📋 抢救简报详情\n"
        msg += "=" * 40 + "\n\n"
        msg += f"🕐 时间: {report.get('timestamp', 'N/A')}\n"
        msg += f"📅 日期: {report.get('date', 'N/A')}\n\n"
        msg += f"⚡ 总电击次数: {report.get('total_shocks', 0)}\n"
        msg += f"💊 转复尝试: {report.get('vf_attempts', 0)} 次\n"
        msg += f"⏱ 首次电击到ROSC: {report.get('rosc_time_formatted', 'N/A')}\n"
        msg += f"📈 初始心律: {report.get('rhythm_initial', 'N/A')}\n"
        msg += f"📈 最终心律: {report.get('rhythm_final', 'N/A')}\n"
        msg += f"👤 患者: {report.get('patient_gender', 'N/A')} {report.get('patient_age', 'N/A')}岁\n"
        msg += f"📊 结局: {'✅ ROSC' if report.get('outcome') == 'ROSC' else '❌ 未转复'}\n\n"
        
        meds = report.get('medications', [])
        if meds:
            msg += "💉 用药清单:\n"
            for med in meds:
                msg += f"  • {med['drug']} {med['dose']} {med['route']} @ {med['time']}\n"
        else:
            msg += "💉 用药清单: 无\n"
        
        msg += "\n" + "=" * 40
        msg += "\n📝 复盘建议:\n"
        if report.get('outcome') == 'ROSC':
            msg += "✅ 自主循环恢复成功，建议继续监测生命体征\n"
            rosc_time = report.get('rosc_time_seconds', 0)
            if rosc_time and rosc_time > 120:
                msg += "⚠️ 恢复时间较长 (>2分钟)，建议回顾除颤流程\n"
        else:
            msg += "⚠️ 未转复，建议检查:\n"
            msg += "  • 电极片位置是否正确\n"
            msg += "  • 能量是否足够 (建议增加能量)\n"
            msg += "  • 是否给予肾上腺素\n"
        
        messagebox.showinfo("📋 抢救简报详情", msg)

    # ==================== V10.0.0: ECG Lab 软按键 ====================
    
    def soft_ecg_lab(self):
        """打开ECG Lab工作台"""
        if self._is_key_test_active():
            return
        if self._is_in_self_test():
            return
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        
        try:
            ecg_lab = ECG_Lab_TK(self.root, self)
            self.event_logger.log_event("操作", "打开ECG Lab")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("错误", f"无法打开ECG Lab: {e}")

    # ==================== 药品库软按键 ====================

    def soft_drug_library(self):
        if self._is_key_test_active():
            if hasattr(self, '_key_test_drug') and self._key_test_drug():
                return
        if self._is_in_self_test():
            return
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        
        if self.drug_library_ui is None:
            self.drug_library_ui = DrugLibraryUI(self.root, self)
            self.drug_library_ui.set_simulator(self.drug_simulator)
        
        self.drug_library_ui.open()
        self.event_logger.log_event("操作", "打开药品库")

    # ==================== 菜单和SIM菜单 (V10.1.3: 优化监护模式菜单布局) ====================

    def draw_menu_area(self, cw, ch):
        if not self.menu_open:
            return
        ITEM_HEIGHT = 28  # 固定每项高度
        menu_width = int(cw*0.42)
        menu_x1 = (cw - menu_width) // 2
        menu_y1 = int(ch*0.72)
        menu_x2 = menu_x1 + menu_width
        menu_y2 = int(ch*0.92)
        menu_h = menu_y2 - menu_y1
        
        self.screen_canvas.create_rectangle(menu_x1, menu_y1, menu_x2, menu_y2,
                                            outline=self.COLOR_YELLOW, fill="#0a1a2a",
                                            tags="menu_area")
        self.screen_canvas.create_text((menu_x1+menu_x2)//2, menu_y1 - int(ch*0.02),
                                       text="=== Menu (滚轮滚动) ===",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 12, "bold"),
                                       tags="menu_area")
        
        if self.mode == "Monitor":
            if self.self_test_running and self.is_auto_self_test:
                self.menu_options = [
                    ("🔒 心导联(自检中)", None, True),
                    ("🔒 治疗线路(自检中)", None, True),
                    ("自检进行中...", None, True)
                ]
            else:
                lead_status = "已连接" if self.lead_connected else "未连接"
                line_status = "已连接" if self.line_connected else "未连接"
                pause_status = "冻结" if self.ecg_paused else "运行"
                child_status = "👶儿童" if self.aed_child_mode else "👤成人"
                prob_text = f"{self.ecg_load_fault_prob:.2f}"
                
                self.menu_options = [
                    (f"心导联: {lead_status} [点击切换]", self.toggle_lead, False),
                    (f"治疗线路: {line_status} [点击切换]", self.toggle_line, False),
                    ("全自动自检", self.start_auto_self_test, False),
                    ("用户检测", self.start_user_test, False),
                    (f"导联: {self.current_lead} [点击切换]", self.cycle_lead, False),
                    (f"波形暂停: {pause_status} [点击切换]", self.toggle_ecg_pause, False),
                    (f"成人/儿童: {child_status} [点击切换]", self.toggle_aed_child, False),
                    (f"ECG LOAD故障概率: {prob_text} [点击设置]", self.open_ecg_fault_setting, False),
                ]
        elif self.mode == "AED":
            pads_status = "已连接" if self.aed_pads_connected else "未连接"
            child_status = "👶儿童" if self.aed_child_mode else "👤成人"
            self.menu_options = [
                (f"AED电极片: {pads_status} [点击切换]", self.toggle_aed_pads, False),
                (f"成人/儿童: {child_status} [点击切换]", self.toggle_aed_child, False),
                (f"导联: {self.current_lead} [点击切换]", self.cycle_lead, False),
            ]
        elif self.mode == "Manual Defib":
            child_status = "👶儿童" if self.aed_child_mode else "👤成人"
            self.menu_options = [
                (f"导联: {self.current_lead} [点击切换]", self.cycle_lead, False),
                (f"成人/儿童: {child_status} [点击切换]", self.toggle_aed_child, False),
            ]
        elif self.mode == "Pacer":
            self.menu_options = [
                (f"导联: {self.current_lead} [点击切换]", self.cycle_lead, False),
            ]
        else:
            self.menu_options = [("请切换到监护或AED模式", None, True)]
        
        # 计算可见项数
        visible_items = max(1, menu_h // ITEM_HEIGHT)
        total_items = len(self.menu_options)
        
        # 限制滚动偏移
        max_offset = max(0, total_items - visible_items)
        if self.menu_scroll_offset > max_offset:
            self.menu_scroll_offset = max_offset
        if self.menu_scroll_offset < 0:
            self.menu_scroll_offset = 0
        
        if self.menu_selection >= total_items:
            self.menu_selection = 0
        
        # 确保选中项可见
        if self.menu_selection < self.menu_scroll_offset:
            self.menu_scroll_offset = self.menu_selection
        elif self.menu_selection >= self.menu_scroll_offset + visible_items:
            self.menu_scroll_offset = self.menu_selection - visible_items + 1
        
        # 绘制可见菜单项
        for i in range(self.menu_scroll_offset, min(self.menu_scroll_offset + visible_items, total_items)):
            text, cmd, disabled = self.menu_options[i]
            visible_idx = i - self.menu_scroll_offset
            y_pos = menu_y1 + visible_idx * ITEM_HEIGHT + ITEM_HEIGHT // 2
            color = "#888" if disabled else (self.COLOR_YELLOW if i == self.menu_selection else "#aaa")
            font_weight = "bold" if i == self.menu_selection else "normal"
            if i == self.menu_selection and not disabled:
                self.screen_canvas.create_rectangle(menu_x1 + 5, y_pos - ITEM_HEIGHT//2 + 3,
                                                   menu_x2 - 15, y_pos + ITEM_HEIGHT//2 - 3,
                                                   fill="#2a4a2a", outline=self.COLOR_GREEN,
                                                   tags="menu_highlight")
            self.screen_canvas.create_text((menu_x1+menu_x2)//2, y_pos,
                                           text=text, fill=color,
                                           font=("Arial", 10, font_weight),
                                           tags=f"menu_item_{i}")
        
        # 绘制滚动条
        if total_items > visible_items:
            scrollbar_x = menu_x2 - 8
            scroll_track_y1 = menu_y1 + 2
            scroll_track_y2 = menu_y2 - 2
            self.screen_canvas.create_rectangle(scrollbar_x - 4, scroll_track_y1, scrollbar_x + 4, scroll_track_y2,
                                                outline="#555", fill="#1a1a2a", tags="menu_area")
            thumb_h = max(15, (visible_items / total_items) * (scroll_track_y2 - scroll_track_y1))
            thumb_y = scroll_track_y1 + (self.menu_scroll_offset / max_offset) * (scroll_track_y2 - scroll_track_y1 - thumb_h) if max_offset > 0 else scroll_track_y1
            self.screen_canvas.create_rectangle(scrollbar_x - 4, thumb_y, scrollbar_x + 4, thumb_y + thumb_h,
                                                outline=self.COLOR_YELLOW, fill="#4a4a2a", tags="menu_area")
        
        self.screen_canvas.bind("<MouseWheel>", self.menu_scroll)
        self.screen_canvas.bind("<Button-1>", self.menu_click_handler)
        self.screen_canvas.bind("<Button-4>", self.menu_scroll)
        self.screen_canvas.bind("<Button-5>", self.menu_scroll)
        self.menu_x1, self.menu_y1, self.menu_x2, self.menu_y2 = menu_x1, menu_y1, menu_x2, menu_y2
        self.menu_item_height = ITEM_HEIGHT
        self.menu_visible_items = visible_items

    def menu_scroll(self, event):
        if not self.menu_open:
            return
        total_items = len(self.menu_options)
        visible_items = getattr(self, 'menu_visible_items', total_items)
        if event.delta > 0 or (hasattr(event, 'num') and event.num == 4):
            self.menu_selection = (self.menu_selection - 1) % total_items
        else:
            self.menu_selection = (self.menu_selection + 1) % total_items
        self.draw_screen_static()

    def menu_click_handler(self, event):
        if not self.menu_open:
            return
        if not hasattr(self, 'menu_y1') or not hasattr(self, 'menu_y2'):
            return
        x, y = event.x, event.y
        if not (self.menu_x1 <= x <= self.menu_x2 and self.menu_y1 <= y <= self.menu_y2):
            return
        item_height = getattr(self, 'menu_item_height', (self.menu_y2 - self.menu_y1) / len(self.menu_options))
        visible_idx = int((y - self.menu_y1) // item_height)
        idx = visible_idx + self.menu_scroll_offset
        if idx < 0 or idx >= len(self.menu_options):
            return
        text, cmd, disabled = self.menu_options[idx]
        if disabled or cmd is None:
            return
        if cmd:
            cmd()
        self.draw_screen_static()

    def draw_sim_menu_area(self, cw, ch):
        if not self.sim_menu_open:
            return
        menu_width = int(cw*0.35)
        menu_x1 = (cw - menu_width) // 2
        menu_y1 = int(ch*0.75)
        menu_x2 = menu_x1 + menu_width
        menu_y2 = int(ch*0.92)
        self.screen_canvas.create_rectangle(menu_x1, menu_y1, menu_x2, menu_y2,
                                            outline=self.COLOR_BLUE, fill="#0a1a2a",
                                            tags="sim_menu_area")
        self.screen_canvas.create_text((menu_x1+menu_x2)//2, menu_y1 - int(ch*0.02),
                                       text="=== SIM 模式选择 (滚轮选择) ===",
                                       fill=self.COLOR_BLUE,
                                       font=("Arial", 12, "bold"),
                                       tags="sim_menu_area")
        self.sim_menu_options = [
            ("⚡ 一键模拟 — 选病种，参数全自动设置", self._open_one_click_sim, False),
            ("⚙ 自定义 — 信息+病种+参数均手动", self._open_sim_window, False),
            ("", None, True),  # 分隔线
            ("🔌 贴电极片 — 阻抗回归正常", self._sim_electrode_attach, False),
            ("🔌 拔电极片 — 阻抗跳至999Ω", self._sim_electrode_detach, False),
            ("🖐 按压电极 — 临时降低阻抗", self._sim_electrode_press, False),
            ("⚠ 触发接触不良 — 阻抗骤升", self._sim_electrode_trigger_poor, False),
        ]
        if self.sim_menu_selection >= len(self.sim_menu_options):
            self.sim_menu_selection = 0
        option_height = (menu_y2 - menu_y1) / len(self.sim_menu_options)
        for i, (text, cmd, disabled) in enumerate(self.sim_menu_options):
            y_pos = menu_y1 + option_height * i + option_height // 2
            
            # 分隔线渲染
            if not text and disabled:
                self.screen_canvas.create_line(menu_x1 + 15, y_pos, menu_x2 - 15, y_pos,
                                               fill="#555", width=1, tags="sim_menu_area")
                continue
            
            color = "#888" if disabled else (self.COLOR_BLUE if i == self.sim_menu_selection else "#aaa")
            font_weight = "bold" if i == self.sim_menu_selection else "normal"
            if i == self.sim_menu_selection and not disabled:
                self.screen_canvas.create_rectangle(menu_x1 + 5, y_pos - option_height//2 + 3,
                                                   menu_x2 - 5, y_pos + option_height//2 - 3,
                                                   fill="#0a2a4a", outline=self.COLOR_BLUE,
                                                   tags="sim_menu_highlight")
            self.screen_canvas.create_text((menu_x1+menu_x2)//2, y_pos,
                                           text=text, fill=color,
                                           font=("Arial", 11, font_weight),
                                           tags=f"sim_menu_item_{i}")
        self.screen_canvas.bind("<MouseWheel>", self.sim_menu_scroll)
        self.screen_canvas.bind("<Button-1>", self.sim_menu_click_handler)
        self.screen_canvas.bind("<Button-4>", self.sim_menu_scroll)
        self.screen_canvas.bind("<Button-5>", self.sim_menu_scroll)
        self.sim_menu_x1, self.sim_menu_y1, self.sim_menu_x2, self.sim_menu_y2 = menu_x1, menu_y1, menu_x2, menu_y2
        self.sim_menu_option_height = option_height

    def sim_menu_scroll(self, event):
        if not self.sim_menu_open:
            return
        direction = -1 if (event.delta > 0 or (hasattr(event, 'num') and event.num == 4)) else 1
        n = len(self.sim_menu_options)
        for _ in range(n):
            self.sim_menu_selection = (self.sim_menu_selection + direction) % n
            _, _, disabled = self.sim_menu_options[self.sim_menu_selection]
            if not disabled:
                break
        self.draw_sim_menu_area(self.canvas_w, self.canvas_h)

    def sim_menu_click_handler(self, event):
        if not self.sim_menu_open:
            return
        if not hasattr(self, 'sim_menu_y1') or not hasattr(self, 'sim_menu_y2'):
            return
        x, y = event.x, event.y
        if not (self.sim_menu_x1 <= x <= self.sim_menu_x2 and self.sim_menu_y1 <= y <= self.sim_menu_y2):
            return
        option_height = (self.sim_menu_y2 - self.sim_menu_y1) / len(self.sim_menu_options)
        idx = int((y - self.sim_menu_y1) // option_height)
        if idx < 0 or idx >= len(self.sim_menu_options):
            return
        text, cmd, disabled = self.sim_menu_options[idx]
        if disabled:
            return
        self.sim_menu_open = False
        self.draw_screen_static()
        if cmd:
            cmd()

    # ==================== 一键模拟 ====================

    def _open_one_click_sim(self):
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        sim_win = Toplevel(self.root)
        sim_win.title("一键模拟 — 选病种即可")
        sim_win.geometry("600x550")
        sim_win.configure(bg="#0a1a2a")
        sim_win.grab_set()
        main_frame = Frame(sim_win, bg="#0a1a2a")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        Label(main_frame, text="⚡ 一键模拟", font=("Arial", 20, "bold"),
              fg=self.COLOR_BLUE, bg="#0a1a2a").pack(pady=10)
        Label(main_frame, text="选择病种，参数自动填充", font=("Arial", 12),
              fg="#aaa", bg="#0a1a2a").pack(pady=3)
        canvas_frame = Frame(main_frame, bg="#0a1a2a")
        canvas_frame.pack(fill="both", expand=True, pady=10)
        canvas = Canvas(canvas_frame, bg="#0a1a2a", highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#0a1a2a")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        one_click_presets = [
            ("正常窦性心律", "normal", 72, 98, 16, 120, 80, "男", 45, [], []),
            ("心肌缺血", "心肌缺血", 85, 96, 16, 130, 80, "男", 55, ["高血压", "冠心病"], ["吸烟"]),
            ("心梗(STEMI)", "心肌梗死(STEMI)", 100, 94, 18, 140, 85, "男", 60, ["高血压", "冠心病", "糖尿病"], ["吸烟", "高血压史"]),
            ("心梗(NSTEMI)", "心肌梗死(NSTEMI)", 95, 92, 18, 135, 82, "男", 58, ["高血压", "冠心病"], ["吸烟", "高血脂"]),
            ("成人室颤(VF)", "室颤(VF)", 280, 88, 10, 80, 50, "男", 55, ["冠心病", "心力衰竭"], ["心脏手术"]),
            ("儿童室颤(VF)", "室颤(VF儿童)", 220, 85, 12, 85, 55, "男", 8, ["先天性心脏病"], []),
            ("房颤(AF)", "房颤(AF)", 140, 92, 20, 150, 90, "女", 70, ["高血压", "心力衰竭"], ["高血压史", "糖尿病史"]),
            ("室速(VT)", "室速(VT)", 150, 85, 22, 100, 60, "男", 50, ["冠心病"], ["支架植入"]),
            ("室上速(SVT)", "室上速(SVT)", 180, 95, 18, 110, 70, "女", 40, [], []),
            ("交界性心率", "交界性心率", 50, 97, 14, 110, 70, "男", 65, ["冠心病"], ["起搏器"]),
            ("窦性心动过缓", "窦性心动过缓", 45, 96, 12, 105, 65, "男", 60, ["冠心病"], []),
            ("窦性心动过速", "窦性心动过速", 130, 95, 20, 160, 95, "女", 35, ["甲状腺功能亢进"], []),
            ("停搏(asystole)", "停搏(asystole)", 0, 0, 0, 0, 0, "男", 60, ["冠心病", "心力衰竭"], ["心脏手术"]),
            ("起搏心律", "起搏心律", 72, 97, 16, 125, 78, "男", 70, ["冠心病", "心力衰竭"], ["起搏器"]),
        ]
        def apply_one_click(rhythm, hr, spo2, resp, sys_bp, dia_bp, gender, age, history, past_history):
            # V10.0.0: 重置ROSC相关数据
            self.rosc_active = False
            self.first_shock_timestamp = None
            self.rosc_time_seconds = None
            self.total_shocks = 0
            self.vf_conversion_attempts = 0
            # 重置除颤后波形序列，防止场景切换后仍显示除颤后波形
            self.post_shock_phase = 0
            self.post_shock_timer = 0
            self.post_shock_amplitude = 1.0
            self.post_shock_rhythm_original = None
            
            self.ecg_rhythm = rhythm
            self.ecg_gene.set_rhythm(rhythm)
            self.sim_hr = hr
            self.ecg_gene.set_hr(hr)
            self.sim_spo2 = spo2
            self.spo2_gene.set_value(spo2)
            self.sim_resp = resp
            self.resp_gene.set_value(resp)
            self.sim_sys_bp = sys_bp
            self.sim_dia_bp = dia_bp
            self.sim_gender = gender
            self.sim_age = age
            self.sim_history = list(history)
            self.sim_past_history = list(past_history)
            self.nibp_result = f"{self.sim_sys_bp}/{self.sim_dia_bp}({(self.sim_sys_bp + 2*self.sim_dia_bp)//3 if self.sim_sys_bp>0 and self.sim_dia_bp>0 else 0})"
            if self.show_nibp:
                self.draw_screen_static()
            self.sim_alarm_list = []
            if self.sim_spo2 < 90:
                self.sim_alarm_list.append("low_spo2")
            if self.sim_resp > 20:
                self.sim_alarm_list.append("resp_fast")
            if 0 < self.sim_resp < 12:
                self.sim_alarm_list.append("resp_slow")
            if self.sim_hr > 120:
                self.sim_alarm_list.append("high_hr")
            if self.sim_sys_bp < 90:
                self.sim_alarm_list.append("low_bp")
            self.sim_alarm_list = list(set(self.sim_alarm_list))
            self.event_logger.log_event("一键模拟", f"患者: {self.sim_gender}, {self.sim_age}岁", {
                "rhythm": rhythm, "hr": hr, "spo2": spo2, "resp": resp,
                "bp": f"{self.sim_sys_bp}/{self.sim_dia_bp}",
                "history": self.sim_history,
                "past_history": self.sim_past_history
            })
            self.draw_screen_static()
            sim_win.destroy()
        Label(scrollable_frame, text="🎯 选择病种（点击即应用）", font=("Arial", 14, "bold"),
              fg=self.COLOR_BLUE, bg="#0a1a2a").pack(pady=10)
        btns_frame = Frame(scrollable_frame, bg="#0a1a2a")
        btns_frame.pack(pady=5)
        for i, (name, rhythm, hr, spo2, resp, sys_bp, dia_bp, gender, age, history, past_history) in enumerate(one_click_presets):
            if hr == 0 or spo2 == 0:
                btn_color = self.COLOR_RED_ALERT
            elif spo2 < 90 or sys_bp < 90:
                btn_color = self.COLOR_ORANGE_BTN
            else:
                btn_color = self.COLOR_BLUE
            btn = Button(btns_frame, text=name, font=("Arial", 11, "bold"),
                        bg=btn_color, fg="white", width=18, height=2,
                        command=lambda r=rhythm, h=hr, s=spo2, resp=resp, 
                                       sb=sys_bp, db=dia_bp, g=gender, a=age,
                                       hi=history, ph=past_history:
                                       apply_one_click(r, h, s, resp, sb, db, g, a, hi, ph))
            btn.grid(row=i//3, column=i%3, padx=4, pady=4)
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            sim_win.destroy()
        sim_win.protocol("WM_DELETE_WINDOW", on_close)

    def _open_sim_window(self):
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        sim_win = Toplevel(self.root)
        sim_win.title("SIM 临床模拟引擎 v2.0 — 自定义")
        sim_win.geometry("700x750")
        sim_win.configure(bg="#2a3a4a")
        sim_win.grab_set()
        main_frame = Frame(sim_win, bg="#2a3a4a")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        Label(main_frame, text="⚙ 自定义模拟", font=("Arial", 18, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=5)
        Label(main_frame, text="信息+病种+参数均手动设置", font=("Arial", 11),
              fg="#aaa", bg="#2a3a4a").pack(pady=2)
        canvas_frame = Frame(main_frame, bg="#2a3a4a")
        canvas_frame.pack(fill="both", expand=True)
        canvas = Canvas(canvas_frame, bg="#2a3a4a", highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#2a3a4a")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        Label(scrollable_frame, text="ECG 病种", font=("Arial", 14, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=5)
        ecg_rhythms = ["normal", "心肌缺血", "心肌梗死(STEMI)", "心肌梗死(NSTEMI)", "室颤(VF)", "室颤(VF儿童)", 
                       "房颤(AF)", "室速(VT)", "室上速(SVT)", "交界性心率",
                       "窦性心动过缓", "窦性心动过速", "停搏(asystole)", "起搏心律"]
        ecg_var = StringVar(scrollable_frame)
        ecg_var.set(self.ecg_rhythm if self.ecg_rhythm in ecg_rhythms else "normal")
        OptionMenu(scrollable_frame, ecg_var, *ecg_rhythms).pack(pady=5)
        Label(scrollable_frame, text="👤 患者信息", font=("Arial", 14, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=10)
        gender_frame = Frame(scrollable_frame, bg="#2a3a4a")
        gender_frame.pack(pady=3)
        Label(gender_frame, text="性别:", fg="white", bg="#2a3a4a", font=("Arial", 12)).pack(side="left", padx=5)
        gender_var = StringVar(value=self.sim_gender)
        gender_menu = OptionMenu(gender_frame, gender_var, "男", "女", "其他")
        gender_menu.config(bg="#3a4a5a", fg="white", width=10)
        gender_menu.pack(side="left", padx=5)
        age_frame = Frame(scrollable_frame, bg="#2a3a4a")
        age_frame.pack(pady=3)
        Label(age_frame, text="年龄 (3-99):", fg="white", bg="#2a3a4a", font=("Arial", 12)).pack(side="left", padx=5)
        age_entry = tk.Entry(age_frame, width=10, bg="#3a4a5a", fg="white")
        age_entry.insert(0, str(self.sim_age))
        age_entry.pack(side="left", padx=5)
        Label(scrollable_frame, text="📋 病史", font=("Arial", 14, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=10)
        history_options = ["高血压", "糖尿病", "低血糖", "高血糖", "血脂异常", "食物中毒", 
                          "冠心病", "心力衰竭", "慢性阻塞性肺病", "哮喘", "肾病", "肝病", "先天性心脏病"]
        history_vars = {}
        history_frame = Frame(scrollable_frame, bg="#2a3a4a")
        history_frame.pack(pady=5)
        for i, opt in enumerate(history_options):
            var = IntVar(value=1 if opt in self.sim_history else 0)
            history_vars[opt] = var
            cb = Checkbutton(history_frame, text=opt, variable=var, bg="#2a3a4a", fg="white",
                           selectcolor="#3a4a5a", font=("Arial", 10))
            cb.grid(row=i//3, column=i%3, sticky="w", padx=10, pady=2)
        Label(scrollable_frame, text="📜 既往史", font=("Arial", 14, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=10)
        past_history_options = ["心脏手术", "支架植入", "起搏器", "卒中/TIA", "糖尿病史", 
                               "高血压史", "吸烟", "饮酒", "药物过敏", "癫痫", "高血脂"]
        past_vars = {}
        past_frame = Frame(scrollable_frame, bg="#2a3a4a")
        past_frame.pack(pady=5)
        for i, opt in enumerate(past_history_options):
            var = IntVar(value=1 if opt in self.sim_past_history else 0)
            past_vars[opt] = var
            cb = Checkbutton(past_frame, text=opt, variable=var, bg="#2a3a4a", fg="white",
                           selectcolor="#3a4a5a", font=("Arial", 10))
            cb.grid(row=i//3, column=i%3, sticky="w", padx=10, pady=2)
        Label(scrollable_frame, text="📊 生命体征", font=("Arial", 14, "bold"),
              fg=self.COLOR_YELLOW, bg="#2a3a4a").pack(pady=10)
        hr_frame = Frame(scrollable_frame, bg="#2a3a4a")
        hr_frame.pack(fill="x", pady=3)
        Label(hr_frame, text=f"心率: {self.sim_hr} bpm", fg="white", bg="#2a3a4a", 
              font=("Arial", 12), width=15, anchor="w").pack(side="left", padx=5)
        hr_scale = Scale(hr_frame, from_=0, to=300, orient="horizontal", length=300,
                        bg="#2a3a4a", fg="white", troughcolor="#555", highlightthickness=0)
        hr_scale.set(self.sim_hr if self.sim_hr > 0 else 0)
        hr_scale.pack(side="left", padx=5)
        spo2_frame = Frame(scrollable_frame, bg="#2a3a4a")
        spo2_frame.pack(fill="x", pady=3)
        Label(spo2_frame, text=f"SPO₂: {self.sim_spo2}%", fg="white", bg="#2a3a4a",
              font=("Arial", 12), width=15, anchor="w").pack(side="left", padx=5)
        spo2_scale = Scale(spo2_frame, from_=0, to=100, orient="horizontal", length=300,
                          bg="#2a3a4a", fg="white", troughcolor="#555", highlightthickness=0)
        spo2_scale.set(self.sim_spo2 if self.sim_spo2 > 0 else 0)
        spo2_scale.pack(side="left", padx=5)
        resp_frame = Frame(scrollable_frame, bg="#2a3a4a")
        resp_frame.pack(fill="x", pady=3)
        Label(resp_frame, text=f"呼吸: {self.sim_resp}/min", fg="white", bg="#2a3a4a",
              font=("Arial", 12), width=15, anchor="w").pack(side="left", padx=5)
        resp_scale = Scale(resp_frame, from_=0, to=30, orient="horizontal", length=300,
                          bg="#2a3a4a", fg="white", troughcolor="#555", highlightthickness=0)
        resp_scale.set(self.sim_resp if self.sim_resp > 0 else 0)
        resp_scale.pack(side="left", padx=5)
        bp_frame = Frame(scrollable_frame, bg="#2a3a4a")
        bp_frame.pack(fill="x", pady=3)
        Label(bp_frame, text=f"血压: {self.sim_sys_bp}/{self.sim_dia_bp} mmHg", 
              fg="white", bg="#2a3a4a", font=("Arial", 12), width=20, anchor="w").pack(side="left", padx=5)
        sys_scale = Scale(bp_frame, from_=0, to=220, orient="horizontal", length=140,
                         bg="#2a3a4a", fg="white", troughcolor="#555", highlightthickness=0)
        sys_scale.set(self.sim_sys_bp if self.sim_sys_bp > 0 else 0)
        sys_scale.pack(side="left", padx=2)
        dia_scale = Scale(bp_frame, from_=0, to=140, orient="horizontal", length=140,
                         bg="#2a3a4a", fg="white", troughcolor="#555", highlightthickness=0)
        dia_scale.set(self.sim_dia_bp if self.sim_dia_bp > 0 else 0)
        dia_scale.pack(side="left", padx=2)
        Label(scrollable_frame, text="🚨 一键模拟危重症", font=("Arial", 14, "bold"),
              fg=self.COLOR_RED_ALERT, bg="#2a3a4a").pack(pady=10)
        def set_critical(rhythm, hr, spo2, resp, sys, dia):
            ecg_var.set(rhythm)
            hr_scale.set(hr)
            spo2_scale.set(spo2)
            resp_scale.set(resp)
            sys_scale.set(sys)
            dia_scale.set(dia)
            apply_sim()
        critical_btns_frame = Frame(scrollable_frame, bg="#2a3a4a")
        critical_btns_frame.pack(pady=5)
        critical_presets = [
            ("心肌缺血", lambda: set_critical("心肌缺血", 85, 96, 16, 130, 80)),
            ("心梗(STEMI)", lambda: set_critical("心肌梗死(STEMI)", 100, 94, 18, 140, 85)),
            ("心梗(NSTEMI)", lambda: set_critical("心肌梗死(NSTEMI)", 95, 92, 18, 135, 82)),
            ("成人室颤", lambda: set_critical("室颤(VF)", 280, 88, 10, 80, 50)),
            ("儿童室颤", lambda: set_critical("室颤(VF儿童)", 220, 85, 12, 85, 55)),
            ("房颤", lambda: set_critical("房颤(AF)", 140, 92, 20, 150, 90)),
            ("室速", lambda: set_critical("室速(VT)", 150, 85, 22, 100, 60)),
            ("停搏", lambda: set_critical("停搏(asystole)", 0, 0, 0, 0, 0))
        ]
        for i, (txt, cmd) in enumerate(critical_presets):
            btn = Button(critical_btns_frame, text=txt, font=("Arial", 10),
                        bg=self.COLOR_RED_ALERT, fg="white", width=12, height=1, command=cmd)
            btn.grid(row=i//4, column=i%4, padx=3, pady=3)
        def apply_sim():
            # V10.0.0: 重置ROSC相关数据
            self.rosc_active = False
            self.first_shock_timestamp = None
            self.rosc_time_seconds = None
            self.total_shocks = 0
            self.vf_conversion_attempts = 0
            # 重置除颤后波形序列，防止场景切换后仍显示除颤后波形
            self.post_shock_phase = 0
            self.post_shock_timer = 0
            self.post_shock_amplitude = 1.0
            self.post_shock_rhythm_original = None
            
            rhythm = ecg_var.get()
            self.ecg_rhythm = rhythm
            self.ecg_gene.set_rhythm(rhythm)
            hr = hr_scale.get()
            self.sim_hr = hr
            self.ecg_gene.set_hr(hr)
            spo2 = spo2_scale.get()
            self.sim_spo2 = spo2
            self.spo2_gene.set_value(spo2)
            resp = resp_scale.get()
            self.sim_resp = resp
            self.resp_gene.set_value(resp)
            self.sim_sys_bp = sys_scale.get()
            self.sim_dia_bp = dia_scale.get()
            self.sim_gender = gender_var.get()
            try:
                self.sim_age = int(age_entry.get())
                if self.sim_age < 3:
                    self.sim_age = 3
                elif self.sim_age > 99:
                    self.sim_age = 99
            except:
                self.sim_age = 45
            self.sim_history = [opt for opt, var in history_vars.items() if var.get() == 1]
            self.sim_past_history = [opt for opt, var in past_vars.items() if var.get() == 1]
            self.nibp_result = f"{self.sim_sys_bp}/{self.sim_dia_bp}({(self.sim_sys_bp + 2*self.sim_dia_bp)//3 if self.sim_sys_bp>0 and self.sim_dia_bp>0 else 0})"
            if self.show_nibp:
                self.draw_screen_static()
            self.sim_alarm_list = []
            if self.sim_spo2 < 90:
                self.sim_alarm_list.append("low_spo2")
            if self.sim_resp > 20:
                self.sim_alarm_list.append("resp_fast")
            if 0 < self.sim_resp < 12:
                self.sim_alarm_list.append("resp_slow")
            if self.sim_hr > 120:
                self.sim_alarm_list.append("high_hr")
            if self.sim_sys_bp < 90:
                self.sim_alarm_list.append("low_bp")
            self.sim_alarm_list = list(set(self.sim_alarm_list))
            self.event_logger.log_event("SIM设置", f"患者: {self.sim_gender}, {self.sim_age}岁", {
                "rhythm": rhythm, "hr": hr, "spo2": spo2, "resp": resp,
                "bp": f"{self.sim_sys_bp}/{self.sim_dia_bp}",
                "history": self.sim_history,
                "past_history": self.sim_past_history
            })
            self.draw_screen_static()
            sim_win.destroy()
        Button(scrollable_frame, text="✅ 应用设置", font=("Arial", 14),
               bg=self.COLOR_GREEN, fg="black", command=apply_sim).pack(pady=15)
        def on_close_sim():
            canvas.unbind_all("<MouseWheel>")
            sim_win.destroy()
        sim_win.protocol("WM_DELETE_WINDOW", on_close_sim)

    # ==================== 功能切换 ====================

    def toggle_lead(self):
        if self._is_in_self_test():
            return
        if self.mode != "Monitor":
            messagebox.showinfo("提示", "请在监护模式下操作心导联")
            return
        self.lead_connected = not self.lead_connected
        self.lead_alarm = not self.lead_connected
        status = "已连接" if self.lead_connected else "已断开"
        self.event_logger.log_event("操作", f"心导联 {status}")
        messagebox.showinfo("心导联", f"心导联 {status}")
        self.draw_screen_static()

    def toggle_line(self):
        if self._is_in_self_test():
            return
        if self.mode not in ["Manual Defib", "AED", "Monitor"]:
            messagebox.showinfo("提示", "请切换到除颤模式或监护模式操作治疗线路")
            return
        self.line_connected = not self.line_connected
        self.alarm_active = not self.line_connected
        status = "已连接" if self.line_connected else "已断开"
        self.event_logger.log_event("操作", f"治疗线路 {status}")
        messagebox.showinfo("治疗线路", f"治疗线路 {status}")
        self.draw_screen_static()

    def toggle_aed_pads(self):
        if self._is_in_self_test():
            return
        self.aed_pads_connected = not self.aed_pads_connected
        status = "已连接" if self.aed_pads_connected else "已断开"
        self.event_logger.log_event("操作", f"AED电极片 {status}")
        messagebox.showinfo("AED电极片", f"AED电极片电缆 {status}")
        self.draw_screen_static()

    def open_ecg_fault_setting(self):
        """设置 CHECK ECG LOAD 故障概率 (0.00-1.00)"""
        import tkinter as tk
        from tkinter import ttk
        win = tk.Toplevel(self.root)
        win.title("设置 CHECK ECG LOAD 故障概率")
        win.geometry("420x200")
        win.configure(bg="#0a1a2a")
        win.grab_set()
        win.resizable(False, False)
        
        frame = tk.Frame(win, bg="#0a1a2a")
        frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        tk.Label(frame, text="CHECK ECG LOAD 故障概率", font=("Arial", 14, "bold"),
                 fg=self.COLOR_YELLOW, bg="#0a1a2a").pack(pady=5)
        tk.Label(frame, text="0 = 永不故障   1 = 一直故障   默认: 0.02",
                 fg="#aaa", bg="#0a1a2a", font=("Arial", 10)).pack(pady=2)
        
        slider_frame = tk.Frame(frame, bg="#0a1a2a")
        slider_frame.pack(pady=10)
        
        value_label = tk.Label(slider_frame, text=f"{self.ecg_load_fault_prob:.2f}",
                               fg=self.COLOR_GREEN, bg="#0a1a2a",
                               font=("Arial", 16, "bold"), width=6)
        value_label.pack(side="left", padx=5)
        
        scale = tk.Scale(slider_frame, from_=0, to=100, orient="horizontal",
                         length=250, bg="#1a2a3a", fg="white",
                         highlightthickness=0, troughcolor="#2a3a4a",
                         activebackground=self.COLOR_GREEN)
        scale.set(int(self.ecg_load_fault_prob * 100))
        scale.pack(side="left", padx=5)
        
        def on_scale_change(val):
            prob = int(val) / 100.0
            value_label.config(text=f"{prob:.2f}")
        
        scale.config(command=on_scale_change)
        
        def apply():
            self.ecg_load_fault_prob = int(scale.get()) / 100.0
            self.event_logger.log_event("设置", f"ECG LOAD故障概率 → {self.ecg_load_fault_prob:.2f}")
            win.destroy()
            self.draw_screen_static()
        
        btn_frame = tk.Frame(frame, bg="#0a1a2a")
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="应用", font=("Arial", 12, "bold"),
                  bg=self.COLOR_GREEN, fg="white", width=10, command=apply).pack(side="left", padx=10)
        tk.Button(btn_frame, text="取消", font=("Arial", 12),
                  bg="#444", fg="white", width=10, command=win.destroy).pack(side="left", padx=10)

    # ==================== AED分析 ====================

    def start_aed_analysis(self):
        if self.mode != "AED":
            return
        if not self.aed_pads_connected:
            messagebox.showinfo("提示", "请先连接电极片电缆")
            return
        self.aed_analyzing = True
        self.aed_analysis_result = None
        self.draw_screen_static()
        self.root.after(3000, self.finish_aed_analysis)

    def finish_aed_analysis(self):
        self.aed_analyzing = False
        
        if self.ecg_rhythm == "室颤(VF儿童)" and not self.aed_child_mode:
            self.aed_child_mode = True
            self.vf_is_child = True
            age_str = simpledialog.askstring("儿童年龄", 
                                            "AED检测到儿童室颤，请输入年龄（3-17岁，支持半岁如10.5）:",
                                            parent=self.root)
            if age_str:
                try:
                    age = float(age_str.replace('，', '.'))
                    if 3.0 <= age <= 17.0:
                        self.child_age = age
                    else:
                        messagebox.showwarning("警告", "年龄必须在3-17岁之间，使用默认值5岁")
                        self.child_age = 5.0
                except ValueError:
                    messagebox.showwarning("警告", "请输入有效数字，使用默认值5岁")
                    self.child_age = 5.0
            else:
                self.child_age = 5.0
            
            available = self.get_available_child_energies(self.child_age)
            if available:
                self.energy = available[0]
            else:
                self.energy = 50
            self.energy_idx = self.energy_levels.index(min(self.energy, max(self.energy_levels)))
            self.event_logger.log_event("AED", "自动检测到儿童室颤，启用儿童模式", 
                                       {"age": self.child_age, "energy": self.energy})
            self.draw_screen_static()
        
        if self.ecg_rhythm in ["室颤(VF)", "室颤(VF儿童)", "室速(VT)"]:
            self.aed_analysis_result = "建议电击"
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                if available:
                    self.energy = available[0]
                else:
                    self.energy = 50
            else:
                self.energy = 200
            self.energy_idx = self.energy_levels.index(min(self.energy, max(self.energy_levels)))
            if self.ecg_rhythm == "房颤(AF)":
                self.sync_mode = True
                self.enter_sync_mode()
                self.aed_analysis_result = "房颤，已进入同步模式"
        elif self.ecg_rhythm == "房颤(AF)":
            self.aed_analysis_result = "建议电击 (同步)"
            self.sync_mode = True
            self.enter_sync_mode()
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                self.energy = available[0] if available else 50
            else:
                self.energy = 100
        else:
            self.aed_analysis_result = "不建议电击"
        self.draw_screen_static()
        if (self.aed_analysis_result.startswith("建议电击") or 
            ("建议电击" in self.aed_analysis_result and "不建议" not in self.aed_analysis_result)):
            self.do_charge()

    # ==================== 同步模式 ====================

    def toggle_sync_mode(self):
        if self.mode != "Manual Defib" or not self.power_on or not self.line_connected:
            messagebox.showinfo("提示", "请确保在Manual Defib模式且线路已连接")
            return
        self.sync_mode = not self.sync_mode
        if not self.sync_mode:
            self.exit_sync_mode()
        else:
            self.enter_sync_mode()

    def enter_sync_mode(self):
        self.sync_mode = True
        self.sync_pending = False
        self.draw_screen_static()
        print("[SYNC] 同步模式已开启")
        self.event_logger.log_event("操作", "进入同步模式")

    def exit_sync_mode(self, redraw=True):
        self.sync_mode = False
        self.sync_pending = False
        if self.sync_delay_task:
            self.root.after_cancel(self.sync_delay_task)
            self.sync_delay_task = None
        if redraw:
            self.draw_screen_static()
        print("[SYNC] 同步模式已退出")

    # ==================== 充电/放电 ====================

    def can_use_charge_shock(self):
        if self.mode == "Manual Defib":
            return True
        if self.mode == "Monitor" and self.self_test_running and not self.is_auto_self_test:
            return True
        if self.mode == "AED":
            return True
        return False

    def do_charge(self):
        if not self.power_on:
            return
        if not self.can_use_charge_shock():
            if self.mode == "Monitor":
                messagebox.showinfo("提示", "请在Manual Defib模式或用户检测模式下使用充电功能")
            return
        if self.mode == "Monitor" and self.self_test_running and not self.is_auto_self_test:
            self.line_connected = True
            self.alarm_active = False
        
        # ===== V11.00: 充电前阻抗阈值校验 =====
        current_imp = self.impedance_gen.get_current()
        self.impedance = current_imp  # 同步
        if current_imp > 200:
            self._cancel_charge_due_to_impedance(current_imp, "充电")
            return
        
        try:
            if self.is_charging or self.is_charged:
                return
            self.is_charging = True
            if sound_charging:
                sound_charging.play(-1)
            self.charge_total_time = self.get_charge_time(self.energy)
            self.charge_btn.config(text="充电...")
            self.charge_progress = 0
            self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging to {self.energy}J")
            self.charge_step()
            self.event_logger.log_event("操作", f"开始充电 {self.energy}J")
        except Exception:
            traceback.print_exc()

    def charge_step(self):
        if not self.is_charging:
            return
        interval_ms = 50
        increment = 100 * (interval_ms / 1000.0) / self.charge_total_time
        self.charge_progress += increment
        if self.charge_progress >= 100:
            self.charge_progress = 100
            self.finish_charge()
            return
        bar_len = self.bar_x2 - self.bar_x1
        fill_width = self.bar_x1 + (self.charge_progress / 100) * bar_len
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, fill_width, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging {int(self.charge_progress)}%")
        self.charging_task_id = self.root.after(interval_ms, self.charge_step)

    def finish_charge(self):
        self.charging_task_id = None
        self.is_charging = False
        self.is_charged = True
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.play(-1)
        self.charge_btn.config(text="完成！")
        self.shock_enabled = True
        self.screen_canvas.itemconfig(self.charge_tip, text="READY TO SHOCK ! Not touch patient!")
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x2, self.bar_y2)
        if hasattr(self, 'shock_cnt_text'):
            self.screen_canvas.itemconfig(self.shock_cnt_text, fill=self.COLOR_TEXT_ORANGE)
        self.start_shock_flash()
        self.auto_disarm_task = self.root.after(30000, self.auto_disarm)
        self.event_logger.log_event("操作", f"充电完成 {self.energy}J")

    def do_shock(self):
        if not self.can_use_charge_shock():
            if self.mode == "Monitor":
                messagebox.showinfo("提示", "请在Manual Defib模式或用户检测模式下使用放电功能")
            return
        if self.sync_mode:
            if self.is_charged and self.shock_enabled:
                self.sync_pending = True
                print("[SYNC] 等待下一个R波...")
            return
        self.do_shock_sync()

    def cancel_charge(self):
        if self.charging_task_id:
            self.root.after_cancel(self.charging_task_id)
            self.charging_task_id = None
        if self.auto_disarm_task:
            self.root.after_cancel(self.auto_disarm_task)
            self.auto_disarm_task = None
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.stop()
        self.stop_shock_flash()
        self.is_charging = False
        self.is_charged = False
        self.shock_enabled = False
        self.charge_btn.config(text="")
        self.charge_progress = 0
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x1, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text="")
        if hasattr(self, 'shock_cnt_text'):
            self.screen_canvas.itemconfig(self.shock_cnt_text, fill="#222")
        self.event_logger.log_event("操作", "取消充电")

    def _cancel_charge_due_to_impedance(self, impedance_value, phase="充电"):
        """V11.00: 因阻抗过高强制终止充电/放电，复位充电状态，停止音效，报告充电取消"""
        # 停止充电进度
        if self.charging_task_id:
            self.root.after_cancel(self.charging_task_id)
            self.charging_task_id = None
        if self.auto_disarm_task:
            self.root.after_cancel(self.auto_disarm_task)
            self.auto_disarm_task = None
        # 停止所有音效
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.stop()
        # 停止闪光
        self.stop_shock_flash()
        # 复位充电状态
        self.is_charging = False
        self.is_charged = False
        self.shock_enabled = False
        self.charge_btn.config(text="")
        self.charge_progress = 0
        if hasattr(self, 'bar_fill') and hasattr(self, 'bar_x1'):
            self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x1, self.bar_y2)
        if hasattr(self, 'charge_tip'):
            self.screen_canvas.itemconfig(self.charge_tip, text="")
        if hasattr(self, 'shock_cnt_text'):
            self.screen_canvas.itemconfig(self.shock_cnt_text, fill="#222")
        
        # 日志记录
        reason = "电极片接触不良/阻抗过大" if impedance_value < 999 else "电极脱落"
        self.event_logger.log_shock_blocked(
            self.shock_count + 1,
            impedance_value,
            reason
        )
        self.event_logger.log_impedance_event(
            "安全拦截",
            f"{phase}取消: 阻抗{impedance_value:.0f}Ω超标",
            impedance_value,
            {"phase": phase, "threshold": 200}
        )
        
        # 屏幕警告
        self.screen_canvas.delete("shock_message")
        self.screen_canvas.delete("impedance_warning")
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.create_rectangle(
            int(cw*0.15), int(ch*0.35), int(cw*0.85), int(ch*0.55),
            fill="#330000", outline=self.COLOR_RED_ALERT, width=4,
            tags="impedance_warning"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.40),
            text=f"⚠ 阻抗过高: {impedance_value:.0f}Ω ⚠",
            fill=self.COLOR_RED_ALERT,
            font=("Arial", 24, "bold"),
            tags="impedance_warning"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.46),
            text=f"{phase}已取消 - 请检查电极片贴敷",
            fill="white",
            font=("Arial", 16),
            tags="impedance_warning"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.51),
            text="电极片接触不良或脱落，请重新贴敷后重试",
            fill="#ff8888",
            font=("Arial", 12),
            tags="impedance_warning"
        )
        # 5秒后清除警告
        self.root.after(5000, lambda: self.screen_canvas.delete("impedance_warning"))
        self.redraw_dynamic_elements()
        
        print(f"[安全拦截] {phase}阶段阻抗{impedance_value:.0f}Ω > 200Ω，充电已取消")

    def auto_disarm(self):
        self._auto_disarming = True
        try:
            self.auto_disarm_task = None
            self.cancel_charge()
            self.event_logger.log_event("安全", "自动放电 (30秒超时)")
        finally:
            self._auto_disarming = False

    def _show_shock_message(self, x1, y1, x2, y2):
        self.shock_msg = self.screen_canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                                                        text="电击已释放！", fill=self.COLOR_RED_ALERT,
                                                        font=("Arial", 30, "bold"), tags="shock_message")

    def _show_impedance_critical_warning(self):
        """V11.00: 阻抗达到999Ω时弹出醒目警告"""
        if not hasattr(self, 'canvas_w') or not hasattr(self, 'canvas_h'):
            return
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("impedance_critical")
        # 半透明红色覆盖层
        self.screen_canvas.create_rectangle(
            int(cw*0.10), int(ch*0.25), int(cw*0.90), int(ch*0.65),
            fill="#3a0000", outline=self.COLOR_RED_ALERT, width=6,
            tags="impedance_critical"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.33),
            text="⚠ 电极片脱落！⚠",
            fill=self.COLOR_RED_ALERT,
            font=("Arial", 28, "bold"),
            tags="impedance_critical"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.42),
            text="阻抗 999Ω - 无法进行除颤",
            fill="white",
            font=("Arial", 20, "bold"),
            tags="impedance_critical"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.50),
            text="请立即检查电极片贴敷状态！",
            fill="#ffaa00",
            font=("Arial", 16),
            tags="impedance_critical"
        )
        self.screen_canvas.create_text(
            cw//2, int(ch*0.57),
            text="→ 使用 SIM 菜单中的电极操作选项重新贴敷 ←",
            fill="#cccccc",
            font=("Arial", 12),
            tags="impedance_critical"
        )
        # 8秒后自动清除
        self.root.after(8000, lambda: self.screen_canvas.delete("impedance_critical"))

    def restore_after_shock(self):
        self.draw_screen_static()
        self.refresh_text()
        self.redraw_dynamic_elements()
        self.shock_message_task = None

    def start_shock_flash(self):
        self.flash_state = False
        self.flash_task = self.root.after(500, self.toggle_shock_flash)

    def toggle_shock_flash(self):
        if not (self.is_charged or self._auto_charged):
            return
        self.flash_state = not self.flash_state
        if self.sync_mode:
            color = "#ffff00" if self.flash_state else self.COLOR_ORANGE_BTN
        else:
            color = "#ff4444" if self.flash_state else self.COLOR_ORANGE_BTN
        self.shock_canvas.itemconfig(self.shock_circle, fill=color)
        self.flash_task = self.root.after(500, self.toggle_shock_flash)

    def stop_shock_flash(self):
        if self.flash_task:
            self.root.after_cancel(self.flash_task)
            self.flash_task = None
        self.shock_canvas.itemconfig(self.shock_circle, fill=self.COLOR_ORANGE_BTN)

    # ==================== 动态更新 ====================

    def redraw_dynamic_elements(self):
        if not self.power_on:
            return
        self.screen_canvas.delete("dynamic_imp")
        self.screen_canvas.delete("dynamic_alarm")
        self.screen_canvas.delete("r_peak_marker")
        self.screen_canvas.delete("sim_alarm")
        self.screen_canvas.delete("sync_box")
        self.screen_canvas.delete("lead_drift_warning")  # V10.0.0

        # ===== 报警区域垂直分层，避免重叠交替闪烁 =====
        alarm_slot = 0  # 当前报警槽位
        ALARM_H = 0.06  # 每个报警栏高度占比
        ALARM_GAP = 0.005  # 间距
        ALARM_X1 = 0.02
        ALARM_X2 = 0.20

        if self.alarm_active and self.alarm_visible:
            alarm_x1 = int(self.canvas_w * ALARM_X1)
            alarm_y1 = int(self.canvas_h * (0.02 + alarm_slot * (ALARM_H + ALARM_GAP)))
            alarm_x2 = int(self.canvas_w * ALARM_X2)
            alarm_y2 = int(alarm_y1 + self.canvas_h * ALARM_H)
            self.screen_canvas.create_rectangle(alarm_x1, alarm_y1, alarm_x2, alarm_y2,
                                                outline=self.COLOR_ALARM_YELLOW, width=3,
                                                tags="dynamic_alarm")
            self.screen_canvas.create_text((alarm_x1+alarm_x2)//2, (alarm_y1+alarm_y2)//2,
                                           text="治疗线路脱落", fill=self.COLOR_ALARM_YELLOW,
                                           font=("SimSun", 10), tags="dynamic_alarm")
            alarm_slot += 1

        if self.lead_alarm and self.lead_alarm_visible:
            alarm_x1 = int(self.canvas_w * ALARM_X1)
            alarm_y1 = int(self.canvas_h * (0.02 + alarm_slot * (ALARM_H + ALARM_GAP)))
            alarm_x2 = int(self.canvas_w * ALARM_X2)
            alarm_y2 = int(alarm_y1 + self.canvas_h * ALARM_H)
            self.screen_canvas.create_rectangle(alarm_x1, alarm_y1, alarm_x2, alarm_y2,
                                                outline=self.COLOR_ALARM_YELLOW, width=3,
                                                tags="dynamic_alarm")
            self.screen_canvas.create_text((alarm_x1+alarm_x2)//2, (alarm_y1+alarm_y2)//2,
                                           text="心导联脱落", fill=self.COLOR_ALARM_YELLOW,
                                           font=("SimSun", 10), tags="dynamic_alarm")
            alarm_slot += 1

        # V10.0.0: 导联接触不良警告
        if self.lead_drift:
            alarm_x1 = int(self.canvas_w*0.70)
            alarm_y1 = int(self.canvas_h*0.02)
            alarm_x2 = int(self.canvas_w*0.90)
            alarm_y2 = int(self.canvas_h*0.08)
            self.screen_canvas.create_rectangle(alarm_x1, alarm_y1, alarm_x2, alarm_y2,
                                                outline=self.COLOR_ALARM_YELLOW, width=2,
                                                tags="lead_drift_warning")
            self.screen_canvas.create_text((alarm_x1+alarm_x2)//2, (alarm_y1+alarm_y2)//2,
                                           text="⚠ Check Leads",
                                           fill=self.COLOR_ALARM_YELLOW,
                                           font=("Arial", 10, "bold"), tags="lead_drift_warning")

        if self.sim_alarm_list and self.sim_alarm_visible:
            idx = self.sim_alarm_index % len(self.sim_alarm_list)
            alarm = self.sim_alarm_list[idx]
            alarm_x1 = int(self.canvas_w * ALARM_X1)
            alarm_y1 = int(self.canvas_h * (0.02 + alarm_slot * (ALARM_H + ALARM_GAP)))
            alarm_x2 = int(self.canvas_w * ALARM_X2)
            alarm_y2 = int(alarm_y1 + self.canvas_h * ALARM_H)
            if alarm in ["low_spo2", "shock_operation"]:
                color = self.COLOR_BLUE
                label = "低SpO2！！" if alarm == "low_spo2" else "除颤操作！"
            elif alarm == "low_bp":
                color = self.COLOR_RED_ALERT
                label = "低血压！"
            elif alarm == "lead_drift":
                color = self.COLOR_ALARM_YELLOW
                label = "导联干扰！"
            else:
                color = self.COLOR_RED_ALERT
                label = {"high_hr": "心率过高！", "resp_fast": "呼吸过速！", "resp_slow": "呼吸过缓！"}.get(alarm, "报警")
            self.screen_canvas.create_rectangle(alarm_x1, alarm_y1, alarm_x2, alarm_y2,
                                                outline=color, width=3,
                                                tags="sim_alarm")
            self.screen_canvas.create_text((alarm_x1+alarm_x2)//2, (alarm_y1+alarm_y2)//2,
                                           text=label, fill=color,
                                           font=("SimSun", 10), tags="sim_alarm")

        if self.mode != "Monitor" and self.line_connected:
            # ===== V11.00: 实时动态轮询阻抗值 =====
            imp = self.impedance_gen.get_current()
            self.impedance = imp  # 同步更新
            if imp <= 100:
                dot_color = self.COLOR_GREEN
            elif 100 < imp <= 150:
                dot_color = self.COLOR_YELLOW
            else:
                dot_color = self.COLOR_RED_ALERT
            dot_r = 8
            self.screen_canvas.create_oval(self.imp_dot_x-dot_r, self.imp_dot_y-dot_r,
                                           self.imp_dot_x+dot_r, self.imp_dot_y+dot_r,
                                           fill=dot_color, outline="white", width=1,
                                           tags="dynamic_imp")
            self.screen_canvas.create_text(self.imp_text_x, self.imp_text_y,
                                           text=f"{imp:.0f}Ω", fill="#222", font=("Arial",10),
                                           tags="dynamic_imp")
            # 阻抗状态文字
            status, level = self.impedance_gen.get_status()
            status_color = {"normal": "#36d036", "caution": "#f9e047", "warning": "#ff8800", "danger": "#ff2222"}.get(level, "#222")
            self.screen_canvas.create_text(self.imp_text_x, self.imp_text_y + int(self.canvas_h*0.025),
                                           text=status, fill=status_color, font=("Arial", 8, "bold"),
                                           tags="dynamic_imp")

        if self.sync_mode and self.ecg_gene.get_r_peak():
            if self.ecg_data:
                last_x, last_y = self.ecg_data[-1]
                self.screen_canvas.create_text(last_x, last_y - 12,
                                               text="▼", fill=self.COLOR_GREEN,
                                               font=("Arial", 12, "bold"),
                                               tags="r_peak_marker")

        if self.power_on and self.mode == "Manual Defib" and self.sync_mode:
            self.screen_canvas.delete("sync_box")
            if self.sync_flash_state:
                cw = self.canvas_w
                ch = self.canvas_h
                box_x1 = int(cw*0.09)
                box_y1 = int(ch*0.38)
                box_x2 = int(cw*0.75)
                box_y2 = int(ch*0.62)
                energy_x = (box_x1+box_x2)//2 + int(cw*0.05)
                sync_width = int(cw*0.06)
                sync_height = int(ch*0.04)
                sync_x1 = energy_x + 10
                sync_y1 = box_y1 + int(ch*0.06)
                sync_x2 = sync_x1 + sync_width
                sync_y2 = sync_y1 + sync_height
                self.screen_canvas.create_rectangle(sync_x1, sync_y1, sync_x2, sync_y2,
                                                    fill=self.COLOR_GREEN, outline="white", width=1,
                                                    tags="sync_box")
                self.screen_canvas.create_text((sync_x1+sync_x2)//2, (sync_y1+sync_y2)//2,
                                               text="同步", fill="white", font=("Arial",10,"bold"),
                                               tags="sync_box")

    def update_alarm_flash(self):
        if self.alarm_active:
            self.alarm_visible = not self.alarm_visible
        else:
            self.alarm_visible = False
            self.screen_canvas.delete("dynamic_alarm")

        if self.lead_alarm:
            self.lead_alarm_visible = not self.lead_alarm_visible
        else:
            self.lead_alarm_visible = False

        if self.sim_alarm_list:
            if "shock_operation" in self.sim_alarm_list:
                self.shock_operation_flash_count += 0.5
                if self.shock_operation_flash_count >= 5:
                    self.sim_alarm_list = [a for a in self.sim_alarm_list if a != "shock_operation"]
                    self.shock_operation_flash_count = 0
            self.sim_alarm_index += 1
            self.sim_alarm_visible = not self.sim_alarm_visible
        else:
            self.sim_alarm_visible = False
            self.screen_canvas.delete("sim_alarm")
            self.shock_operation_flash_count = 0

        self.sync_flash_state = not self.sync_flash_state
        self.redraw_dynamic_elements()
        self.alarm_flash_task = self.root.after(500, self.update_alarm_flash)

    def trigger_post_shock_sequence(self):
        self.post_shock_rhythm_original = self.ecg_rhythm
        self.post_shock_hr_original = self.sim_hr
        self.post_shock_phase = 1
        self.post_shock_timer = 0
        self.post_shock_amplitude = 1.0

    def _smooth_lerp(self, a, b, t):
        t = max(0.0, min(1.0, t))
        return a + (b - a) * (t * t * (3.0 - 2.0 * t))

    def _update_post_shock(self):
        if self.post_shock_phase == 0:
            return
        self.post_shock_timer += 1
        t = self.post_shock_timer
        T1 = 37
        T2 = 87
        T3 = 150
        T4 = 250
        T5 = 375

        if t >= T5:
            if self.post_shock_rhythm_original:
                self.ecg_gene.set_rhythm(self.post_shock_rhythm_original)
                self.ecg_rhythm = self.post_shock_rhythm_original
            self.ecg_gene.set_hr(self.post_shock_hr_original)
            self.sim_hr = self.post_shock_hr_original
            self.post_shock_amplitude = 1.0
            self.post_shock_phase = 0
            self.post_shock_timer = 0
            self.post_shock_rhythm_original = None
            self._post_shock_last_rhythm = None
            return

        if t < T1:
            target_rhythm = "停搏(asystole)"
            self.ecg_gene.set_hr(0)
            self.sim_hr = 0
            progress = t / T1
            self.post_shock_amplitude = self._smooth_lerp(1.0, 0.15, progress)
        else:
            target_rhythm = "normal"
            if t < T2:
                progress = (t - T1) / (T2 - T1)
                hr = self._smooth_lerp(0, 20, progress)
                amp = self._smooth_lerp(0.15, 0.35, progress)
            elif t < T3:
                progress = (t - T2) / (T3 - T2)
                hr = self._smooth_lerp(20, 60, progress)
                amp = self._smooth_lerp(0.35, 2.0, progress)
            elif t < T4:
                progress = (t - T3) / (T4 - T3)
                hr = self._smooth_lerp(60, 80, progress)
                amp = self._smooth_lerp(2.0, 1.0, progress)
            else:
                progress = (t - T4) / (T5 - T4)
                hr = self._smooth_lerp(80, self.post_shock_hr_original, progress)
                amp = 1.0
            self.ecg_gene.set_hr(int(hr))
            self.sim_hr = int(hr)
            self.post_shock_amplitude = amp
        
        # 仅在心律变化时调用 set_rhythm，避免每帧重置 ECG 相位 (self.t = 0.0)
        if getattr(self, '_post_shock_last_rhythm', None) != target_rhythm:
            self.ecg_gene.set_rhythm(target_rhythm)
            self._post_shock_last_rhythm = target_rhythm

    # ==================== 循环更新 ====================

    def update_ecg_loop(self):
        if not self.power_on:
            self.ecg_task_id = self.root.after(40, self.update_ecg_loop)
            return
        try:
            x_start = self.ecg_x1
            x_end = self.ecg_x2
            y_top = self.ecg_area_y1
            y_bottom = self.ecg_area_y2
            y_mid = (y_top + y_bottom) // 2

            if not self.lead_connected:
                self.screen_canvas.delete(self.ecg_line)
                self.ecg_line = self.screen_canvas.create_line(x_start, y_mid, x_end, y_mid,
                                                               fill=self.COLOR_GREEN, width=2)
                self.screen_canvas.itemconfig(self.hr_display, text="---")
                self.ecg_task_id = self.root.after(40, self.update_ecg_loop)
                return

            if self.post_shock_phase > 0:
                self._update_post_shock()

            amplitude = (y_bottom - y_top) // 3
            
            # ===== V10.0.0: ECG Pause =====
            if not self.ecg_paused:
                sample = self.ecg_gene.next()
                sample = sample * self.post_shock_amplitude
                
                # ===== V10.0.0: 导联接触不良干扰 =====
                if self.lead_drift:
                    # 模拟导联接触不良: 工频干扰 + 基线漂移 (不同于除颤后波形)
                    mains_hum = 0.25 * math.sin(2 * math.pi * 8 * self.ecg_gene.t)
                    baseline_wander = 0.15 * math.sin(2 * math.pi * 0.5 * self.ecg_gene.t)
                    sample += mains_hum + baseline_wander
                    self.lead_drift_timer -= 1
                    if self.lead_drift_timer <= 0:
                        self.clear_lead_drift()
                self._last_sample = sample
            else:
                # 冻结时保持最后采样值，不推进波形生成器
                sample = getattr(self, '_last_sample', 0)
            
            y_val = y_mid - sample * amplitude
            y_val = max(y_top + 5, min(y_bottom - 5, y_val))

            if not self.ecg_data:
                self.ecg_data.append((x_start, y_mid))
            last_x = self.ecg_data[-1][0]
            new_x = last_x + 3
            if new_x > x_end:
                shift = new_x - x_end
                self.ecg_data = [(x - shift, y) for x, y in self.ecg_data if x - shift >= x_start]
                if not self.ecg_data:
                    self.ecg_data.append((x_start, y_mid))
                new_x = self.ecg_data[-1][0] + 3
            self.ecg_data.append((new_x, y_val))

            self.screen_canvas.delete(self.ecg_line)
            if len(self.ecg_data) > 1:
                self.ecg_line = self.screen_canvas.create_line(self.ecg_data, fill=self.COLOR_GREEN, width=2)

            hr_text = str(self.sim_hr) if self.sim_hr > 0 else "0"
            self.screen_canvas.itemconfig(self.hr_display, text=hr_text)

            if self.sync_mode and self.sync_pending and self.ecg_gene.get_r_peak():
                self.sync_pending = False
                if self.sync_delay_task:
                    self.root.after_cancel(self.sync_delay_task)
                self.sync_delay_task = self.root.after(30, self.deliver_sync_shock)
                print("[SYNC] R波检测到，30ms后放电")

            self.redraw_dynamic_elements()
            self.ecg_task_id = self.root.after(40, self.update_ecg_loop)
        except Exception:
            traceback.print_exc()
            self.ecg_task_id = self.root.after(40, self.update_ecg_loop)

    def deliver_sync_shock(self):
        self.sync_delay_task = None
        print("[SYNC] 同步放电！")
        self.do_shock_sync()

    def update_spo2_loop(self):
        if not self.power_on:
            self.spo2_task_id = self.root.after(40, self.update_spo2_loop)
            return
        try:
            if not hasattr(self, 'spo2_area_y1'):
                self.spo2_task_id = self.root.after(40, self.update_spo2_loop)
                return
            x_start = self.ecg_x1
            x_end = self.ecg_x2
            y_top = self.spo2_area_y1
            y_bottom = self.spo2_area_y2
            y_mid = (y_top + y_bottom) // 2
            amplitude = (y_bottom - y_top) // 3

            sample = self.spo2_gene.next()
            y_val = y_mid - sample * amplitude

            if not self.spo2_data:
                self.spo2_data.append((x_start, y_mid))
            last_x = self.spo2_data[-1][0]
            new_x = last_x + 3
            if new_x > x_end:
                shift = new_x - x_end
                self.spo2_data = [(x - shift, y) for x, y in self.spo2_data if x - shift >= x_start]
                if not self.spo2_data:
                    self.spo2_data.append((x_start, y_mid))
                new_x = self.spo2_data[-1][0] + 3
            self.spo2_data.append((new_x, y_val))

            self.screen_canvas.delete(self.spo2_line)
            if len(self.spo2_data) > 1:
                self.spo2_line = self.screen_canvas.create_line(self.spo2_data, fill=self.COLOR_BLUE, width=2)

            self.spo2_task_id = self.root.after(40, self.update_spo2_loop)
        except Exception:
            traceback.print_exc()
            self.spo2_task_id = self.root.after(40, self.update_spo2_loop)

    def update_resp_loop(self):
        if not self.power_on or self.mode != "Monitor" or self.show_nibp:
            self.resp_task_id = self.root.after(40, self.update_resp_loop)
            return
        try:
            if not hasattr(self, 'resp_area_y1'):
                self.resp_task_id = self.root.after(40, self.update_resp_loop)
                return
            x_start = self.ecg_x1
            x_end = self.ecg_x2
            y_top = self.resp_area_y1
            y_bottom = self.resp_area_y2
            y_mid = (y_top + y_bottom) // 2
            amplitude = (y_bottom - y_top) // 3

            sample = self.resp_gene.next()
            y_val = y_mid - sample * amplitude
            y_val = max(y_top + 2, min(y_bottom - 2, y_val))

            if not self.resp_data:
                self.resp_data.append((x_start, y_mid))
            last_x = self.resp_data[-1][0]
            new_x = last_x + 3
            if new_x > x_end:
                shift = new_x - x_end
                self.resp_data = [(x - shift, y) for x, y in self.resp_data if x - shift >= x_start]
                if not self.resp_data:
                    self.resp_data.append((x_start, y_mid))
                new_x = self.resp_data[-1][0] + 3
            self.resp_data.append((new_x, y_val))

            self.screen_canvas.delete(self.resp_line)
            if len(self.resp_data) > 1:
                self.resp_line = self.screen_canvas.create_line(self.resp_data, fill=self.COLOR_RESP, width=2)

            self.resp_task_id = self.root.after(40, self.update_resp_loop)
        except Exception:
            traceback.print_exc()
            self.resp_task_id = self.root.after(40, self.update_resp_loop)

    def update_timer(self):
        if not self.power_on:
            self.timer_task_id = self.root.after(1000, self.update_timer)
            return
        try:
            self.timer_sec += 1
            mins = self.timer_sec // 60
            secs = self.timer_sec % 60
            if hasattr(self, 'timer_text'):
                self.screen_canvas.itemconfig(self.timer_text, text=f"{mins:02d}:{secs:02d}")

            if self.lead_connected and self.sim_hr > 0:
                delta_hr = random.randint(-5, 5)
                new_hr = self.sim_hr + delta_hr
                limits = get_hr_limits(self.ecg_rhythm)
                if limits[0] == 0 and limits[1] == 0:
                    new_hr = 0
                else:
                    new_hr = max(limits[0], min(limits[1], new_hr))
                self.sim_hr = new_hr
                self.ecg_gene.set_hr(new_hr)
                self.screen_canvas.itemconfig(self.hr_display, text=str(new_hr))

                if random.random() < 0.1:
                    delta_spo2 = random.randint(-1, 1)
                    new_spo2 = self.sim_spo2 + delta_spo2
                    new_spo2 = max(70, min(100, new_spo2))
                    self.sim_spo2 = new_spo2
                    self.spo2_gene.set_value(new_spo2)
                    if hasattr(self, 'spo2_value_text'):
                        self.screen_canvas.itemconfig(self.spo2_value_text, text=str(new_spo2))

                if random.random() < 0.1:
                    delta_resp = random.randint(-1, 1)
                    new_resp = self.sim_resp + delta_resp
                    new_resp = max(5, min(30, new_resp))
                    self.sim_resp = new_resp
                    self.resp_gene.set_value(new_resp)
                    if self.mode == "Monitor" and not self.show_nibp:
                        self.draw_screen_static()

                if random.random() < 0.05:
                    delta_co2 = random.randint(-1, 1)
                    new_co2 = self.co2_val + delta_co2
                    new_co2 = max(30, min(50, new_co2))
                    self.co2_val = new_co2
                    if hasattr(self, 'co2_value_text'):
                        self.screen_canvas.itemconfig(self.co2_value_text, text=str(new_co2))

                if self.sim_hr > 120:
                    if "high_hr" not in self.sim_alarm_list:
                        self.sim_alarm_list.append("high_hr")
                else:
                    if "high_hr" in self.sim_alarm_list:
                        self.sim_alarm_list.remove("high_hr")
                if self.sim_resp > 20:
                    if "resp_fast" not in self.sim_alarm_list:
                        self.sim_alarm_list.append("resp_fast")
                else:
                    if "resp_fast" in self.sim_alarm_list:
                        self.sim_alarm_list.remove("resp_fast")
                if 0 < self.sim_resp < 12:
                    if "resp_slow" not in self.sim_alarm_list:
                        self.sim_alarm_list.append("resp_slow")
                else:
                    if "resp_slow" in self.sim_alarm_list:
                        self.sim_alarm_list.remove("resp_slow")
                if self.sim_spo2 < 90:
                    if "low_spo2" not in self.sim_alarm_list:
                        self.sim_alarm_list.append("low_spo2")
                else:
                    if "low_spo2" in self.sim_alarm_list:
                        self.sim_alarm_list.remove("low_spo2")
                if self.sim_sys_bp < 90:
                    if "low_bp" not in self.sim_alarm_list:
                        self.sim_alarm_list.append("low_bp")
                else:
                    if "low_bp" in self.sim_alarm_list:
                        self.sim_alarm_list.remove("low_bp")

                # ===== V10.0.0: 随机触发导联干扰 (可配置概率) =====
                if random.random() < self.ecg_load_fault_prob and not self.lead_drift and self.lead_connected:
                    self.trigger_lead_drift()

            # ===== V11.00: 动态阻抗更新 (每秒) =====
            self.impedance_gen.update(1.0)
            self.impedance = self.impedance_gen.get_current()
            
            # 阻抗过高警告标志
            if self.impedance >= 999 and not self._impedance_warning_shown:
                self._impedance_warning_shown = True
                self.impedance_high_warning = True
                self._show_impedance_critical_warning()
            elif self.impedance < 999:
                self._impedance_warning_shown = False
                if self.impedance < 200:
                    self.impedance_high_warning = False

            self.timer_task_id = self.root.after(1000, self.update_timer)
        except Exception:
            traceback.print_exc()

    def refresh_text(self):
        if hasattr(self, 'energy_text'):
            self.screen_canvas.itemconfig(self.energy_text, text=str(self.energy))
        if hasattr(self, 'shock_cnt_text'):
            self.screen_canvas.itemconfig(self.shock_cnt_text, text=f"Energy: {self.energy}J")
            if not (self.is_charged or self._auto_charged):
                self.screen_canvas.itemconfig(self.shock_cnt_text, fill="#222")
        if hasattr(self, 'shock_cnt_text2'):
            self.screen_canvas.itemconfig(self.shock_cnt_text2, text=f"Shocks: {self.shock_count}")

    def get_charge_time(self, energy):
        return self.charge_time_map.get(energy, 2.0)

    # ==================== 关闭/自检等 ====================

    def on_close(self):
        for task in [self.ecg_task_id, self.timer_task_id, self.charging_task_id,
                     self.auto_disarm_task, self.flash_task, self.alarm_flash_task,
                     self.shock_message_task, self.shock_clear_task, self.sync_delay_task,
                     self.spo2_task_id, self.resp_task_id, self._auto_task_id,
                     self._auto_charge_task_id, self._key_test_timeout_id]:
            if task:
                self.root.after_cancel(task)
        self._clean_self_test_buttons()
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.stop()
        if sound_rosc:
            sound_rosc.stop()
        pygame.mixer.quit()
        self.root.destroy()

    def _clean_self_test_buttons(self):
        for btn in self._self_test_buttons:
            try:
                btn.destroy()
            except:
                pass
        self._self_test_buttons = []

    def _is_in_self_test(self):
        return self.self_test_running

    def _is_key_test_active(self):
        return self._key_test_active and self._key_test_phase == "waiting"

    def _is_self_test_mode(self):
        return self.self_test_running

    def _is_treatment_mode(self):
        if self.mode in ["Manual Defib", "AED"] and self.line_connected:
            return True
        return False

    # ==================== 自检相关 (从v9.56.3完整保留) ====================
    # 从 v9.56.3 完整移植，适用于 v11.31

    # ==================== 自检相关 ====================

    def _check_connections_before_test(self, test_type="auto"):
        """自检前检查连接状态"""
        connections = []
        if self.lead_connected:
            connections.append("心导联")
        if self.aed_pads_connected:
            connections.append("AED电极片")
        if not self.line_connected:
            self.line_connected = True
            self.alarm_active = False
            self.event_logger.log_event("自检", "治疗线路自动连接")
        if connections:
            msg = "检测到以下设备已连接，请先断开后再进行自检：\n\n"
            msg += "• " + "\n• ".join(connections) + "\n\n"
            msg += "请断开心导联和AED电极片后，点击'确定'重新发起自检。"
            messagebox.showwarning("连接检测", msg)
            return False
        return True

    def start_auto_self_test(self):
        """启动全自动自检"""
        if self.self_test_running:
            return
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        if self.mode != "Monitor":
            messagebox.showinfo("提示", "请在监护模式下启动自检")
            return
        if not self._check_connections_before_test("auto"):
            return
        if not messagebox.askyesno("全自动自检", 
                                   "设备即将进行全自动自检，请确保：\n"
                                   "1. 设备与病人隔离\n"
                                   "2. 不要接触病人\n"
                                   "3. 心导联和AED电极片已断开\n\n"
                                   "点击'是'开始全自动自检"):
            return
        self._clean_self_test_buttons()
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self._auto_charge_total = 0
        self._cable_test_in_progress = False
        self._cable_test_energy_done = False
        self._key_test_active = False
        self._key_test_phase = "idle"
        self._current_test_start_time = datetime.now()
        self._current_test_type = "auto"
        self.lead_connected = False
        self.lead_alarm = True
        self.aed_pads_connected = False
        self.line_connected = True
        self.alarm_active = False
        self.is_auto_self_test = True
        self.self_test_running = True
        self.self_test_step = 0
        self.self_test_result = {}
        self.self_test_steps = [
            ("常规检测", self.run_routine_test),
            ("大能量360J检测", self.run_auto_energy_360),
            ("大能量200J检测", self.run_auto_energy_200),
            ("电极片电缆检测", self.run_auto_cable_check),
            ("按键检测", self.run_key_test),
            ("完成", self.finish_auto_self_test)
        ]
        self.menu_open = False
        self.root.after(100, self.run_self_test_step)

    def start_user_test(self):
        """启动用户检测"""
        if self.self_test_running:
            return
        if not self.power_on:
            messagebox.showinfo("提示", "请先开机")
            return
        if self.mode != "Monitor":
            messagebox.showinfo("提示", "请在监护模式下启动用户检测")
            return
        if not self._check_connections_before_test("user"):
            return
        if not messagebox.askyesno("用户检测", 
                                   "设备即将进行用户检测，请确保：\n"
                                   "1. 设备与病人隔离\n"
                                   "2. 不要接触病人\n"
                                   "3. 心导联和AED电极片已断开\n\n"
                                   "点击'是'开始用户检测"):
            return
        self._clean_self_test_buttons()
        self._user_test_current_energy = 0
        self._user_test_waiting = False
        self._user_test_energies = [360, 200]
        self._cable_test_in_progress = False
        self._cable_test_energy_done = False
        self._key_test_active = False
        self._key_test_phase = "idle"
        self._current_test_start_time = datetime.now()
        self._current_test_type = "user"
        self.lead_connected = False
        self.lead_alarm = True
        self.aed_pads_connected = False
        self.line_connected = True
        self.alarm_active = False
        self.is_auto_self_test = False
        self.self_test_running = True
        self.self_test_step = 0
        self.self_test_result = {}
        self.self_test_steps = [
            ("常规检测", self.run_routine_test),
            ("大能量检测", self.run_user_energy_test),
            ("电极片电缆检测", self.run_user_cable_check),
            ("按键检测", self.run_key_test),
            ("完成", self.finish_user_test)
        ]
        self.menu_open = False
        self.root.after(100, self.run_self_test_step)

    def run_self_test_step(self):
        """执行自检步骤"""
        if self.self_test_step >= len(self.self_test_steps):
            if self.is_auto_self_test:
                self.finish_auto_self_test()
            else:
                self.finish_user_test()
            return
        step_name, step_func = self.self_test_steps[self.self_test_step]
        self.screen_canvas.delete("self_test_overlay")
        cw, ch = self.canvas_w, self.canvas_h
        test_type = "全自动自检" if self.is_auto_self_test else "用户检测"
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 50,
                                       text=f"D3 {test_type} - {step_name}",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 24, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 10,
                                       text=f"步骤 {self.self_test_step + 1}/{len(self.self_test_steps)}",
                                       fill="white",
                                       font=("Arial", 16),
                                       tags="self_test_overlay")
        step_func()

    def run_routine_test(self):
        """常规检测"""
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 50,
                                       text="常规检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 24, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 30,
                                       text="检测主电源... 通过",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 16),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 60,
                                       text="检测电池... 通过",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 16),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 90,
                                       text="检测显示模块... 通过",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 16),
                                       tags="self_test_overlay")
        self.self_test_result["routine"] = "通过"
        self._log_test_result("both", "常规检测", "通过")
        self.self_test_step += 1
        self.root.after(2500, self.run_self_test_step)

    # ==================== 全自动 360J 能量检测 ====================

    def run_auto_energy_360(self):
        """全自动 360J 能量检测"""
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 360
        self.energy_idx = self.energy_levels.index(360)
        self.refresh_text()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="全自动自检 - 大能量360J检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="正在充电 360J ...",
                                       fill="white",
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_charging = True
        self._auto_charged = False
        self._auto_charge_progress = 0
        self._auto_charge_total = self.get_charge_time(360)
        self._auto_charge_step_360()

    def _auto_charge_step_360(self):
        """360J 充电步骤"""
        if not self._auto_charging:
            return
        interval_ms = 50
        increment = 100 * (interval_ms / 1000.0) / self._auto_charge_total
        self._auto_charge_progress += increment
        if self._auto_charge_progress >= 100:
            self._auto_charge_progress = 100
            self._auto_charge_finish_360()
            return
        bar_len = self.bar_x2 - self.bar_x1
        fill_width = self.bar_x1 + (self._auto_charge_progress / 100) * bar_len
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, fill_width, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging {int(self._auto_charge_progress)}%")
        self._auto_charge_task_id = self.root.after(interval_ms, self._auto_charge_step_360)

    def _auto_charge_finish_360(self):
        """360J 充电完成"""
        self._auto_charging = False
        self._auto_charged = True
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.play(-1)
        self.charge_btn.config(text="READY")
        self.shock_enabled = True
        self.screen_canvas.itemconfig(self.charge_tip, text="READY TO SHOCK ! Not touch patient!")
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x2, self.bar_y2)
        self.start_shock_flash()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="全自动自检 - 大能量360J检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="充电完成，自动放电中...",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_task_id = self.root.after(800, self._auto_shock_360)

    def _auto_shock_360(self):
        """360J 自动放电"""
        if self._auto_charged:
            self.do_shock_sync()
            self.self_test_result["auto_360"] = "通过"
            self._log_test_result("auto", "360J能量测试", "通过", {"energy": 360})
            cw, ch = self.canvas_w, self.canvas_h
            self.screen_canvas.delete("self_test_overlay")
            self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                                fill="#000000", stipple="gray50",
                                                tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                           text="全自动自检 - 大能量360J检测",
                                           fill=self.COLOR_YELLOW,
                                           font=("Arial", 22, "bold"),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2,
                                           text="360J 测试通过 ✓",
                                           fill=self.COLOR_GREEN,
                                           font=("Arial", 24, "bold"),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 + 50,
                                           text="即将进入200J测试...",
                                           fill="white",
                                           font=("Arial", 14),
                                           tags="self_test_overlay")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self._auto_task_id = self.root.after(2000, self.after_auto_360)
        else:
            self._auto_task_id = self.root.after(300, self._auto_shock_360)

    def after_auto_360(self):
        """360J 测试完成后处理"""
        self._auto_charged = False
        self._auto_charging = False
        self.set_mode("Monitor")
        self.self_test_step += 1
        self.root.after(500, self.run_self_test_step)

    # ==================== 全自动 200J 能量检测 ====================

    def run_auto_energy_200(self):
        """全自动 200J 能量检测"""
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 200
        self.energy_idx = self.energy_levels.index(200)
        self.refresh_text()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="全自动自检 - 大能量200J检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="正在充电 200J ...",
                                       fill="white",
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_charging = True
        self._auto_charged = False
        self._auto_charge_progress = 0
        self._auto_charge_total = self.get_charge_time(200)
        self._auto_charge_step_200()

    def _auto_charge_step_200(self):
        """200J 充电步骤"""
        if not self._auto_charging:
            return
        interval_ms = 50
        increment = 100 * (interval_ms / 1000.0) / self._auto_charge_total
        self._auto_charge_progress += increment
        if self._auto_charge_progress >= 100:
            self._auto_charge_progress = 100
            self._auto_charge_finish_200()
            return
        bar_len = self.bar_x2 - self.bar_x1
        fill_width = self.bar_x1 + (self._auto_charge_progress / 100) * bar_len
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, fill_width, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging {int(self._auto_charge_progress)}%")
        self._auto_charge_task_id = self.root.after(interval_ms, self._auto_charge_step_200)

    def _auto_charge_finish_200(self):
        """200J 充电完成"""
        self._auto_charging = False
        self._auto_charged = True
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.play(-1)
        self.charge_btn.config(text="READY")
        self.shock_enabled = True
        self.screen_canvas.itemconfig(self.charge_tip, text="READY TO SHOCK ! Not touch patient!")
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x2, self.bar_y2)
        self.start_shock_flash()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="全自动自检 - 大能量200J检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="充电完成，自动放电中...",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_task_id = self.root.after(800, self._auto_shock_200)

    def _auto_shock_200(self):
        """200J 自动放电"""
        if self._auto_charged:
            self.do_shock_sync()
            self.self_test_result["auto_200"] = "通过"
            self._log_test_result("auto", "200J能量测试", "通过", {"energy": 200})
            cw, ch = self.canvas_w, self.canvas_h
            self.screen_canvas.delete("self_test_overlay")
            self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                                fill="#000000", stipple="gray50",
                                                tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                           text="全自动自检 - 大能量200J检测",
                                           fill=self.COLOR_YELLOW,
                                           font=("Arial", 22, "bold"),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2,
                                           text="200J 测试通过 ✓",
                                           fill=self.COLOR_GREEN,
                                           font=("Arial", 24, "bold"),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 + 50,
                                           text="即将进入电缆检测...",
                                           fill="white",
                                           font=("Arial", 14),
                                           tags="self_test_overlay")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self._auto_task_id = self.root.after(2000, self.after_auto_200)
        else:
            self._auto_task_id = self.root.after(300, self._auto_shock_200)

    def after_auto_200(self):
        """200J 测试完成后处理"""
        self._auto_charged = False
        self._auto_charging = False
        self.set_mode("Monitor")
        self.self_test_step += 1
        self.root.after(500, self.run_self_test_step)

    # ==================== 电缆检测 ====================

    def run_auto_cable_check(self):
        """全自动电缆检测"""
        self._ask_electrode_cable("auto")

    def run_user_cable_check(self):
        """用户电缆检测"""
        self._ask_electrode_cable("user")

    def _ask_electrode_cable(self, test_type="auto"):
        """询问是否有电极片电缆"""
        result = messagebox.askyesno("电极片电缆检测", 
                                    "是否有电极片电缆？\n\n"
                                    "选'是'：将进行360J自动充放电测试\n"
                                    "选'否'：跳过此测试")
        if result:
            if test_type == "auto":
                self._run_auto_cable_test()
            else:
                self._run_user_cable_test()
        else:
            self._cable_test_in_progress = False
            self._cable_test_energy_done = False
            self._log_test_result(test_type, "电缆检测", "跳过")
            self.self_test_step += 1
            self.root.after(500, self.run_self_test_step)

    def _run_auto_cable_test(self):
        """执行全自动电缆测试"""
        self._cable_test_in_progress = True
        self._cable_test_energy_done = False
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 360
        self.energy_idx = self.energy_levels.index(360)
        self.refresh_text()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="电极片电缆测试 - 360J",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="正在充电 360J ...",
                                       fill="white",
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_charging = True
        self._auto_charged = False
        self._auto_charge_progress = 0
        self._auto_charge_total = self.get_charge_time(360)
        self._auto_charge_step_cable()

    def _auto_charge_step_cable(self):
        """电缆测试充电步骤"""
        if not self._auto_charging:
            return
        interval_ms = 50
        increment = 100 * (interval_ms / 1000.0) / self._auto_charge_total
        self._auto_charge_progress += increment
        if self._auto_charge_progress >= 100:
            self._auto_charge_progress = 100
            self._auto_charge_finish_cable()
            return
        bar_len = self.bar_x2 - self.bar_x1
        fill_width = self.bar_x1 + (self._auto_charge_progress / 100) * bar_len
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, fill_width, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging {int(self._auto_charge_progress)}%")
        self._auto_charge_task_id = self.root.after(interval_ms, self._auto_charge_step_cable)

    def _auto_charge_finish_cable(self):
        """电缆测试充电完成"""
        self._auto_charging = False
        self._auto_charged = True
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.play(-1)
        self.charge_btn.config(text="READY")
        self.shock_enabled = True
        self.screen_canvas.itemconfig(self.charge_tip, text="READY TO SHOCK ! Not touch patient!")
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x2, self.bar_y2)
        self.start_shock_flash()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="电极片电缆测试 - 360J",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="充电完成，自动放电中...",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_task_id = self.root.after(1000, self._auto_shock_cable)

    def _auto_shock_cable(self):
        """电缆测试自动放电"""
        if self._auto_charged:
            self.do_shock_sync()
            self.self_test_result["cable_360"] = "通过"
            self._cable_test_energy_done = True
            self._log_test_result("auto", "电缆测试", "通过", {"energy": 360})
            cw, ch = self.canvas_w, self.canvas_h
            self.screen_canvas.delete("self_test_overlay")
            self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                                fill="#000000", stipple="gray50",
                                                tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2,
                                           text="360J 电缆测试通过 ✓",
                                           fill=self.COLOR_GREEN,
                                           font=("Arial", 28, "bold"),
                                           tags="self_test_overlay")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self._auto_task_id = self.root.after(1500, self._finish_cable_test)
        else:
            self._auto_task_id = self.root.after(300, self._auto_shock_cable)

    def _finish_cable_test(self):
        """完成电缆测试"""
        self._auto_charged = False
        self._auto_charging = False
        self._cable_test_in_progress = False
        self.set_mode("Monitor")
        self.self_test_step += 1
        self.root.after(500, self.run_self_test_step)

    def _run_user_cable_test(self):
        """执行用户电缆测试"""
        self._cable_test_in_progress = True
        self._cable_test_energy_done = False
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 360
        self.energy_idx = self.energy_levels.index(360)
        self.refresh_text()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="用户检测 - 电缆测试",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="正在充电 360J ...",
                                       fill="white",
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_charging = True
        self._auto_charged = False
        self._auto_charge_progress = 0
        self._auto_charge_total = self.get_charge_time(360)
        self._auto_charge_step_user_cable()

    def _auto_charge_step_user_cable(self):
        """用户电缆测试充电步骤"""
        if not self._auto_charging:
            return
        interval_ms = 50
        increment = 100 * (interval_ms / 1000.0) / self._auto_charge_total
        self._auto_charge_progress += increment
        if self._auto_charge_progress >= 100:
            self._auto_charge_progress = 100
            self._auto_charge_finish_user_cable()
            return
        bar_len = self.bar_x2 - self.bar_x1
        fill_width = self.bar_x1 + (self._auto_charge_progress / 100) * bar_len
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, fill_width, self.bar_y2)
        self.screen_canvas.itemconfig(self.charge_tip, text=f"Charging {int(self._auto_charge_progress)}%")
        self._auto_charge_task_id = self.root.after(interval_ms, self._auto_charge_step_user_cable)

    def _auto_charge_finish_user_cable(self):
        """用户电缆测试充电完成"""
        self._auto_charging = False
        self._auto_charged = True
        if sound_charging:
            sound_charging.stop()
        if sound_charged:
            sound_charged.play(-1)
        self.charge_btn.config(text="READY")
        self.shock_enabled = True
        self.screen_canvas.itemconfig(self.charge_tip, text="READY TO SHOCK ! Not touch patient!")
        self.screen_canvas.coords(self.bar_fill, self.bar_x1, self.bar_y1, self.bar_x2, self.bar_y2)
        self.start_shock_flash()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="用户检测 - 电缆测试",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="充电完成，自动放电中...",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 18),
                                       tags="self_test_overlay")
        self._auto_task_id = self.root.after(1000, self._auto_shock_user_cable)

    def _auto_shock_user_cable(self):
        """用户电缆测试自动放电"""
        if self._auto_charged:
            self.do_shock_sync()
            self.self_test_result["user_cable_360"] = "通过"
            self._cable_test_energy_done = True
            self._log_test_result("user", "电缆测试", "通过", {"energy": 360})
            cw, ch = self.canvas_w, self.canvas_h
            self.screen_canvas.delete("self_test_overlay")
            self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                                fill="#000000", stipple="gray50",
                                                tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2,
                                           text="360J 电缆测试通过 ✓",
                                           fill=self.COLOR_GREEN,
                                           font=("Arial", 28, "bold"),
                                           tags="self_test_overlay")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self._auto_task_id = self.root.after(1500, self._finish_user_cable_test)
        else:
            self._auto_task_id = self.root.after(300, self._auto_shock_user_cable)

    def _finish_user_cable_test(self):
        """完成用户电缆测试"""
        self._auto_charged = False
        self._auto_charging = False
        self._cable_test_in_progress = False
        self.set_mode("Monitor")
        self.self_test_step += 1
        self.root.after(500, self.run_self_test_step)

    # ==================== 用户能量检测 ====================

    def run_user_energy_test(self):
        """用户能量检测"""
        self._clean_self_test_buttons()
        self._user_test_current_energy = 0
        self._user_test_waiting = False
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 360
        self.energy_idx = self.energy_levels.index(360)
        self.refresh_text()
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 80,
                                       text="用户检测 - 大能量检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_overlay")
        self._update_user_energy_display()

    def _update_user_energy_display(self):
        """更新用户能量检测界面"""
        cw, ch = self.canvas_w, self.canvas_h
        current_energy = self._user_test_energies[self._user_test_current_energy] if self._user_test_current_energy < len(self._user_test_energies) else None
        self.screen_canvas.delete("user_test_info")
        if current_energy is None:
            self.screen_canvas.create_text(cw//2, ch//2 - 30,
                                           text="所有能量测试完成！",
                                           fill=self.COLOR_GREEN,
                                           font=("Arial", 24, "bold"),
                                           tags="user_test_info")
            return
        self.screen_canvas.create_text(cw//2, ch//2 - 30,
                                       text=f"请测试 {current_energy}J",
                                       fill="white",
                                       font=("Arial", 20, "bold"),
                                       tags="user_test_info")
        self.screen_canvas.create_text(cw//2, ch//2 + 10,
                                       text="1. 按 Charge 键充电",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 14),
                                       tags="user_test_info")
        self.screen_canvas.create_text(cw//2, ch//2 + 35,
                                       text="2. 按 Shock 键放电",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 14),
                                       tags="user_test_info")
        progress = f"进度: {self._user_test_current_energy + 1}/{len(self._user_test_energies)}"
        self.screen_canvas.create_text(cw//2, ch//2 + 65,
                                       text=progress,
                                       fill="#ccc",
                                       font=("Arial", 12),
                                       tags="user_test_info")
        self.charge_btn.config(command=self._user_handle_charge)
        self.shock_canvas.bind("<Button-1>", lambda e: self._user_handle_shock())
        self.charge_btn.config(state="normal")

    def _user_handle_charge(self):
        """用户能量检测 - 处理充电"""
        if self._user_test_current_energy >= len(self._user_test_energies):
            return
        if self.is_charging or self.is_charged:
            return
        energy = self._user_test_energies[self._user_test_current_energy]
        self.energy = energy
        self.energy_idx = self.energy_levels.index(energy)
        self.refresh_text()
        self.do_charge()
        self._user_test_waiting = True
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("user_test_info")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 40,
                                       text=f"充电中... {energy}J",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 24, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 20,
                                       text="请等待充电完成，然后按Shock放电",
                                       fill="white",
                                       font=("Arial", 14),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 + 50,
                                       text=f"进度: {self._user_test_current_energy + 1}/{len(self._user_test_energies)}",
                                       fill="#ccc",
                                       font=("Arial", 12),
                                       tags="self_test_overlay")

    def _user_handle_shock(self):
        """用户能量检测 - 处理放电"""
        if self._user_test_current_energy >= len(self._user_test_energies):
            return
        if not self.is_charged:
            if self._user_test_waiting:
                cw, ch = self.canvas_w, self.canvas_h
                self.screen_canvas.create_text(cw//2, ch//2 + 80,
                                               text="请先等待充电完成！",
                                               fill=self.COLOR_RED_ALERT,
                                               font=("Arial", 14, "bold"),
                                               tags="self_test_overlay")
            return
        energy = self.energy
        self.do_shock_sync()
        self.self_test_result[f"user_energy_{energy}"] = "通过"
        self._log_test_result("user", f"{energy}J能量测试", "通过", {"energy": energy})
        self._user_test_current_energy += 1
        self._user_test_waiting = False
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 40,
                                       text=f"{energy}J 测试通过 ✓",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 28, "bold"),
                                       tags="self_test_overlay")
        if self._user_test_current_energy >= len(self._user_test_energies):
            self.screen_canvas.create_text(cw//2, ch//2 + 30,
                                           text="所有能量测试完成！",
                                           fill=self.COLOR_YELLOW,
                                           font=("Arial", 18),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 + 60,
                                           text="即将进入下一步...",
                                           fill="white",
                                           font=("Arial", 14),
                                           tags="self_test_overlay")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self.charge_btn.config(command=self.do_charge)
            self.root.after(1500, self._user_energy_test_complete)
        else:
            next_energy = self._user_test_energies[self._user_test_current_energy]
            self.screen_canvas.create_text(cw//2, ch//2 + 30,
                                           text=f"请继续测试 {next_energy}J",
                                           fill=self.COLOR_YELLOW,
                                           font=("Arial", 16),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 + 55,
                                           text=f"进度: {self._user_test_current_energy + 1}/{len(self._user_test_energies)}",
                                           fill="#ccc",
                                           font=("Arial", 12),
                                           tags="self_test_overlay")
            self.screen_canvas.create_text(cw//2, ch//2 + 80,
                                           text="按Charge键充电",
                                           fill="white",
                                           font=("Arial", 12),
                                           tags="self_test_overlay")
            self.energy = next_energy
            self.energy_idx = self.energy_levels.index(next_energy)
            self.refresh_text()
            self.charge_btn.config(command=self._user_handle_charge)
            self.shock_canvas.bind("<Button-1>", lambda e: self._user_handle_shock())
            self.charge_btn.config(state="normal")

    def _user_energy_test_complete(self):
        """用户能量检测完成"""
        self._clean_self_test_buttons()
        self.set_mode("Monitor")
        self.screen_canvas.delete("self_test_overlay")
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text="大能量检测完成 ✓",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 28, "bold"),
                                       tags="self_test_overlay")
        self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
        self.charge_btn.config(command=self.do_charge)
        self.self_test_step += 1
        self.root.after(1500, self.run_self_test_step)

    # ==================== 按键检测 ====================

    def run_key_test(self):
        """按键检测"""
        cw, ch = self.canvas_w, self.canvas_h
        self.key_test_targets = [
            ("NIBP", self._key_test_nibp),
            ("Alarm Pause", self._key_test_alarm),
            ("Event", self._key_test_event),
            ("药品库", self._key_test_drug),
            ("Menu", self._key_test_menu),
            ("SIM", self._key_test_sim),
            ("能量+", self._key_test_energy_plus),
            ("能量-", self._key_test_energy_minus)
        ]
        self.key_test_index = 0
        self._key_test_active = True
        self._key_test_phase = "waiting"
        self._key_test_timeout_id = None
        self.screen_canvas.delete("self_test_overlay")
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text="按键检测",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 24, "bold"),
                                       tags="self_test_overlay")
        self.screen_canvas.create_text(cw//2, ch//2 - 10,
                                       text=f"请按下闪烁的按键 ({self.key_test_index + 1}/{len(self.key_test_targets)})",
                                       fill="white",
                                       font=("Arial", 16),
                                       tags="self_test_overlay")
        self._key_test_start_time = datetime.now()
        self._log_test_result("both", "按键检测", "进行中")
        self._highlight_key(self.key_test_index)

    def _highlight_key(self, index):
        """高亮当前需要按下的按键"""
        cw, ch = self.canvas_w, self.canvas_h
        if index >= len(self.key_test_targets):
            self._finish_key_test()
            return
        key_name, _ = self.key_test_targets[index]
        self.screen_canvas.delete("key_highlight")
        self.screen_canvas.create_text(cw//2, ch//2 + 40,
                                       text=f"请按下: {key_name}",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="key_highlight")
        self._key_flash_count = 0
        self._key_test_active = True
        self._key_test_phase = "waiting"
        self._flash_key_highlight()

    def _flash_key_highlight(self):
        """闪烁高亮提示"""
        if not self._key_test_active or self.key_test_index >= len(self.key_test_targets):
            return
        self._key_flash_count += 1
        color = self.COLOR_YELLOW if self._key_flash_count % 2 == 0 else self.COLOR_RED_ALERT
        try:
            self.screen_canvas.itemconfig("key_highlight", fill=color)
        except:
            pass
        if self._key_flash_count < 20:
            if self._key_test_active and self._key_test_phase == "waiting":
                self._key_test_timeout_id = self.root.after(500, self._flash_key_highlight)
        else:
            try:
                self.screen_canvas.itemconfig("key_highlight", fill=self.COLOR_RED_ALERT)
                self.screen_canvas.itemconfig("key_highlight", text="⏰ 超时!")
            except:
                pass
            key_name = self.key_test_targets[self.key_test_index][0]
            self.self_test_result[f"key_{key_name}"] = "超时"
            self._log_test_result("both", f"按键-{key_name}", "超时")
            self._key_test_active = False
            self._key_test_phase = "finished"
            self.key_test_index += 1
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(1000, self._finish_key_test)
            else:
                self.root.after(1000, self._highlight_key, self.key_test_index)

    def _finish_key_test(self):
        """完成按键检测"""
        self._key_test_active = False
        self._key_test_phase = "finished"
        if self._key_test_timeout_id:
            self.root.after_cancel(self._key_test_timeout_id)
            self._key_test_timeout_id = None
        has_timeout = any("超时" in str(v) for v in self.self_test_result.values())
        if has_timeout:
            self.self_test_result["key_test"] = "部分超时"
            self._log_test_result("both", "按键检测", "部分超时")
        else:
            self.self_test_result["key_test"] = "通过"
            self._log_test_result("both", "按键检测", "通过")
        self.screen_canvas.delete("key_highlight")
        self.screen_canvas.delete("self_test_overlay")
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.create_rectangle(0, 0, cw, ch, 
                                            fill="#000000", stipple="gray50",
                                            tags="self_test_overlay")
        status_text = "按键检测完成" if not has_timeout else "按键检测完成 (有超时)"
        self.screen_canvas.create_text(cw//2, ch//2,
                                       text=status_text,
                                       fill=self.COLOR_GREEN if not has_timeout else self.COLOR_YELLOW,
                                       font=("Arial", 24, "bold"),
                                       tags="self_test_overlay")
        self.self_test_step += 1
        self.root.after(1500, self.run_self_test_step)

    # ==================== 按键检测 - 各按键回调 ====================

    def _key_test_nibp(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "NIBP":
            self.self_test_result["key_NIBP"] = "通过"
            self._log_test_result("both", "按键-NIBP", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_alarm(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "Alarm Pause":
            self.self_test_result["key_Alarm Pause"] = "通过"
            self._log_test_result("both", "按键-Alarm Pause", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_event(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "Event":
            self.self_test_result["key_Event"] = "通过"
            self._log_test_result("both", "按键-Event", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_drug(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "药品库":
            self.self_test_result["key_药品库"] = "通过"
            self._log_test_result("both", "按键-药品库", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_menu(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "Menu":
            self.self_test_result["key_Menu"] = "通过"
            self._log_test_result("both", "按键-Menu", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_sim(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "SIM":
            self.self_test_result["key_SIM"] = "通过"
            self._log_test_result("both", "按键-SIM", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_energy_plus(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "能量+":
            self.self_test_result["key_能量+"] = "通过"
            self._log_test_result("both", "按键-能量+", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    def _key_test_energy_minus(self):
        if not self._key_test_active or self._key_test_phase != "waiting":
            return False
        if self.key_test_index < len(self.key_test_targets) and self.key_test_targets[self.key_test_index][0] == "能量-":
            self.self_test_result["key_能量-"] = "通过"
            self._log_test_result("both", "按键-能量-", "通过")
            self.key_test_index += 1
            self._key_test_active = False
            self._key_test_phase = "finished"
            if self._key_test_timeout_id:
                self.root.after_cancel(self._key_test_timeout_id)
                self._key_test_timeout_id = None
            if self.key_test_index >= len(self.key_test_targets):
                self.root.after(500, self._finish_key_test)
            else:
                self.root.after(500, self._highlight_key, self.key_test_index)
            return True
        return False

    # ==================== 自检完成 ====================

    def finish_auto_self_test(self):
        """全自动自检完成"""
        self._clean_self_test_buttons()
        self.screen_canvas.delete("self_test_overlay")
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.create_rectangle(cw//2 - 220, ch//2 - 130, cw//2 + 220, ch//2 + 130,
                                            fill="#0a1a2a", outline=self.COLOR_GREEN,
                                            tags="self_test_report")
        self.screen_canvas.create_text(cw//2, ch//2 - 90,
                                       text="全自动自检完成",
                                       fill=self.COLOR_GREEN,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_report")
        passed = sum(1 for v in self.self_test_result.values() if v == "通过")
        total = len(self.self_test_result)
        result_text = f"通过: {passed}/{total}" if total > 0 else "全部通过 ✓"
        self.screen_canvas.create_text(cw//2, ch//2 - 40,
                                       text=f"检测结果: {result_text}",
                                       fill=self.COLOR_YELLOW if passed < total else self.COLOR_GREEN,
                                       font=("Arial", 18),
                                       tags="self_test_report")
        y_pos = ch//2 + 10
        for key, value in self.self_test_result.items():
            color = self.COLOR_GREEN if value == "通过" else self.COLOR_RED_ALERT
            display_key = key.replace("auto_", "").replace("_", " ").title()
            self.screen_canvas.create_text(cw//2, y_pos,
                                           text=f"{display_key}: {value}",
                                           fill=color,
                                           font=("Arial", 12),
                                           tags="self_test_report")
            y_pos += 25
        self.event_logger.log_event("自检", f"全自动自检完成 - {result_text}", self.self_test_result)
        ok_btn = Button(self.root, text="确定", font=("Arial", 14),
                       bg=self.COLOR_GREEN, fg="black",
                       command=self._finish_auto_self_test)
        ok_btn.place(x=cw//2 - 40, y=ch//2 + 80, width=80, height=35)
        self._self_test_buttons.append(ok_btn)

    def _finish_auto_self_test(self):
        """完成全自动自检 - 清理并重启"""
        self._clean_self_test_buttons()
        self.screen_canvas.delete("self_test_report")
        self.screen_canvas.delete("self_test_overlay")
        self.self_test_running = False
        self.is_auto_self_test = False
        self.self_test_result = {}
        self._key_test_active = False
        self._key_test_phase = "idle"
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self._cable_test_in_progress = False
        self._cable_test_energy_done = False
        if self.is_charging:
            self.is_charging = False
            if sound_charging:
                sound_charging.stop()
        if self.is_charged:
            self.is_charged = False
            if sound_charged:
                sound_charged.stop()
        self.shock_enabled = False
        self.charge_btn.config(text="")
        self.charge_progress = 0
        self.set_mode("Off")
        self.root.after(1000, self._reboot_to_defib)

    def finish_user_test(self):
        """用户检测完成"""
        self._clean_self_test_buttons()
        self.screen_canvas.delete("self_test_overlay")
        cw, ch = self.canvas_w, self.canvas_h
        self.screen_canvas.create_rectangle(cw//2 - 220, ch//2 - 140, cw//2 + 220, ch//2 + 140,
                                            fill="#0a1a2a", outline=self.COLOR_YELLOW,
                                            tags="self_test_report")
        self.screen_canvas.create_text(cw//2, ch//2 - 100,
                                       text="用户检测完成",
                                       fill=self.COLOR_YELLOW,
                                       font=("Arial", 22, "bold"),
                                       tags="self_test_report")
        passed = sum(1 for v in self.self_test_result.values() if v == "通过")
        total = len(self.self_test_result)
        result_text = f"通过: {passed}/{total}" if total > 0 else "全部通过 ✓"
        self.screen_canvas.create_text(cw//2, ch//2 - 60,
                                       text=f"检测结果: {result_text}",
                                       fill=self.COLOR_YELLOW if passed < total else self.COLOR_GREEN,
                                       font=("Arial", 16),
                                       tags="self_test_report")
        y_pos = ch//2 - 20
        for key, value in self.self_test_result.items():
            color = self.COLOR_GREEN if value == "通过" else self.COLOR_RED_ALERT
            display_key = key.replace("user_", "").replace("_", " ").title()
            self.screen_canvas.create_text(cw//2, y_pos,
                                           text=f"{display_key}: {value}",
                                           fill=color,
                                           font=("Arial", 13),
                                           tags="self_test_report")
            y_pos += 28
        self.event_logger.log_event("自检", f"用户检测完成 - {result_text}", self.self_test_result)
        ok_btn = Button(self.root, text="确定", font=("Arial", 14),
                       bg=self.COLOR_GREEN, fg="black",
                       command=self._finish_user_test)
        ok_btn.place(x=cw//2 - 40, y=ch//2 + 90, width=80, height=35)
        self._self_test_buttons.append(ok_btn)

    def _finish_user_test(self):
        """完成用户检测 - 清理并重启"""
        self._clean_self_test_buttons()
        self.screen_canvas.delete("self_test_report")
        self.screen_canvas.delete("self_test_overlay")
        self.self_test_running = False
        self.is_auto_self_test = False
        self.self_test_result = {}
        self._key_test_active = False
        self._key_test_phase = "idle"
        self._auto_charged = False
        self._auto_charging = False
        self._auto_charge_progress = 0
        self._cable_test_in_progress = False
        self._cable_test_energy_done = False
        if self.is_charging:
            self.is_charging = False
            if sound_charging:
                sound_charging.stop()
        if self.is_charged:
            self.is_charged = False
            if sound_charged:
                sound_charged.stop()
        self.shock_enabled = False
        self.charge_btn.config(text="")
        self.charge_progress = 0
        self.set_mode("Off")
        self.root.after(1000, self._reboot_to_defib)

    def _log_test_result(self, test_type, test_name, result, details=None):
        """记录测试结果到事件日志"""
        self.event_logger.log_test(test_type, test_name, result, details or {})
        if result == "通过":
            desc = f"{test_type}检测 - {test_name} 通过"
        elif result == "失败":
            desc = f"{test_type}检测 - {test_name} 失败"
        else:
            desc = f"{test_type}检测 - {test_name} {result}"
        self.event_logger.log_event("自检", desc, {"test_type": test_type, "test_name": test_name, "result": result})

    def _reboot_to_defib(self):
        """重启到Manual Defib模式"""
        self.set_mode("Manual Defib")
        self.line_connected = True
        self.alarm_active = False
        self.energy = 200
        self.energy_idx = self.energy_levels.index(200)
        self.refresh_text()
        self.draw_screen_static()
        self.redraw_dynamic_elements()
        if self.is_auto_self_test:
            messagebox.showinfo("全自动自检完成", "设备已重启，切换到Manual Defib模式")
        else:
            messagebox.showinfo("用户检测完成", "设备已重启，切换到Manual Defib模式")

    def set_mode(self, mode):
        if self.self_test_running and self.is_auto_self_test:
            if mode not in ["Off", "Manual Defib", "Monitor"]:
                return
            
        self.mode = mode
        self.mode_idx = self.mode_list.index(mode)
        self.draw_mode_knob()
        if hasattr(self, 'mode_label'):
            self.mode_label.config(text=mode, fg="black")

        if self.sync_mode:
            self.exit_sync_mode()
        if self.aed_analyzing:
            self.aed_analyzing = False

        if mode == "AED":
            self._aed_energy_backup = self.energy
            if self.aed_child_mode:
                available = self.get_available_child_energies(self.child_age)
                self.energy = available[0] if available else 50
            else:
                self.energy = 100
            self.energy_idx = self.energy_levels.index(min(self.energy, max(self.energy_levels)))
            self.refresh_text()
        else:
            if self._aed_energy_backup is not None:
                self.energy = self._aed_energy_backup
                self.energy_idx = self.energy_levels.index(self.energy)
                self.refresh_text()
                self._aed_energy_backup = None

        if mode == "Off":
            self.power_on = False
            self.line_connected = False
            self.alarm_active = False
            self.timer_sec = 0
            self.screen_canvas.config(bg=self.COLOR_SCREEN_BG)
            self.screen_canvas.delete("all")
            self.charge_btn.config(state="disabled")
            self.shock_canvas.unbind("<Button-1>")
            self.shock_enabled = False
            if sound_charging:
                sound_charging.stop()
            if sound_charged:
                sound_charged.stop()
            if sound_rosc:
                sound_rosc.stop()
        else:
            if not self.power_on:
                self.timer_sec = 0
            self.power_on = True
            if not self.line_connected:
                self.alarm_active = True
            else:
                self.alarm_active = False
            self.charge_btn.config(state="normal")
            self.shock_canvas.bind("<Button-1>", lambda e: self.do_shock())
            self.draw_screen_static()
            self.redraw_dynamic_elements()
        
        self.update_pacer_panel_visibility()

    def update_pacer_panel_visibility(self):
        if hasattr(self, 'pacer_panel'):
            if self.mode == "Pacer":
                self.pacer_panel.pack(fill="x", pady=8)
            else:
                self.pacer_panel.pack_forget()

    def knob_mouse_wheel(self, event):
        try:
            if event.delta > 0:
                self.mode_idx = (self.mode_idx + 1) % len(self.mode_list)
            else:
                self.mode_idx = (self.mode_idx - 1) % len(self.mode_list)
            self.set_mode(self.mode_list[self.mode_idx])
        except Exception:
            traceback.print_exc()

    def knob_click(self, event):
        cx, cy = 120, 120
        angle_map = {0: -90, 1: -135, 2: -45, 3: 180, 4: 0}
        radius_inner = 80
        min_dist = float('inf')
        closest_idx = self.mode_idx
        for i, angle in angle_map.items():
            rad = math.radians(angle)
            x = cx + radius_inner * math.cos(rad)
            y = cy + radius_inner * math.sin(rad)
            dist = (event.x - x)**2 + (event.y - y)**2
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        if min_dist < 900:
            self.set_mode(self.mode_list[closest_idx])


if __name__ == "__main__":
    try:
        win = tk.Tk()
        app = MindrayD3DefibSim(win)
        win.mainloop()
    except Exception as e:
        traceback.print_exc()
        input("程序异常，按回车关闭")