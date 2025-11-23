def merge_clips(clips):
    if not clips:
        return []
    clips.sort(key=lambda x: x["start"])
    merged = [clips[0]]

    for c in clips[1:]:
        prev = merged[-1]
        if c["start"] <= prev["end"]:
            prev["end"] = max(prev["end"], c["end"])
        else:
            merged.append(c)
    return merged
# clip_service placeholder
