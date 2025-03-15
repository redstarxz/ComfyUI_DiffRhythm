[中文](README.md) | [English](README-en.md) 

# DiffRhythm 的 ComfyUI 节点

快速而简单的端到端全长歌曲生成.

![](https://github.com/billwuhao/ComfyUI_DiffRhythm/blob/master/images/2025-03-12_23-49-32.png)


## 📣 更新

[2025-03-13]⚒️: 发布版本 v1.0.0.

- 所有参数均是可选的, 不提供任何参数随机生成音乐.

## 安装

```
cd ComfyUI/custom_nodes
git clone https://github.com/billwuhao/ComfyUI_DiffRhythm.git
cd ComfyUI_DiffRhythm
pip install -r requirements.txt

# python_embeded
./python_embeded/python.exe -m pip install -r requirements.txt
```

## 模型下载

模型会自动下载到 `ComfyUI\models\TTS\DiffRhythm` 文件夹下.

结构如下:

![](https://github.com/billwuhao/ComfyUI_DiffRhythm/blob/master/images/2025-03-13_00-08-51.png)

手动下载地址:

https://huggingface.co/ASLP-lab/DiffRhythm-base/blob/main/cfm_model.pt  
https://huggingface.co/ASLP-lab/DiffRhythm-vae/blob/main/vae_model.pt  
https://huggingface.co/OpenMuQ/MuQ-MuLan-large/tree/main  
https://huggingface.co/OpenMuQ/MuQ-large-msd-iter/tree/main  
https://huggingface.co/FacebookAI/xlm-roberta-base/tree/main

## 环境配置

Windows 系统做如下配置. 

下载安装最新版 [espeak-ng](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0)

添加环境变量 `PHONEMIZER_ESPEAK_LIBRARY` 到系统中, 值是你安装的 espeak-ng 软件中 `libespeak-ng.dll` 文件的路径, 例如: `C:\Program Files\eSpeak NG\libespeak-ng.dll`.

Linux 系统下, 需要安装 `espeak-ng` 软件包. 执行如下命令安装:

`apt-get -qq -y install espeak-ng > /dev/null 2>&1`

应该支持 Mac, 但尚未测试.

享受音乐吧🎶

## 鸣谢

[DiffRhythm](https://github.com/ASLP-lab/DiffRhythm)

感谢 DiffRhythm 团队的卓越的工作, 目前最强开源 音乐/歌曲 生成模型👍.