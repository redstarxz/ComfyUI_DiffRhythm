# Copyright (c) 2025 ASLP-LAB
#               2025 Huakang Chen  (huakang@mail.nwpu.edu.cn)
#               2025 Guobin Ma     (guobin.ma@gmail.com)
#
# Licensed under the Stability AI License (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   https://huggingface.co/stabilityai/stable-audio-open-1.0/blob/main/LICENSE.md
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import torchaudio
from mutagen.mp3 import MP3
import torch
from einops import rearrange
import sys
import os
import json
from muq import MuQMuLan

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from model import DiT, CFM

from diffrhythm_utils import (
    decode_audio,
    get_lrc_token,
    get_negative_style_prompt,
    get_reference_latent,
    CNENTokenizer,
    load_checkpoint,
)


def inference(
    cfm_model,
    vae_model,
    cond,
    text,
    duration,
    style_prompt,
    negative_style_prompt,
    start_time,
    chunked=False,
):
        with torch.inference_mode():
            generated, _ = cfm_model.sample(
                cond=cond,
                text=text,
                duration=duration,
                style_prompt=style_prompt,
                negative_style_prompt=negative_style_prompt,
                steps=32,
                cfg_strength=4.0,
                start_time=start_time,
            )


        generated = generated.to(torch.float32)
        latent = generated.transpose(1, 2)  # [b d t]

        output = decode_audio(latent, vae_model, chunked=chunked)

        # Rearrange audio batch to a single sequence
        output = rearrange(output, "b d n -> d (b n)")
        # Peak normalize, clip, convert to int16, and save to file
        output = (
            output.to(torch.float32)
            .div(torch.max(torch.abs(output)))
            .clamp(-1, 1)
            .mul(32767)
            .to(torch.int16)
            .cpu()
        )

        return output


class MultiLinePrompt:
    @classmethod
    def INPUT_TYPES(cls):

        return {
            "required": {
                "multi_line_prompt": ("STRING", {
                    "multiline": True,
                    "default": ""}),
                },
        }

    CATEGORY = "MW-DiffRhythm"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "promptgen"

    def promptgen(self, multi_line_prompt: str):
        return (multi_line_prompt.strip(),)


class DiffRhythmRun:
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"

    node_dir = os.path.dirname(os.path.abspath(__file__))
    comfy_path = os.path.dirname(os.path.dirname(node_dir))
    model_path = os.path.join(comfy_path, "models", "TTS")
    models = ["cfm_model.pt", "cfm_full_model.pt"]

    @classmethod
    def INPUT_TYPES(cls):

        return {
            "required": {
                "model": (cls.models, {"default": "cfm_full_model.pt"}),
                # "audio_length": ([95, 285], {"default": 285, "tooltip": "The length of the audio to generate."}),
                "style_prompt": ("STRING", {
                    "multiline": True,
                    "default": ""}),
                },
            "optional": {
                "lyrics_prompt": ("STRING",),
                "style_audio": ("AUDIO", ),
                "chunked": ("BOOLEAN", {"default": False, "tooltip": "Whether to use chunked decoding."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
        }

    CATEGORY = "MW-DiffRhythm"
    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "diffrhythmgen"

    def diffrhythmgen(
            self,
            model: str,
            style_prompt: str,
            # audio_length: int,
            lyrics_prompt: str = "",
            style_audio: str = None,
            chunked: bool = False,
            seed: int = 0):

        if model == "cfm_model.pt":
            max_frames = 2048
        elif model == "cfm_full_model.pt":
            max_frames = 6144

        cfm, tokenizer, muq, vae = self.prepare_model(model, self.device)

        lrc_prompt, start_time = get_lrc_token(max_frames, lyrics_prompt, tokenizer, self.device)

        if style_audio:
            prompt = self.get_style_prompt(muq, style_audio)
        else:
            prompt = self.get_style_prompt(muq, prompt=style_prompt)

        negative_style_prompt = get_negative_style_prompt(self.device)
        latent_prompt = get_reference_latent(self.device, max_frames)

        try:
            generated_song = inference(
                cfm_model=cfm,
                vae_model=vae,
                cond=latent_prompt,
                text=lrc_prompt,
                duration=max_frames,
                style_prompt=prompt,
                negative_style_prompt=negative_style_prompt,
                start_time=start_time,
                chunked=chunked,
            )
        except Exception as e:
            raise

        audio_tensor = generated_song.unsqueeze(0)
        return ({"waveform": audio_tensor, "sample_rate": 44100},)

    @torch.no_grad()
    def get_style_prompt(self, model, audio=None, prompt=None):
        mulan = model

        if prompt is not None:
            return mulan(texts=prompt).half()

        if audio is None:
            raise ValueError("Audio data or style prompt must be provided")

        waveform = audio["waveform"]
        sample_rate = audio["sample_rate"]

        # 确保波形是正确的形状
        if len(waveform.shape) == 3:  # [1, channels, samples]
            waveform = waveform.squeeze(0)
        if waveform.shape[0] > 1:  # 如果是立体声，转换为单声道
            waveform = waveform.mean(0, keepdim=True)

        # 计算音频长度（秒）
        audio_len = waveform.shape[-1] / sample_rate

        if audio_len < 10:
            raise ValueError(f"The audio is too short ({audio_len:.2f} s), it takes at least 10 seconds.")

        # 提取中间 10 秒的片段
        mid_time = int((audio_len // 2) * sample_rate)
        start_sample = mid_time - int(5 * sample_rate)
        end_sample = start_sample + int(10 * sample_rate)
        wav_segment = waveform[..., start_sample:end_sample]

        # 重采样到 24kHz
        if sample_rate != 24000:
            wav_segment = torchaudio.transforms.Resample(sample_rate, 24000)(wav_segment)

        # 确保形状正确并移动到正确的设备
        wav = wav_segment.to(model.device)
        if len(wav.shape) == 1:
            wav = wav.unsqueeze(0)

        with torch.no_grad():
            audio_emb = mulan(wavs=wav)  # [1, 512]

        audio_emb = audio_emb.half()

        return audio_emb

    def prepare_model(self, model, device):
        from huggingface_hub import snapshot_download
        # prepare cfm model
        if model == "cfm_full_model.pt":
            dit_ckpt_path = f"{self.model_path}/DiffRhythm/cfm_full_model.pt"
            dit_config_path = f"{self.model_path}/DiffRhythm/config.json"
            if not os.path.exists(dit_ckpt_path):
                snapshot_download(repo_id="ASLP-lab/DiffRhythm-full",
                                    local_dir=f"{self.model_path}/DiffRhythm")

        elif model == "cfm_model.pt":
            dit_ckpt_path = f"{self.model_path}/DiffRhythm/cfm_model.pt"
            dit_config_path = f"{self.node_dir}/config/diffrhythm-1b.json"
            if not os.path.exists(dit_ckpt_path):
                snapshot_download(repo_id="ASLP-lab/DiffRhythm-base",
                                    local_dir=f"{self.model_path}/DiffRhythm")

        vae_ckpt_path = f"{self.model_path}/DiffRhythm/vae_model.pt"

        if not os.path.exists(vae_ckpt_path):
            snapshot_download(repo_id="ASLP-lab/DiffRhythm-vae",
                                local_dir=f"{self.model_path}/DiffRhythm",
                                ignore_patterns=["*safetensors"])

        try:
            with open(dit_config_path, "r", encoding="utf-8") as f:
                model_config = json.load(f)
        except Exception as e:
            raise

        dit_model_cls = DiT
        if model == "cfm_model.pt":
            cfm = CFM(
                transformer=dit_model_cls(**model_config["model"], use_style_prompt=True, max_pos=2048),
                num_channels=model_config["model"]["mel_dim"],
            )
        elif model == "cfm_full_model.pt":
            cfm = CFM(
                    transformer=dit_model_cls(**model_config["model"], use_style_prompt=True, max_pos=6144),
                    num_channels=model_config["model"]['mel_dim'],
                    use_style_prompt=True
                )
        cfm = cfm.to(device)

        try:
            cfm = load_checkpoint(cfm, dit_ckpt_path, device=device, use_ema=False)
        except Exception as e:
            raise

        # prepare tokenizer
        try:
            tokenizer = CNENTokenizer()
        except Exception as e:
            raise

        # prepare muq model
        try:
            # 修改这部分代码
            muq = MuQMuLan.from_pretrained("OpenMuQ/MuQ-MuLan-large", cache_dir=f"{self.model_path}/DiffRhythm")
        except Exception as e:
            raise

        muq = muq.to(device).eval()

        # prepare vae
        try:
            vae = torch.jit.load(vae_ckpt_path, map_location="cpu").to(device)
        except Exception as e:
            raise

        return cfm, tokenizer, muq, vae


from MWAudioRecorderDR import AudioRecorderDR

NODE_CLASS_MAPPINGS = {
    "DiffRhythmRun": DiffRhythmRun,
    "MultiLinePrompt": MultiLinePrompt,
    "AudioRecorderDR": AudioRecorderDR
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DiffRhythmRun": "DiffRhythm Run",
    "MultiLinePrompt": "Multi Line Prompt",
    "AudioRecorderDR": "MW Audio Recorder"
}
