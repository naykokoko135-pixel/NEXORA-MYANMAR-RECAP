"""Validated FFmpeg transition graph builder."""
from __future__ import annotations
TRANSITIONS = {"fade":"fade","wipeleft":"wipeleft","wiperight":"wiperight","slideleft":"slideleft","slideright":"slideright","smoothleft":"smoothleft","smoothright":"smoothright","circleopen":"circleopen","circleclose":"circleclose","dissolve":"dissolve","pixelize":"pixelize"}
def build_transition_graph(durations: list[float], transition: str = "fade", seconds: float = 0.6) -> tuple[str, str]:
    key = str(transition or "fade").strip().lower()
    if key not in TRANSITIONS: raise ValueError("Transition မသိပါ။")
    if not durations or any(float(d) <= 0 for d in durations): raise ValueError("Clip duration မမှန်ပါ။")
    if len(durations) == 1: return "", "0:v"
    fade = float(seconds)
    if not 0.1 <= fade <= 2.0 or any(float(d) <= fade for d in durations): raise ValueError("Clip ကြာချိန်နှင့် Transition ကြာချိန် မကိုက်ညီပါ။")
    graph, prior, last = [], 0.0, "0:v"
    for index in range(1, len(durations)):
        prior += float(durations[index - 1]); output = f"v{index}"
        graph.append(f"[{last}][{index}:v]xfade=transition={TRANSITIONS[key]}:duration={fade:.3f}:offset={prior-fade*index:.3f}[{output}]")
        last = output
    return ";".join(graph), f"[{last}]"
