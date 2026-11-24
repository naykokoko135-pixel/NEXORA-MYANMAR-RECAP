"""Audio-mix graphs for narration-led edits with optional ducked background music."""
from __future__ import annotations

def build_background_music_graph(volume: float = 0.18, ducking: bool = True,
                                 music_input_index: int = 3,
                                 narration_input_index: int = 1) -> tuple[str, str]:
    level = float(volume)
    if not 0.01 <= level <= 1.0:
        raise ValueError("Background music volume သည် 0.01 မှ 1.0 အတွင်း ဖြစ်ရပါမယ်။")
    if music_input_index < 0 or narration_input_index < 0 or music_input_index == narration_input_index:
        raise ValueError("Audio input index မမှန်ပါ။")
    music = f"[{music_input_index}:a]volume={level:.3f}[bgm]"
    if ducking:
        graph = (music + ";"
                 + f"[{narration_input_index}:a]asplit=2[narration_sc][narration_mix];"
                 + "[bgm][narration_sc]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=450[ducked];"
                 + "[narration_mix][ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]")
    else:
        graph = music + ";" + f"[{narration_input_index}:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    return graph, "[aout]"
