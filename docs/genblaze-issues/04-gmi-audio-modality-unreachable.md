# The entire GMI Cloud audio modality is unreachable: the TTS/music param allowlists omit the API's required parameter

**Package versions:** `genblaze` 0.4.3, `genblaze-core` 0.3.6, `genblaze-gmicloud` 0.3.3
(the GitHub v0.5.0 release). Python 3.12, Windows.
**Provider:** GMI Cloud, audio models, via the request-queue API.

## Summary

No GMI Cloud audio model can be invoked through `genblaze-gmicloud` 0.3.3. Every TTS model
fails with HTTP 400 `text (Required parameter is missing)`, and music fails with
`lyrics (Required parameter is missing)` — because the SDK **strips those parameters before
sending**. They are absent from each family's `param_allowlist`, and `prompt` (which *is*
allow-listed) is never aliased onto them.

This is not an entitlement problem. The requests reach GMI and are rejected on payload
validation, which means the account can call these models — the SDK cannot construct a
valid body for them.

```python
import asyncio
from genblaze import Modality, Pipeline
from genblaze_gmicloud import GMICloudAudioProvider

pipe = Pipeline("tts").step(
    GMICloudAudioProvider(),
    model="minimax-tts-speech-2.6-turbo",
    modality=Modality.AUDIO,
    prompt="Handmade ceramic mug, thrown and glazed by hand.",
)
pipe.preflight = False
asyncio.run(pipe.arun(timeout=180, raise_on_failure=False))
# Step failed: GMICloud submit failed (400):
#   invalid payload parameters: text (Required parameter is missing) (code=invalid_input)
```

Passing the API's own parameter name explicitly does not help — the allowlist drops it,
and the SDK says so in its own log line before the request goes out:

```python
pipe = Pipeline("tts").step(
    GMICloudAudioProvider(), model="minimax-tts-speech-2.6-turbo",
    modality=Modality.AUDIO, text="...", voice_id="male-qn-qingse",
)
# Dropping non-allowlisted params for minimax-tts-speech-2.6-turbo: ['text']
# Step failed: GMICloud submit failed (400): invalid payload parameters: text (...)
```

## Root cause

From the SDK's own registry:

```python
from genblaze_gmicloud.models import build_audio_registry, build_image_registry

for fam in build_audio_registry().families:
    if fam.name == "gmi-audio-tts":
        t = fam.spec_template
        sorted(t.param_allowlist)
        # ['duration', 'language', 'negative_prompt', 'output_format',
        #  'prompt', 'reference_audio', 'seed', 'voice_id']
        "text" in t.param_allowlist        # False   ← required by the API
        t.param_aliases                    # {'voice': 'voice_id'}   ← no prompt -> text
```

| Family | API requires | Allow-listed? | Aliased from `prompt`? |
|---|---|---|---|
| `gmi-audio-tts` | `text` | ❌ | ❌ |
| `gmi-audio-music` | `lyrics` | ❌ | ❌ |
| `gmi-image-*` | `prompt` | ✅ | n/a |

The image and video families work because GMI's image/video endpoints happen to take
`prompt`. The audio endpoints follow the MiniMax/Inworld convention (`text`, `lyrics`), and
the audio spec templates appear to have inherited the image family's parameter vocabulary
without being reconciled against the audio API.

Affected models — every entry in `build_audio_registry().known()` except the one that is
independently dead:

| Model | Result |
|---|---|
| `minimax-tts-speech-2.6-turbo` | 400 — `text` missing |
| `inworld-tts-1.5-mini` | 400 — `text`, `voice_id` missing |
| `minimax-music-2.5` | 400 — `lyrics` missing |
| `minimax-audio-voice-clone-speech-2.6-hd` | (same family as TTS) |
| `elevenlabs-tts-v3` | separate problem: upstream probe returns DEAD / not in catalog |

## Impact

We had designed a voiceover step — listing copy → narration script → TTS → muxed onto the
generated product video — specifically to exercise Genblaze across a fourth modality, and
because TTS was the one place our app could show a *real* multi-model fallback chain
(ElevenLabs → MiniMax → Inworld). We cut the feature after this probe. Nothing in the
catalog, in `validate_model()`, or in the docs indicates audio is non-functional; the only
way to find out is to spend the time building against it and read a 400.

Related to [issue 01](01-validate-model-inverted.md): had `validate_model()` been an
entitlement/usability check, this would have surfaced in seconds rather than after a build.

## Expected

TTS and music steps invoked with `prompt=` should generate audio, consistent with how every
image and video step in the SDK behaves.

## Suggested fix

Adding the alias to each audio family's `spec_template` keeps one idiom across modalities
and needs no user-facing change:

```python
# gmi-audio-tts
param_aliases={"voice": "voice_id", "prompt": "text"},
param_allowlist=frozenset({..., "text"}),

# gmi-audio-music
param_aliases={"voice": "voice_id", "prompt": "lyrics"},
param_allowlist=frozenset({..., "lyrics"}),
```

Allow-listing `text`/`lyrics` alone would also unblock it, but then audio steps would take a
different parameter than every other modality, which is the kind of inconsistency the
unified Pipeline API exists to remove.

Happy to open a PR.

## Notes

`inworld-tts-1.5-mini` additionally reports `voice_id` as required while the SDK treats it
as optional, so a default voice per family may be worth considering alongside the alias.
