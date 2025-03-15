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
import librosa
from mutagen.mp3 import MP3
import torch
from einops import rearrange
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from diffrhythm_utils import (
    decode_audio,
    get_lrc_token,
    get_negative_style_prompt,
    get_reference_latent,
    prepare_model,
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
    elif torch.mps.is_available():
        device = "mps"

    @classmethod
    def INPUT_TYPES(cls):
               
        return {
            "required": {
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
            style_prompt: str, 
            # audio_length: int,
            lyrics_prompt: str = "", 
            style_audio: str = None,
            chunked: bool = False,
            seed: int = 0):

        # if audio_length == 95:
        #     max_frames = 2048
        # elif audio_length == 285:  # current not available
        #     max_frames = 6144
        max_frames = 2048
        cfm, tokenizer, muq, vae = prepare_model(self.device)

        lrc_prompt, start_time = get_lrc_token(lyrics_prompt, tokenizer, self.device)

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