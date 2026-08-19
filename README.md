# D3-Sim-v11.31

> BeneHeart D3 Sim v11.31 · 17岁独立开源 · PKAST药物代谢动力学引擎 · 医学模拟 · 欢迎Star

---

## 📌 这是什么？

一个面向**实习医学生、规培医师、急诊急救实训教学**的除颤模拟系统。  
17岁独立开发，27天完成。

---

## ⚡ 核心功能

- **PKAST 药代动力学模拟引擎** — 药物起效、代谢、半衰期、浓度曲线全模拟
- **动态阻抗安全锁** — 阻抗 >200Ω 自动拦截充电，还原临床安全机制
- **抢救复盘 CodeSummary** — 自动生成抢救简报，包含电击次数、用药清单、AI优化建议
- **ECG Lab 波形对比工作台** — 多通道心电波形并列/叠加对比，支持速度调节
- **4种工作模式** — 监护 / 手动除颤 / AED / 起搏

---

## 🚀 下载与运行

### 方式一：直接运行 EXE（推荐，无需安装 Python）

1. 前往 [Releases](https://github.com/Mingzs082317/D3-Sim-v11.31/releases) 页面
2. 下载 `d3_v11.31.exe`
3. 右键选择「以管理员身份运行」
4. 双击即可使用

### 方式二：源码运行（开发者）

```bash
git clone https://github.com/Mingzs082317/D3-Sim-v11.31.git
cd D3-Sim-v11.31
pip install pygame pillow
python d3_v11.31.py
```

---

## 📁 文件说明

| 文件 | 说明 |
|---|---|
| `d3_v11.31.exe` | 主程序（双击运行） |
| `d3_v11.31.py` | 完整源码 |
| `app.ico` | 程序图标 |
| `charging.mp3` / `charged.mp3` / `shock.mp3` / `rosc.mp3` | 音效文件 |
| `Mindray BeneHeart D3 Sim v11.31 ... 说明书.pdf` | 完整使用说明 |

---

## 📖 完整说明书

见仓库根目录下的 PDF 文件：[说明书](./Mindray%20BeneHeart%20D3%20Sim%20v11.31%20临床安全与复盘系统（BSSS-EMC璧山中学电子科教与融媒体发展促进中心电子平台第二大子系统）程序安装及操作说明书.pdf)

---

## 📄 许可证

本项目采用 **GNU General Public License v3.0** 开源协议。  
详细信息请查看 [LICENSE](./LICENSE) 文件。

---

## ⭐ 欢迎

- Star 支持 · Fork 学习 · Issue 反馈
- 作者：家茗 (Mingzs) · 17岁 · 独立开发者

---

**Made with ❤️ for medical education**
