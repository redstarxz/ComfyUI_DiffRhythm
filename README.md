[中文](README.md) | [English](README-en.md) 

# DiffRhythm Node for ComfyUI

Blazingly Fast and Embarrassingly Simple End-to-End Full-Length Song Generation.

![](https://github.com/billwuhao/ComfyUI_DiffRhythm/blob/master/images/2025-03-12_23-49-32.png)

## 📣 update

[2025-03-13]⚒️: Release version v1.0.0.

- All parameters are optional; you can generate random music without providing any parameters.

## Installation

```
cd ComfyUI/custom_nodes
git clone https://github.com/billwuhao/ComfyUI_DiffRhythm.git
cd ComfyUI_DiffRhythm
pip install -r requirements.txt

# python_embeded
./python_embeded/python.exe -m pip install -r requirements.txt
```

## Model Download

Models will be automatically downloaded to the `ComfyUI\models\TTS\DiffRhythm` folder.

The structure is as follows:

![](https://github.com/billwuhao/ComfyUI_DiffRhythm/blob/master/images/2025-03-13_00-08-51.png)

Manual Download Addresses:

https://huggingface.co/ASLP-lab/DiffRhythm-base/blob/main/cfm_model.pt  
https://huggingface.co/ASLP-lab/DiffRhythm-vae/blob/main/vae_model.pt  
https://huggingface.co/OpenMuQ/MuQ-MuLan-large/tree/main  
https://huggingface.co/OpenMuQ/MuQ-large-msd-iter/tree/main  
https://huggingface.co/FacebookAI/xlm-roberta-base/tree/main

## Environment Configuration

- Configure the following on Windows systems:

Download and install the latest version of [espeak-ng](https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0)

Add the environment variable `PHONEMIZER_ESPEAK_LIBRARY` to your system. The value should be the path to the `libespeak-ng.dll` file in your espeak-ng installation, for example: `C:\Program Files\eSpeak NG\libespeak-ng.dll`.

- On Linux systems, you need to install the `espeak-ng` package. Execute the following command to install:

`apt-get -qq -y install espeak-ng > /dev/null 2>&1`

It should support Mac, but has not been tested.

Enjoy the music! 🎶

## Acknowledgements

[DiffRhythm](https://github.com/ASLP-lab/DiffRhythm)

Thanks to the DiffRhythm team for their excellent work. Currently the strongest open-source music/song generation model 👍.
