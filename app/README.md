# 无人机巡检系统：轻量部署交付

交付分成两个文件夹。**只收到 `01-app` 就能安装并启动，`02-data` 可晚些再发，也可以完全不发。** 原始开发目录、视频和历史实验文件不会被打包程序移动或删除。

```text
部署目录/
├── 01-app/                 源代码、依赖清单、安装/启动脚本、部署文档
│   ├── setup.bat           Windows 首次安装
│   ├── start.bat           Windows 日常启动
│   ├── deploy.py           通用安装、启动、检查入口
│   ├── uav-inspection-ui/  前端源码与 npm 锁文件
│   └── uav-inspection-backend/ 后端源码与 Python 依赖清单
└── 02-data/                可选：视频、字幕、模型、已有分析结果
    ├── uav-inspection-backend/
    ├── uav-inspection-ui/public/rose-pictures/
    ├── measurement_data/
    ├── prelabel_output/instances_20260715/
    ├── models/
    └── prediction_output/
```

## 给部署老师：最快启动

1. 安装 **Python 3.12** 和 **Node.js 22.12 以上或 24**，确认 `python`、`node`、`npm` 可用。其他已支持的 Python 版本为 3.10–3.13。
2. 解压 `01-app.zip`，进入 `01-app`。**不用等待视频数据包。**
3. Windows 双击 `setup.bat`，看到安装成功后双击 `start.bat`。
4. 浏览器访问 **http://127.0.0.1:8002**，接口文档在 **http://127.0.0.1:8002/docs**。
5. 关闭运行窗口或按 `Ctrl+C` 停止服务。

首次安装需要联网下载依赖。交付包中的“依赖文件”是依赖清单与前端锁文件，**不是第三方库的离线安装包**；不复制发送者的 `node_modules`、虚拟环境、GPU 库。Python 的安装结果放在 `01-app/.venv-deploy`，不会修改系统 Python 或旧开发环境。

Linux/macOS 在 `01-app` 内运行：

```bash
bash setup.sh
bash start.sh
```

Linux 需提供 Python venv、pip 和 OpenCV 所需的系统运行库；如出现 `libGL.so.1` 或 `libglib-2.0.so.0` 缺失，在 Debian/Ubuntu 安装 `python3-venv libgl1 libglib2.0-0` 后重试。以上平台脚本已提供；实际部署验证环境为 Windows。

## 没有数据时哪些功能可用

- 首页、各模块页面、接口文档和基础服务可以运行。
- 视频和测量任务显示为空，缺少照片时显示占位说明；仍可上传自己的视频。
- 真实 AI 检测需要**对应模型 + 可选推理依赖**，缺少时返回明确提示，不伪造识别结果。
- 外墙模块原有的规则回退仍可用，不等同于已加载 AI 模型。
- 数字玫瑰园和病虫害部分模块包含原有示例/模拟内容，不代表现场实时结果。
- 基础启动不要求 MongoDB、WebODM 或 GPU。WebODM 重建、外部地图、真实无人机接入等外部功能仍需各自的服务或网络，不包含在本交付中。

## 后续补齐数据和模型

将 `02-data` 放在 `01-app` 旁边，保持里面的子目录不变。若第一次运行已经生成空的 `02-data`，把收到的数据合并进去；**已有上传文件重名时不要直接覆盖**。然后重启程序。

数据也可以放到其他磁盘，不必复制回源码：

```powershell
python deploy.py start --data-dir "D:\uav-data"
```

或者设置环境变量 `UAV_DATA_DIR`。优先级：`--data-dir` > 环境变量 > 交付包的 `deployment-layout.json` 中的相对路径。源码原目录未设置时仍使用原来的数据位置。

安装可选 CPU 推理依赖（下载体积较大；只需执行一次）：

```powershell
python deploy.py install --backend-only --inference
```

默认不会自动下载模型。各模块使用 `02-data/uav-inspection-backend` 下的原始对应权重：

| 模块 | 数据包内模型路径 |
| --- | --- |
| 客流热力图 | `heatmapweight/renliu.pt` |
| 玫瑰产量 | `roseapp/rose-detect-best.pt` |
| 通信基站 | `telecomapp/station2-best.pt` |
| 电杆线路 | `powerapp/wire-pole-seg.pt` |
| 乔木修剪 | `treeapp/tree-pruning-best.pt` |
| 建筑外墙 | `wallapp/wall-damage-best.pt` |

有 NVIDIA GPU 的老师可自行安装与显卡驱动匹配的 PyTorch，然后安装 `uav-inspection-backend/requirements-inference.txt`；不要把本机 CUDA 环境直接打包搬过去。视频浏览器播放取决于编码，H.264 最兼容；需要转码时另行提供 FFmpeg。

## 发邮件前打包（发送者）

在原项目根目录执行：

```powershell
python scripts/build_delivery.py
```

结果在新建的 `delivery/时间戳/`。优先发送里面的 **`01-app.zip`**；`manifest.json` 记录实际文件与体积。打包会复制可选运行数据，但不会改动原文件。

不复制任何大型数据、只生成程序包：

```powershell
python scripts/build_delivery.py --without-data
```

如确实要通过邮件发送全部运行数据，可按每片 18 MiB 生成分卷（需预留额外磁盘空间）：

```powershell
python scripts/build_delivery.py --data-volumes-mb 18
```

视频本身已压缩，原始数据仍可能有数 GB，分卷不会显著减少总量。邮箱还可能对附件格式、总容量和编码后大小有限制，建议先只发程序包。分卷拼接和校验方法见生成的数据说明及 `python scripts/build_delivery.py --help`。

收到全部分卷和 `02-data.parts.json` 后，将它们放在 `01-app` 旁边，在该父目录执行以下命令，然后解压生成的普通 ZIP 即可：

```powershell
python 01-app/scripts/build_delivery.py --join-data . --output 02-data.zip
```

拼接会逐片检查 SHA-256，缺片或损坏时拒绝生成 ZIP。程序不会自动解压或覆盖已有数据。

程序包排除：本机依赖、缓存、旧构建、视频、模型权重、训练数据、实验输出、备份权重、个人环境配置。训练工具的源码仍保留；训练所需的额外数据、PDAL 等环境不属于基础部署，原件仍在原目录。

## 检查与开发

```powershell
python deploy.py doctor
python deploy.py start --backend-only
python deploy.py dev
```

正式使用只运行 `start.bat`，由一个进程在 8002 同时提供前端、API 和 WebSocket，不再启动重复的 8003 服务。`dev` 仅供前端开发，访问 5173，后端需单独启动；可用 `--backend-url` 改开发代理目标。

端口冲突可用 `python deploy.py start --port 8010`。只有需要受信任的教学局域网访问时才使用 `--host 0.0.0.0`。**本项目未配置用户认证，不能直接暴露到公网**；公网部署需额外的访问控制、HTTPS 与反向代理。

自动化测试：根目录 `python -m unittest discover -s tests -v`；后端测试需要额外安装 `httpx`，在后端目录执行 `python -m unittest discover -s tests -v`。测试只在临时目录写入，不修改原视频。
